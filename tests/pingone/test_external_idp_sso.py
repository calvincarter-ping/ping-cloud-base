import logging
import os
import unittest
import warnings

import chromedriver_autoinstaller
import requests
import requests_oauthlib
import tenacity
import urllib3
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

from pingone import common as p1_utils


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@tenacity.retry(
    reraise=True,
    wait=tenacity.wait_fixed(5),
    before_sleep=tenacity.before_sleep_log(logger, logging.INFO),
    stop=tenacity.stop_after_attempt(60),
)
def wait_until_url_is_reachable(admin_console_url: str):
    try:
        warnings.filterwarnings(
            "ignore", category=urllib3.exceptions.InsecureRequestWarning
        )
        response = requests.get(admin_console_url, allow_redirects=True, verify=False)
        response.raise_for_status()
        warnings.resetwarnings()
    except requests.exceptions.HTTPError:
        raise


def any_browser_element_displayed(browser: webdriver, xpaths: [str]) -> bool:
    """
    Check if any of the elements are displayed in the browser
    :param browser: webdriver.Chrome()
    :param xpaths: A list of XPATH strings, ex: ["//span[contains(text(), 'Applications')]", ...]
    :return: True if any of the elements are displayed, False otherwise
    """
    for xpath in xpaths:
        try:
            element = browser.find_element(By.XPATH, xpath)
            WebDriverWait(browser, timeout=10).until(lambda t: element.is_displayed())
            if element.is_displayed():
                return True
        except NoSuchElementException:
            continue
    return False


def create_external_idp_user(
    session=None, endpoints=None, username=None, password=None
):
    """
    Create a user in the default population
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
        token_session=session,
        endpoints=endpoints,
        name=username,
        payload=user_payload,
    )


def delete_external_idp_user(session=None, endpoints=None, username=None):
    """
    Deletes a user
    """
    p1_utils.delete_user(
        token_session=session,
        endpoints=endpoints,
        name=username,
    )


class TestExternalIdPSSO(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        chromedriver_autoinstaller.install()
        cls.tenant_name = os.getenv("TENANT_NAME")
        tenant_domain = os.environ["TENANT_DOMAIN"]
        cls.argocd_hostname = f"https://argocd.{tenant_domain}"
        cls.opensearch_hostname = f"https://logs.{tenant_domain}"
        cls.pingaccess_hostname = f"https://pingaccess-admin.{tenant_domain}"
        cls.pingfederate_hostname = f"https://pingfederate-admin.{tenant_domain}"

        cls.client = p1_utils.get_client()
        cls.session = requests_oauthlib.OAuth2Session(
            cls.client["client_id"], token=cls.client["token"]
        )
        cls.external_idp_env_id = os.getenv("EXTERNAL_IDP_ENVIRONMENT_ID")
        cls.external_idp_endpoints = p1_utils.EnvironmentEndpoints(
            p1_utils.API_LOCATION, cls.external_idp_env_id
        )

        # Test user setup
        cls.username = f"external-idp-test-user-{cls.tenant_name}"
        cls.password = "2FederateM0re!"
        delete_external_idp_user(
            session=cls.session,
            endpoints=cls.external_idp_endpoints,
            username=cls.username,
        )
        create_external_idp_user(
            session=cls.session,
            endpoints=cls.external_idp_endpoints,
            username=cls.username,
            password=cls.password,
        )

        # Chrome browser options
        cls.chrome_options = webdriver.ChromeOptions()
        cls.chrome_options.add_argument("--ignore-ssl-errors=yes")
        cls.chrome_options.add_argument("--ignore-certificate-errors")
        cls.chrome_options.add_argument(
            "--headless=new"
        )  # run in headless mode in CICD
        cls.chrome_options.add_argument("--no-sandbox")  # run in Docker
        cls.chrome_options.add_argument("--disable-dev-shm-usage")  # run in Docker

    @classmethod
    def tearDownClass(cls):
        delete_external_idp_user(
            session=cls.session,
            endpoints=cls.external_idp_endpoints,
            username=cls.username,
        )
        cls.session.close()

    def setUp(self):
        self.browser = webdriver.Chrome(options=self.chrome_options)
        self.browser.implicitly_wait(10)

    def tearDown(self):
        self.browser.quit()

    def login_from_external_idp(self, browser: webdriver.Chrome, console_url: str):
        browser.get(console_url)
        browser.find_element(By.CLASS_NAME, "custom-provider-button").click()
        browser.find_element(By.ID, "username").send_keys(self.username)
        browser.find_element(By.ID, "password").send_keys(self.password)
        browser.find_element(By.CSS_SELECTOR, 'button[data-id="submit-button"]').click()

    def test_external_user_can_access_argocd_console(self):
        console_url = f"{self.argocd_hostname}/auth/login"
        expected_xpaths = ["//span[contains(text(), 'Applications')]"]

        # Wait for admin console to be reachable if it has been restarted by another test
        wait_until_url_is_reachable(console_url)
        try:
            self.login_from_external_idp(browser=self.browser, console_url=console_url)
            self.assertTrue(
                any_browser_element_displayed(self.browser, expected_xpaths),
                f"Console was not displayed when attempting to access {console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"Console was not displayed when attempting to access {console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_external_user_can_access_opensearch_console(self):
        console_url = f"{self.opensearch_hostname}/auth/openid/login"
        expected_xpaths = ["//h4[contains(text(), 'Select your tenant')]"]

        # Wait for admin console to be reachable if it has been restarted by another test
        wait_until_url_is_reachable(console_url)
        try:
            self.login_from_external_idp(browser=self.browser, console_url=console_url)
            self.assertTrue(
                any_browser_element_displayed(self.browser, expected_xpaths),
                f"Console was not displayed when attempting to access {console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"Console was not displayed when attempting to access {console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_external_user_can_access_pingaccess_admin_console(self):
        console_url = self.pingaccess_hostname
        expected_xpaths = ["//div[contains(text(), 'Applications')]"]

        # Wait for admin console to be reachable if it has been restarted by another test
        wait_until_url_is_reachable(console_url)
        try:
            self.login_from_external_idp(browser=self.browser, console_url=console_url)
            self.assertTrue(
                any_browser_element_displayed(self.browser, expected_xpaths),
                f"Console was not displayed when attempting to access {console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"Console was not displayed when attempting to access {console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_external_user_can_access_pingfederate_admin_console(self):
        console_url = self.pingfederate_hostname
        # PingFederate has a pop-up that may or may not be displayed
        expected_xpaths = [
            "//div[contains(text(), 'Welcome to PingFederate')]",
            "//div[contains(text(), 'Cluster')]",
        ]

        # Wait for admin console to be reachable if it has been restarted by another test
        wait_until_url_is_reachable(console_url)
        try:
            self.login_from_external_idp(browser=self.browser, console_url=console_url)
            self.assertTrue(
                any_browser_element_displayed(self.browser, expected_xpaths),
                f"Console was not displayed when attempting to access {console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"Console was not displayed when attempting to access {console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )


if __name__ == "__main__":
    unittest.main()
