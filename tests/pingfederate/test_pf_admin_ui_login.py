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
        cls.audit_role = {"p1asPingFederateRoles": [f"{cls.environment}-pf-roleadmin"]}
        cls.local_user = p1_ui.PingOneUser(
            session=cls.p1_session,
            environment_endpoints=cls.p1_environment_endpoints,
            username=f"sso-pingfederate-test-user-{cls.tenant_name}",
            roles=cls.audit_role,
            population_id=cls.population_id,
        )
        cls.local_user.delete()
        cls.local_user.create(add_p1_role=True)
        cls.external_user = p1_ui.PingOneUser(
            session=cls.p1_session,
            environment_endpoints=cls.external_idp_endpoints,
            username=f"pingfederate-external-idp-test-user-{cls.tenant_name}",
            roles=cls.audit_role,
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
        cls.local_user.delete()
        cls.external_user.delete()
        cls.shadow_external_user.delete()

    def test_user_can_access_pingfederate_admin_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.public_hostname)
        # Attempt to access the console with SSO
        self.pingone_login(username=self.local_user.username, password=self.local_user.password)
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
                username=self.external_user.username,
                password=self.external_user.password,
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
            username=self.no_role_user.username,
            password=self.no_role_user.password,
        )

        self.assertTrue(
            p1_ui.any_browser_element_displayed(
                browser=self.browser,
                xpaths=self.access_denied_xpaths,
            ),
            f"Expected 'An error occurred while trying to login with OIDC' to be in browser contents: "
            f"{self.browser.page_source}",
        )

    def test_user_cannot_access_console_without_correct_population(self):
        default_population_user = p1_ui.PingOneUser(
            session=self.p1_session,
            environment_endpoints=self.p1_environment_endpoints,
            username=f"pingfederate-default-pop-{self.tenant_name}",
            roles=self.audit_role,
        )
        default_population_user.create()
        self.addCleanup(default_population_user.delete)

        self.wait_until_url_is_reachable(self.public_hostname)

        p1_ui.login_as_pingone_user(
            browser=self.browser,
            console_url=self.public_hostname,
            username=default_population_user.username,
            password=default_population_user.password,
        )

        self.assertTrue(
            p1_ui.any_browser_element_displayed(
                browser=self.browser, xpaths=self.access_denied_xpaths
            ),
            f"Expected 'An error occurred while trying to login with OIDC' to be in browser contents: "
            f"{self.browser.page_source}",
        )


if __name__ == "__main__":
    unittest.main()
