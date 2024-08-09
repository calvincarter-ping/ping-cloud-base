import json
import logging
import os
import unittest

import chromedriver_autoinstaller
import requests
import requests_oauthlib
import selenium.common.exceptions
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
import tenacity
import urllib3
import warnings

import k8s_utils
from pingone import common as p1_utils

K8S = k8s_utils.K8sUtils()
ENV_METADATA_CM = K8S.get_configmap_values(namespace="ping-cloud", configmap_name="p14c-environment-metadata")
ENV_METADATA = json.loads(ENV_METADATA_CM.get("information.json"))
ENV_ID = ENV_METADATA.get("pingOneInformation").get("environmentId")
ENV_UI_URL = f"https://console-staging.pingone.com/?env={ENV_ID}#home?nav=home"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def wait_until_browser_element_displayed(browser: webdriver, xpath: str) -> WebElement:
    """
    Wait until the element is displayed in the browser
    :param browser: webdriver.Chrome()
    :param xpath: XPATH string, ex: "//span[contains(text(), 'Applications')]"
    """
    element = browser.find_element(By.XPATH, xpath)
    WebDriverWait(browser, timeout=10).until(lambda t: element.is_displayed())
    return element


def any_browser_element_displayed(browser: webdriver, xpaths: [str]) -> bool:
    """
    Check if any of the elements are displayed in the browser
    :param browser: webdriver.Chrome()
    :param xpaths: A list of XPATH strings, ex: ["//span[contains(text(), 'Applications')]", ...]
    :return: True if any of the elements are displayed, False otherwise
    """
    for xpath in xpaths:
        try:
            element = wait_until_browser_element_displayed(browser, xpath)
            if element.is_displayed():
                return True
        except NoSuchElementException:
            continue
    return False


def login_from_external_idp(browser: webdriver.Chrome, console_url: str, username: str, password: str):
    browser.get(console_url)
    browser.find_element(By.CLASS_NAME, "custom-provider-button").click()
    browser.find_element(By.ID, "username").send_keys(username)
    browser.find_element(By.ID, "password").send_keys(password)
    browser.find_element(By.CSS_SELECTOR, 'button[data-id="submit-button"]').click()


def login_as_pingone_user(browser: webdriver.Chrome, console_url: str, username: str, password: str):
    browser.get(console_url)
    browser.find_element(By.ID, "username").send_keys(username)
    browser.find_element(By.ID, "password").send_keys(password)
    browser.find_element(By.CSS_SELECTOR, 'button[data-id="submit-button"]').click()


class PingOneUITestConfig:

    def __init__(self, app_name: str, console_url: str, roles: {}, access_granted_xpaths: [str], access_denied_xpaths: [str]):
        self.app_name = app_name
        self.console_url = console_url
        self.roles = roles
        self.access_granted_xpaths = access_granted_xpaths
        self.access_denied_xpaths = access_denied_xpaths
        self.tenant_name = os.getenv("TENANT_NAME")
        self.client = p1_utils.get_client()
        self.session = requests_oauthlib.OAuth2Session(
            self.client["client_id"], token=self.client["token"]
        )
        self.environment_id = ENV_ID
        self.p1as_endpoints = p1_utils.EnvironmentEndpoints(
            p1_utils.API_LOCATION, self.environment_id
        )
        self.population_id = p1_utils.get_population_id(
            token_session=self.session,
            endpoints=self.p1as_endpoints,
            name=self.tenant_name,
        )

        # User with no roles for negative testing
        self.no_role_user = PingOneUser(
            session=self.session,
            environment_endpoints=self.p1as_endpoints,
            username=f"{self.app_name}-no-role-{self.tenant_name}",
            roles=None,
            population_id=self.population_id,
        )
        self.no_role_user.delete()
        self.no_role_user.create()

        # User local to the P1AS shared tenant environment
        self.local_user = PingOneUser(
            session=self.session,
            environment_endpoints=self.p1as_endpoints,
            username=f"{self.app_name}-sso-user-{self.tenant_name}",
            roles=self.roles,
            population_id=self.population_id,
        )
        self.local_user.delete()
        self.local_user.create(add_p1_role=True)

        # Default population user for negative testing
        self.default_pop_user = PingOneUser(
            session=self.session,
            environment_endpoints=self.p1as_endpoints,
            username=f"{self.app_name}-default-pop-{self.tenant_name}",
            roles=self.roles,
        )
        self.default_pop_user.delete()
        self.default_pop_user.create()

        # External IdP setup
        self.external_idp_env_id = os.getenv("EXTERNAL_IDP_ENVIRONMENT_ID")
        self.external_idp_endpoints = p1_utils.EnvironmentEndpoints(
            p1_utils.API_LOCATION, self.external_idp_env_id
        )
        # External IdP user for P1-to-P1 SSO testing
        self.external_user = PingOneUser(
            session=self.session,
            environment_endpoints=self.external_idp_endpoints,
            username=f"{self.app_name}-external-idp-test-user-{self.tenant_name}",
            roles=self.roles,
        )
        self.external_user.delete()
        self.external_user.create()
        self.shadow_external_user = PingOneUser(
            session=self.session,
            environment_endpoints=self.p1as_endpoints,
            username=f"{self.external_user.username}-{self.tenant_name}",
        )
        # Do not create shadow external user, delete only in case it exists from a previous run
        self.shadow_external_user.delete()

    def delete_users(self):
        self.local_user.delete()
        self.external_user.delete()
        self.shadow_external_user.delete()
        self.no_role_user.delete()
        self.default_pop_user.delete()


