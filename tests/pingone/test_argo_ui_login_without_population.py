import os
import unittest

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

from pingone import common as p1_utils
import pingone_ui as p1_ui


class TestArgoUILoginWithoutPopulation(p1_ui.ConsoleUILoginTestBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.public_hostname = os.getenv(
            "ARGOCD_PUBLIC_HOSTNAME",
            f"https://argocd.{os.environ['TENANT_DOMAIN']}",
        )
        cls.username = f"sso-argocd-test-user-{cls.tenant_name}"
        cls.password = "2FederateM0re!"
        cls.delete_pingone_user()
        cls.create_pingone_user(role_attribute_name="p1asPingRoles",
                                population_id="1234a567-b890-1234-c5d6-78ef90g12345") # dummy population id

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.delete_pingone_user()

    def test_a_user_cannot_access_argocd_console_without_argopingbeluga_role(self):
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.public_hostname)
        # Attempt to access the console with SSO
        self.pingone_login()
        self.browser.get(f"{self.public_hostname}/auth/login")
        self.browser.implicitly_wait(10)
        try:
            title = self.browser.find_element(
                By.XPATH, "//span[contains(text(), 'Applications')]"
            )
            wait = WebDriverWait(self.browser, timeout=10)
            wait.until(lambda t: title.is_displayed())
            self.assertFalse(
                title.is_displayed(),
                f"ArgoCD console 'Applications' page was not displayed when attempting to access {self.public_hostname}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"ArgoCD console 'Applications' page was not displayed when attempting to access {self.public_hostname}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

    def test_b_user_can_access_argocd_console_after_adding_role(self):
        # Assign argo-pingbeluga role to the user
        p1_utils.update_pingone_user(role_attribute_name="p1asPingRoles",
                                     role_attribute_values=["argo-pingbeluga"],
                                     population_id="1234a567-b890-1234-c5d6-78ef90g12345")
        # Logout from the console. Re-login is required for role assignment change to take effect
        self.pingone_logout()
        # Re-login into the console
        self.pingone_login()
        # Wait for admin console to be reachable if it has been restarted by another test
        self.wait_until_url_is_reachable(self.public_hostname)
        # Attempt to access the console with SSO
        self.pingone_login()
        self.browser.get(f"{self.public_hostname}/auth/login")
        self.browser.implicitly_wait(10)
        try:
            title = self.browser.find_element(
                By.XPATH, "//span[contains(text(), 'Applications')]"
            )
            wait = WebDriverWait(self.browser, timeout=10)
            wait.until(lambda t: title.is_displayed())
            self.assertTrue(
                title.is_displayed(),
                f"ArgoCD console 'Applications' page was not displayed when attempting to access {self.public_hostname}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )
        except NoSuchElementException:
            self.fail(
                f"ArgoCD console 'Applications' page was not displayed when attempting to access {self.public_hostname}. SSO may have failed. Browser contents: {self.browser.page_source}",
            )

if __name__ == "__main__":
    unittest.main()
