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
        cls.local_user = p1_ui.PingOneUser(
            session=cls.p1_session,
            environment_endpoints=cls.p1_environment_endpoints,
            username=f"sso-pingaccess-test-user-{cls.tenant_name}",
            roles={"p1asPingAccessRoles": [f"{cls.environment}-pa-audit"]},
            population_id=cls.population_id,
        )
        cls.local_user.delete()
        cls.local_user.create(add_p1_role=True)
        cls.external_user = p1_ui.PingOneUser(
            session=cls.p1_session,
            environment_endpoints=cls.external_idp_endpoints,
            username=f"pingaccess-external-idp-test-user-{cls.tenant_name}",
            roles={"p1asPingAccessRoles": [f"{cls.environment}-pa-audit"]},
        )
        cls.external_user.delete()
        cls.external_user.create()
        cls.shadow_external_user = p1_ui.PingOneUser(
            session=cls.p1_session,
            environment_endpoints=cls.p1_environment_endpoints,
            username=f"{cls.external_user.username}-{cls.tenant_name}",
        )
        # Do not create shadow external user, delete only in case it exists from a previous run
        cls.shadow_external_user.delete()

        cls.access_granted_xpaths = ["//div[contains(text(), 'Applications')]"]
        cls.access_denied_xpaths = ["//pre[contains(text(), 'Access Denied')]"]

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.local_user.delete()
        cls.external_user.delete()
        cls.shadow_external_user.delete()

    def test_user_can_access_pa_admin_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.public_hostname)
        # Attempt to access the PingAccess Admin console with SSO
        self.pingone_login(username=self.local_user.username, password=self.local_user.password)
        self.browser.get(self.public_hostname)
        try:
            self.assertTrue(
                p1_ui.any_browser_element_displayed(
                    self.browser, self.access_granted_xpaths
                ),
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
                username=self.external_user.username,
                password=self.external_user.password,
            )
            self.assertTrue(
                p1_ui.any_browser_element_displayed(
                    self.browser, self.access_granted_xpaths
                ),
                f"PingAccess Admin console was not displayed when attempting to access {self.public_hostname}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"PingAccess Admin console was not displayed when attempting to access {self.public_hostname}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_user_without_role_cannot_access_pingaccess_admin_console(self):
        self.wait_until_url_is_reachable(self.public_hostname)
        p1_ui.login_as_pingone_user(
            browser=self.browser,
            console_url=self.public_hostname,
            username=self.no_role_user.username,
            password=self.no_role_user.password,
        )

        self.assertTrue(
            p1_ui.any_browser_element_displayed(
                browser=self.browser, xpaths=self.access_denied_xpaths
            ),
            f"Expected 'Access Denied' to be in browser contents: {self.browser.page_source}",
        )


if __name__ == "__main__":
    unittest.main()