class PingOneUser:

    def __init__(self, session: requests_oauthlib.OAuth2Session, environment_endpoints: p1_utils.EnvironmentEndpoints, username: str, roles: {} = None, population_id: str = None):
        self.endpoints = environment_endpoints
        self.password = "2FederateM0re!"
        self.population_id = population_id
        self.roles = roles
        self.session = session
        self.username = username

    def create(self, add_p1_role: bool = False):
        payload = {
            "email": "do-not-reply@pingidentity.com",
            "name": {"given": self.username, "family": "User"},
            "username": self.username,
            "password": {"value": self.password, "forceChange": "false"},
        }

        if self.population_id:
            payload["population"] = {"id": self.population_id}

        if self.roles:
            for role_attribute_name, role_attribute_values in self.roles.items():
                payload[role_attribute_name] = role_attribute_values

        p1_utils.create_user(
            token_session=self.session,
            endpoints=self.endpoints,
            name=self.username,
            payload=payload,
        )

        if add_p1_role:
            environment_id = self.endpoints.env.split("/environments/")[1]
            self.add_pingone_identity_read_only_role(environment_id=environment_id)

    def add_pingone_identity_read_only_role(self, environment_id: str):
        p1_utils.add_role_to_user(
            token_session=self.session,
            endpoints=self.endpoints,
            user_name=self.username,
            role_name="Identity Data Read Only",
            environment_id=environment_id,
        )

    def delete(self):
        p1_utils.delete_user(
            token_session=self.session,
            endpoints=self.endpoints,
            name=self.username,
        )


