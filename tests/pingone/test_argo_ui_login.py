import os
import unittest

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

import pingone_ui as p1_ui


class TestArgoUILogin(p1_ui.ConsoleUILoginTestBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.public_hostname = os.getenv(
            "ARGOCD_PUBLIC_HOSTNAME",
            f"https://argocd.{os.environ['TENANT_DOMAIN']}",
        )
        cls.console_url = f"{cls.public_hostname}/auth/login"
        cls.local_user = p1_ui.PingOneUser(
            session=cls.p1_session,
            environment_endpoints=cls.p1_environment_endpoints,
            username=f"sso-argocd-test-user-{cls.tenant_name}",
            roles={"p1asArgoCDRoles": ["argo-configteam"]},
            population_id=cls.population_id,
        )
        cls.local_user.delete()
        cls.local_user.create(add_p1_role=True)
        cls.external_user = p1_ui.PingOneUser(
            session=cls.p1_session,
            environment_endpoints=cls.external_idp_endpoints,
            username=f"argocd-external-idp-test-user-{cls.tenant_name}",
            roles={"p1asArgoCDRoles": ["argo-configteam"]},
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

        cls.application_page_xpath = "//span[contains(text(), 'Applications')]"
        cls.access_granted_xpaths = [cls.application_page_xpath]
        cls.access_denied_xpaths = [
            "//h4[contains(text(), 'No applications available to you')]"
        ]

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.local_user.delete()
        cls.external_user.delete()
        cls.shadow_external_user.delete()

    def _setup(self, role_attribute_name, role_attribute_values, population_id):
        # Delete user if exists
        self.local_user.delete()
        # Create user
        self.local_user.roles = {role_attribute_name: role_attribute_values}
        self.local_user.population_id = population_id
        self.local_user.create(add_p1_role=True)
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.console_url)
        # Attempt to access the console with SSO
        self.pingone_login(username=self.local_user.username, password=self.local_user.password)

    def test_cust_user_can_access_argocd_with_correct_population(self):
        self._setup(
            role_attribute_name="p1asArgoCDRoles",
            role_attribute_values=["argo-configteam"],
            population_id=TestArgoUILogin.population_id,
        )

        self.browser.get(self.console_url)
        try:
            p1_ui.wait_until_browser_element_displayed(
                self.browser, self.application_page_xpath
            )
            app_list = self.browser.find_elements(
                By.CLASS_NAME, "applications-list__entry"
            )
            self.assertTrue(
                len(app_list) > 0,
                f"ArgoCD console 'Applications' page was not displayed when attempting to access {self.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"ArgoCD console 'Applications' page was not displayed when attempting to access {self.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_ping_user_can_access_argocd_with_any_population(self):
        self._setup(
            role_attribute_name="p1asPingRoles",
            role_attribute_values=["argo-pingbeluga"],
            population_id=TestArgoUILogin.default_population_id,
        )

        self.browser.get(self.console_url)
        try:
            p1_ui.wait_until_browser_element_displayed(
                self.browser, self.application_page_xpath
            )
            app_list = self.browser.find_elements(
                By.CLASS_NAME, "applications-list__entry"
            )
            self.assertTrue(
                len(app_list) > 0,
                f"Applications were not visible on ArgoCD console 'Applications' page when attempting to access {self.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"ArgoCD console 'Applications' page was not displayed when attempting to access {self.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_cust_user_cannot_access_argocd_without_correct_population(self):
        self._setup(
            role_attribute_name="p1asArgoCDRoles",
            role_attribute_values=["argo-configteam"],
            population_id=TestArgoUILogin.default_population_id,
        )

        self.browser.get(f"{self.console_url}/auth/login")
        try:
            p1_ui.wait_until_browser_element_displayed(
                self.browser, self.application_page_xpath
            )
            app_list = self.browser.find_elements(
                By.CLASS_NAME, "applications-list__entry"
            )
            self.assertTrue(
                len(app_list) == 0,
                f"Applications were visible on ArgoCD console 'Applications' page when attempting to access {self.console_url}. SSO may have succeeded. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"ArgoCD console 'Applications' page was not displayed when attempting to access {self.console_url}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_external_user_can_access_argocd_console(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.console_url)
        try:
            p1_ui.login_from_external_idp(
                browser=self.browser,
                console_url=self.console_url,
                username=self.external_user.username,
                password=self.external_user.password,
            )
            p1_ui.wait_until_browser_element_displayed(
                self.browser, self.application_page_xpath
            )
            app_list = self.browser.find_elements(
                By.CLASS_NAME, "applications-list__entry"
            )
            self.assertTrue(
                len(app_list) > 0,
                f"ArgoCD console was not displayed when attempting to access {self.console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"ArgoCD console was not displayed when attempting to access {self.console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_user_without_role_cannot_access_argocd_console(self):
        self.wait_until_url_is_reachable(self.console_url)
        try:
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
                f"Expected 'No applications available to you' to be in browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"ArgoCD console 'Applications' page was not displayed when attempting to access {self.console_url}. "
                f"SSO may have failed. Browser contents: {self.browser.page_source}",
            )


if __name__ == "__main__":
    unittest.main()
