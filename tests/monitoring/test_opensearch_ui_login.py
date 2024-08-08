import os
import unittest

from selenium.common.exceptions import NoSuchElementException

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
        cls.local_user = p1_ui.PingOneUser(
            session=cls.p1_session,
            environment_endpoints=cls.p1_environment_endpoints,
            username=f"sso-opensearch-test-user-{cls.tenant_name}",
            roles={"p1asOpensearchRoles": ["os-configteam"]},
            population_id=cls.population_id,
        )
        cls.local_user.delete()
        cls.local_user.create(add_p1_role=True)
        cls.external_user = p1_ui.PingOneUser(
            session=cls.p1_session,
            environment_endpoints=cls.external_idp_endpoints,
            username=f"opensearch-external-idp-test-user-{cls.tenant_name}",
            roles={"p1asOpensearchRoles": ["os-configteam"]},
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

        cls.access_granted_xpaths = ["//h4[contains(text(), 'Select your tenant')]"]
        cls.access_denied_xpaths = ["//h3[contains(text(), 'Missing Role')]"]

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.local_user.delete()
        cls.external_user.delete()
        cls.shadow_external_user.delete()

    def test_user_can_access_opensearch_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.console_url)
        # Attempt to access the console with SSO
        self.pingone_login(username=self.local_user.username, password=self.local_user.password)
        self.browser.get(self.console_url)
        try:
            self.assertTrue(
                p1_ui.any_browser_element_displayed(
                    self.browser, self.access_granted_xpaths
                ),
                f"Opensearch console was not displayed when attempting to access {self.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"Opensearch console was not displayed when attempting to access {self.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_external_user_can_access_opensearch_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.console_url)
        try:
            p1_ui.login_from_external_idp(
                browser=self.browser,
                console_url=self.console_url,
                username=self.external_user.username,
                password=self.external_user.password,
            )
            self.assertTrue(
                p1_ui.any_browser_element_displayed(
                    self.browser, self.access_granted_xpaths
                ),
                f"Opensearch console was not displayed when attempting to access {self.console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"Opensearch console was not displayed when attempting to access {self.console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_user_without_role_cannot_access_opensearch_console(self):
        self.wait_until_url_is_reachable(self.console_url)
        p1_ui.login_as_pingone_user(
            browser=self.browser,
            console_url=self.console_url,
            username=self.no_role_user.username,
            password=self.no_role_user.password,
        )

        self.assertTrue(
            p1_ui.any_browser_element_displayed(
                browser=self.browser, xpaths=self.access_denied_xpaths
            ),
            f"Expected 'Missing Role' to be in browser contents: {self.browser.page_source}",
        )


if __name__ == "__main__":
    unittest.main()