class ConsoleUILoginTestBase(unittest.TestCase):
    """
    Base class for PingOne console UI login tests. Contains a basic suite of tests to verify that a user can log in to
    the PingOne console and access the app console with SSO.

    Add test cases specific to each app in the child classes.
    """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chromedriver_autoinstaller.install()
        cls.config = None

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.config.delete_users()

    def setUp(self):
        options = webdriver.ChromeOptions()
        # Ignore certificate error warning page from chrome
        options.add_argument("--ignore-ssl-errors=yes")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--headless=new")  # run in headless mode in CICD
        options.add_argument("--no-sandbox")  # run in Docker
        options.add_argument("--disable-dev-shm-usage")  # run in Docker
        self.browser = webdriver.Chrome(options=options)
        self.browser.implicitly_wait(10)
        self.addCleanup(self.browser.quit)

    def pingone_login(self, username: str, password: str):
        self.browser.get(ENV_UI_URL)
        self.browser.find_element(By.ID, "username").send_keys(username)
        self.browser.find_element(By.ID, "password").send_keys(password)
        self.browser.find_element(
            By.CSS_SELECTOR, 'button[data-id="submit-button"]'
        ).click()
        self.close_popup()

    def close_popup(self):
        try:
            # Handle verify email pop-up when presented
            close_modal_button = self.browser.find_element(
                By.CSS_SELECTOR, '[aria-label="Close modal window"]'
            )
            if close_modal_button:
                close_modal_button.click()
        except (
            selenium.common.exceptions.NoSuchElementException,
            selenium.common.exceptions.ElementNotInteractableException,
        ):
            pass

    @tenacity.retry(
        reraise=True,
        wait=tenacity.wait_fixed(5),
        before_sleep=tenacity.before_sleep_log(logger, logging.INFO),
        stop=tenacity.stop_after_attempt(60),
    )
    def wait_until_url_is_reachable(self, admin_console_url: str):
        try:
            warnings.filterwarnings(
                "ignore", category=urllib3.exceptions.InsecureRequestWarning
            )
            response = requests.get(
                admin_console_url, allow_redirects=True, verify=False
            )
            response.raise_for_status()
            warnings.resetwarnings()
        except requests.exceptions.HTTPError:
            raise

    def test_user_can_log_in_to_pingone(self):
        self.pingone_login(username=self.config.local_user.username, password=self.config.local_user.password)
        # The content iframe on the home page displays the list of environments, have to switch or selenium can't see it

        try:
            iframe = self.browser.find_element(By.ID, "content-iframe")
            self.browser.switch_to.frame(iframe)
            self.close_popup()
            self.assertTrue(
                "Environments" in self.browser.page_source,
                f"Expected 'Environments' to be in page source: {self.browser.page_source}",
            )
        except selenium.common.exceptions.NoSuchElementException:
            self.fail(
                f"PingOne console 'Environments' page was not displayed when attempting to access {ENV_UI_URL}. "
                f"Browser contents: {self.browser.page_source}"
            )

    def test_user_can_access_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.config.console_url)
        # Attempt to access the console with SSO
        self.pingone_login(username=self.config.local_user.username, password=self.config.local_user.password)
        self.browser.get(self.config.console_url)
        try:
            self.assertTrue(
                any_browser_element_displayed(
                    self.browser, self.config.access_granted_xpaths
                ),
                f"{self.config.app_name} console was not displayed when attempting to access "
                f"{self.config.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"{self.config.app_name} console was not displayed when attempting to access "
                f"{self.config.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_external_user_can_access_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.config.console_url)
        try:
            login_from_external_idp(
                browser=self.browser,
                console_url=self.config.console_url,
                username=self.config.external_user.username,
                password=self.config.external_user.password,
            )
            self.assertTrue(
                any_browser_element_displayed(
                    self.browser, self.config.access_granted_xpaths
                ),
                f"{self.config.app_name} console was not displayed when attempting to access "
                f"{self.config.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"{self.config.app_name} console was not displayed when attempting to access "
                f"{self.config.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_user_without_role_cannot_access_console(self):
        self.wait_until_url_is_reachable(self.config.console_url)
        login_as_pingone_user(
            browser=self.browser,
            console_url=self.config.console_url,
            username=self.config.no_role_user.username,
            password=self.config.no_role_user.password,
        )

        self.assertTrue(
            any_browser_element_displayed(
                browser=self.browser, xpaths=self.config.access_denied_xpaths
            ),
            f"Expected '{self.config.access_denied_xpaths}' to be in browser contents: {self.browser.page_source}",
        )

    def test_user_cannot_access_console_without_correct_population(self):
        self.wait_until_url_is_reachable(self.config.console_url)

        login_as_pingone_user(
            browser=self.browser,
            console_url=self.config.console_url,
            username=self.config.default_pop_user.username,
            password=self.config.default_pop_user.password,
        )

        self.assertTrue(
            any_browser_element_displayed(
                browser=self.browser, xpaths=self.config.access_denied_xpaths
            ),
            f"Expected '{self.config.access_denied_xpaths}' to be in browser contents: {self.browser.page_source}",
        )
