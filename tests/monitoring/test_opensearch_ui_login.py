import os
import unittest

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

import pingone_ui as p1_ui


class TestOpensearchUILogin(p1_ui.ConsoleUILoginTestBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.public_hostname = os.getenv(
            "OPENSEARCH_PUBLIC_HOSTNAME",
            f"https://logs.{os.environ['TENANT_DOMAIN']}",
        )
        cls.console_url = f"{cls.public_hostname}/auth/openid/login"
        cls.username = f"sso-opensearch-test-user-{cls.tenant_name}"
        cls.password = "2FederateM0re!"
        cls.delete_pingone_user(
            endpoints=cls.p1_environment_endpoints, username=cls.username
        )
        cls.create_pingone_user(
            role_attribute_name="p1asPingRoles", role_attribute_values=["os-ping"]
        )
        cls.external_user_username = (
            f"opensearch-external-idp-test-user-{cls.tenant_name}"
        )
        cls.external_user_password = "2FederateM0re!"
        cls.delete_pingone_user(
            endpoints=cls.external_idp_endpoints,
            username=cls.external_user_username,
        )
        cls.delete_pingone_user(
            endpoints=cls.p1_environment_endpoints,
            username=f"{cls.external_user_username}-{cls.tenant_name}",
        )
        cls.create_external_idp_user(
            endpoints=cls.external_idp_endpoints,
            username=cls.external_user_username,
            password=cls.external_user_password,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.delete_pingone_user(
            endpoints=cls.p1_environment_endpoints, username=cls.username
        )
        # Delete the external user from the external IdP environment and the main PingOne environment
        cls.delete_pingone_user(
            endpoints=cls.p1_environment_endpoints,
            username=f"{cls.external_user_username}-{cls.tenant_name}",
        )
        cls.delete_pingone_user(
            endpoints=cls.external_idp_endpoints,
            username=cls.external_user_username,
        )

    def test_user_can_access_opensearch_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.console_url)
        # Attempt to access the console with SSO
        self.pingone_login()
        self.browser.get(self.console_url)
        self.browser.implicitly_wait(10)
        try:
            title = self.browser.find_element(
                By.XPATH, "//h4[contains(text(), 'Select your tenant')]"
            )
            wait = WebDriverWait(self.browser, timeout=10)
            wait.until(lambda t: title.is_displayed())
            self.assertTrue(
                title.is_displayed(),
                f"Opensearch console was not displayed when attempting to access {self.public_hostname}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"Opensearch console was not displayed when attempting to access {self.public_hostname}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_external_user_can_access_opensearch_console(self):
        expected_xpaths = ["//h4[contains(text(), 'Select your tenant')]"]

        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.console_url)
        try:
            p1_ui.login_from_external_idp(
                browser=self.browser,
                console_url=self.console_url,
                username=self.external_user_username,
                password=self.external_user_password,
            )
            self.assertTrue(
                p1_ui.any_browser_element_displayed(self.browser, expected_xpaths),
                f"Opensearch console was not displayed when attempting to access {self.console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"Opensearch console was not displayed when attempting to access {self.console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )


if __name__ == "__main__":
    unittest.main()
