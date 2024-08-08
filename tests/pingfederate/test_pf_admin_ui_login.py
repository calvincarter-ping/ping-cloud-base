import os
import unittest

from selenium.common.exceptions import NoSuchElementException

import pingone_ui as p1_ui


@unittest.skipIf(
    os.environ.get("ENV_TYPE") == "customer-hub",
    "Customer-hub CDE detected, skipping test module",
)
class TestPingFederateUILogin(p1_ui.ConsoleUILoginTestBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.public_hostname = os.getenv(
            "PINGFEDERATE_ADMIN_PUBLIC_HOSTNAME",
            f"https://pingfederate-admin.{os.environ['TENANT_DOMAIN']}",
        )
        cls.username = f"sso-pingfederate-test-user-{cls.tenant_name}"
        cls.password = "2FederateM0re!"
        cls.delete_pingone_user(
            endpoints=cls.p1_environment_endpoints, username=cls.username
        )
        cls.create_pingone_user(
            username=cls.username,
            password=cls.password,
            role_attribute_name="p1asPingFederateRoles",
            role_attribute_values=[f"{cls.environment}-pf-roleadmin"],
            population_id=cls.population_id,
        )
        cls.external_user_username = (
            f"pingfederate-external-idp-test-user-{cls.tenant_name}"
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
        # PingFederate has a pop-up that may or may not be displayed
        cls.access_granted_xpaths = [
            "//div[contains(text(), 'Welcome to PingFederate')]",
            "//div[contains(text(), 'Cluster')]",
        ]
        cls.access_denied_xpaths = [
            "//span[contains(text(), 'An error occurred while trying to login with OIDC')]"
        ]

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

    def test_user_can_access_pingfederate_admin_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.public_hostname)
        # Attempt to access the console with SSO
        self.pingone_login()
        self.browser.get(self.public_hostname)
        try:
            self.assertTrue(
                p1_ui.any_browser_element_displayed(
                    self.browser, self.access_granted_xpaths
                ),
                f"PingFederate Admin console 'Cluster' was not displayed when attempting to access {self.public_hostname}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"PingFederate Admin console 'Cluster' was not displayed when attempting to access {self.public_hostname}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_external_user_can_access_pingfederate_admin_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.public_hostname)
        try:
            p1_ui.login_from_external_idp(
                browser=self.browser,
                console_url=self.public_hostname,
                username=self.external_user_username,
                password=self.external_user_password,
            )
            self.assertTrue(
                p1_ui.any_browser_element_displayed(
                    self.browser, self.access_granted_xpaths
                ),
                f"PingFederate Admin console was not displayed when attempting to access {self.public_hostname}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"PingFederate Admin console was not displayed when attempting to access {self.public_hostname}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_user_without_role_cannot_access_pingfederate_admin_console(self):
        self.wait_until_url_is_reachable(self.public_hostname)
        p1_ui.login_as_pingone_user(
            browser=self.browser,
            console_url=self.public_hostname,
            username=self.no_role_user_username,
            password=self.no_role_user_password,
        )

        self.assertTrue(
            p1_ui.any_browser_element_displayed(
                browser=self.browser,
                xpaths=self.access_denied_xpaths,
            ),
            f"Expected 'An error occurred while trying to login with OIDC' to be in browser contents: "
            f"{self.browser.page_source}",
        )


if __name__ == "__main__":
    unittest.main()
