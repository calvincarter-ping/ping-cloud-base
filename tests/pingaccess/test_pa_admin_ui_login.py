import os
import unittest

from selenium.common.exceptions import NoSuchElementException

import pingone_ui as p1_ui


@unittest.skipIf(
    os.environ.get("ENV_TYPE") == "customer-hub",
    "Customer-hub CDE detected, skipping test module",
)
class TestPAAdminUILogin(p1_ui.ConsoleUILoginTestBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.public_hostname = os.getenv(
            "PA_ADMIN_PUBLIC_HOSTNAME",
            f"https://pingaccess-admin.{os.environ['TENANT_DOMAIN']}",
        )
        cls.username = f"sso-pingaccess-test-user-{cls.tenant_name}"
        cls.password = "2FederateM0re!"
        cls.delete_pingone_user(endpoints=cls.p1_environment_endpoints, username=cls.username)
        cls.create_pingone_user(
            username=cls.username,
            password=cls.password,
            role_attribute_name="p1asPingAccessRoles",
            role_attribute_values=[f"{cls.environment}-pa-admin"],
            population_id=cls.population_id
        )
        cls.external_user_username = f"pingaccess-external-idp-test-user-{cls.tenant_name}"
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
        cls.expected_xpaths = ["//div[contains(text(), 'Applications')]"]

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.delete_pingone_user(endpoints=cls.p1_environment_endpoints, username=cls.username)
        # Delete the external user from the external IdP environment and the main PingOne environment
        cls.delete_pingone_user(
            endpoints=cls.p1_environment_endpoints,
            username=f"{cls.external_user_username}-{cls.tenant_name}",
        )
        cls.delete_pingone_user(
            endpoints=cls.external_idp_endpoints,
            username=cls.external_user_username,
        )

    def test_user_can_access_pa_admin_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.public_hostname)
        # Attempt to access the PingAccess Admin console with SSO
        self.pingone_login()
        self.browser.get(self.public_hostname)
        try:
            self.assertTrue(
                p1_ui.any_browser_element_displayed(self.browser, self.expected_xpaths),
                f"PingAccess Admin console 'Applications' page was not displayed when attempting to access {self.public_hostname}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"PingAccess Admin console 'Applications' page was not displayed when attempting to access {self.public_hostname}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_external_user_can_access_pingaccess_admin_console(self):
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
                p1_ui.any_browser_element_displayed(self.browser, self.expected_xpaths),
                f"PingAccess Admin console was not displayed when attempting to access {self.public_hostname}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"PingAccess Admin console was not displayed when attempting to access {self.public_hostname}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )


if __name__ == "__main__":
    unittest.main()
