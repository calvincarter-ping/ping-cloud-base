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


class ConsoleUILoginTestBase(unittest.TestCase):
    tenant_name = ""
    environment = ""
    username = ""
    password = ""
    group_names = []
    p1_client = None
    p1_environment_endpoints = None
    p1_session = None
    population_id = ""
    default_population_id = ""
    console_url = ""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chromedriver_autoinstaller.install()
        cls.tenant_name = os.getenv("TENANT_NAME")
        cls.environment = os.getenv("ENV", "dev")
        cls.p1_client = p1_utils.get_client()
        cls.p1_session = requests_oauthlib.OAuth2Session(
            cls.p1_client["client_id"], token=cls.p1_client["token"]
        )
        cls.p1_environment_endpoints = p1_utils.EnvironmentEndpoints(
            p1_utils.API_LOCATION, ENV_ID
        )
        cls.population_id = p1_utils.get_population_id(
            token_session=cls.p1_session,
            endpoints=cls.p1_environment_endpoints,
            name=cls.tenant_name,
        )
        cls.default_population_id = p1_utils.get_population_id(
            token_session=cls.p1_session,
            endpoints=cls.p1_environment_endpoints,
            name="Default",
        )
        cls.no_role_user_username = f"no-role-{cls.tenant_name}"
        cls.no_role_user_password = "2FederateM0re!"
        cls.delete_pingone_user(
            endpoints=cls.p1_environment_endpoints,
            username=cls.no_role_user_username,
        )
        cls.create_pingone_user(
            username=cls.no_role_user_username,
            password=cls.no_role_user_password,
            population_id=cls.population_id,
        )
        # External IdP setup
        cls.external_idp_env_id = os.getenv("EXTERNAL_IDP_ENVIRONMENT_ID")
        cls.external_idp_endpoints = p1_utils.EnvironmentEndpoints(
            p1_utils.API_LOCATION, cls.external_idp_env_id
        )

    @classmethod
    def tearDownClass(cls):
        cls.delete_pingone_user(
            endpoints=cls.p1_environment_endpoints,
            username=cls.no_role_user_username,
        )
        cls.p1_session.close()

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

    @classmethod
    def create_pingone_user(
        cls,
        username: str,
        password: str,
        role_attribute_name: str = None,
        role_attribute_values: list = None,
        population_id: str = None,
    ):
        """
        Create a PingOne user
        """

        user_payload = {
            "email": "do-not-reply@pingidentity.com",
            "name": {"given": username, "family": "User"},
            "username": username,
            "password": {"value": password, "forceChange": "false"},
        }

        if population_id:
            user_payload["population"] = {"id": population_id}

        if role_attribute_name and role_attribute_values:
            user_payload[role_attribute_name] = role_attribute_values

        p1_utils.create_user(
            token_session=cls.p1_session,
            endpoints=cls.p1_environment_endpoints,
            name=username,
            payload=user_payload,
        )

        p1_utils.add_role_to_user(
            token_session=cls.p1_session,
            endpoints=cls.p1_environment_endpoints,
            user_name=username,
            role_name="Identity Data Read Only",
            environment_id=ENV_ID,
        )

    @classmethod
    def create_external_idp_user(
        cls,
        endpoints: p1_utils.EnvironmentEndpoints,
        username: str,
        password: str,
    ):
        """
        Create a user in the default population in an external PingOne environment
        """
        user_payload = {
            "email": "do-not-reply@pingidentity.com",
            "name": {"given": username, "family": "User"},
            "username": username,
            "password": {"value": password, "forceChange": "false"},
            "p1asArgoCDRoles": ["argo-configteam"],
            "p1asOpensearchRoles": ["os-configteam"],
            "p1asPingAccessRoles": ["dev-pa-audit"],
            "p1asPingFederateRoles": ["dev-pf-audit"],
        }

        p1_utils.create_user(
            token_session=cls.p1_session,
            endpoints=endpoints,
            name=username,
            payload=user_payload,
        )

    @classmethod
    def delete_pingone_user(
        cls,
        endpoints: p1_utils.EnvironmentEndpoints,
        username: str,
    ):
        p1_utils.delete_user(
            token_session=cls.p1_session,
            endpoints=endpoints,
            name=username,
        )

    def pingone_login(self):
        self.browser.get(ENV_UI_URL)
        self.browser.find_element(By.ID, "username").send_keys(self.username)
        self.browser.find_element(By.ID, "password").send_keys(self.password)
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
        self.pingone_login()
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
                f"PingOne console 'Environments' page was not displayed when attempting to access {ENV_UI_URL}. Browser contents: {self.browser.page_source}"
            )
