import os
import unittest

import requests
import requests.auth
import urllib3
import warnings

import b64
import k8s_utils
import oauth
import pingone_ui


@unittest.skipIf(
    os.environ.get("ENV_TYPE") == "customer-hub",
    "Customer-hub CDE detected, skipping test module",
)
class TestPFAdminAPILogin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ignore warnings for insecure http requests
        warnings.filterwarnings(
            "ignore", category=urllib3.exceptions.InsecureRequestWarning
        )
        # Ignore ResourceWarning for unclosed SSL sockets
        warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed <ssl.SSLSocket")
        cls.tenant_name = os.getenv("TENANT_NAME", f"{os.getenv('USER')}-primary")
        cls.environment = os.getenv("ENV", "dev")
        cls.user_attribute_name = "p1asPingFederateRoles"
        cls.role_names = [
            f"{cls.environment}-pf-roleadmin",
            f"{cls.environment}-pf-crypto",
            f"{cls.environment}-pf-expression",
            f"{cls.environment}-pf-useradmin",
            f"{cls.environment}-pf-audit",
        ]
        cls.app_name = f"client-{cls.tenant_name}-pingfederate-admin-sso"
        cls.auth_policy_name = f"client-{cls.tenant_name}"
        cls.k8s = k8s_utils.K8sUtils()
        cls.namespace = os.getenv("PING_CLOUD_NAMESPACE", "ping-cloud")
        cls.operator_resource_name = f"client-{cls.tenant_name}-pf-operator"
        cls.operator_scope_name = "p1asPFOperatorRoles"
        cls.admin_env_vars = cls.k8s.get_configmap_values(
            namespace=cls.namespace,
            configmap_name="pingfederate-admin-environment-variables",
        )
        passwords_secret = cls.k8s.get_namespaced_secret(
            namespace=cls.namespace, name="pingfederate-passwords"
        ).data
        cls.passwords = {k: b64.decode(v) for k, v in passwords_secret.items()}
        pf_p14c_secret = cls.k8s.get_namespaced_secret(
            namespace=cls.namespace, name="pingfederate-admin-p14c"
        ).data
        cls.p14c_secret = {k: b64.decode(v) for k, v in pf_p14c_secret.items()}
        customer_p1_app_secret = cls.k8s.get_namespaced_secret(
            namespace="argocd", name="customer-p1-app"
        )
        cls.customer_p1_app_secret = {k: b64.decode(v) for k, v in customer_p1_app_secret.data.items()}
        cls.admin_api_url = f"https://{cls.admin_env_vars['PF_ADMIN_PUBLIC_HOSTNAME']}/pf-admin-api/v1"
        cls.environment = os.getenv("ENV", "dev")

    def headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "X-XSRF-Header": "PingFederate"}

    def test_oauth_token_login(self):
        token = oauth.get_token(
            app_id=self.p14c_secret["PF_OIDC_CLIENT_ID"],
            app_secret=self.p14c_secret["PF_OIDC_CLIENT_SECRET"],
            app_token_url=f"{self.p14c_secret['PF_OIDC_ISSUER']}/token",
            scopes=self.operator_scope_name,
        )
        res = requests.get(
            url=f"{self.admin_api_url}/cluster/status",
            headers=self.headers(token),
            verify=False,
        )
        self.assertEqual(200, res.status_code)

    def test_user_access_token_login(self):
        ui_test_config = pingone_ui.PingOneUITestConfig(
            app_name="PingFederate-API",
            console_url=self.admin_env_vars["PF_ADMIN_PUBLIC_HOSTNAME"],
            roles={
                self.user_attribute_name: [
                    self.role_names[0],
                ]
            },
            access_granted_xpaths=[],
            access_denied_xpaths=[],
            create_local_only=True,
        )
        p1_ui = pingone_ui.PingOneUIDriver()
        p1_ui.setup_browser()
        p1_ui.self_service_login(
            url=f"https://self-service-api.{self.admin_env_vars['PRIMARY_TENANT_DOMAIN']}/api/v1/auth/login/pingfederate",
            username=ui_test_config.local_user.username,
            password=ui_test_config.local_user.password,
        )
        token = p1_ui.self_service_get_token()
        p1_ui.teardown_browser()
        res = requests.get(
            url=f"{self.admin_api_url}/cluster/status",
            headers=self.headers(token),
            verify=False,
        )
        self.assertEqual(200, res.status_code)

    def test_basic_auth_login(self):
        res = requests.get(
            url=f"{self.admin_api_url}/cluster/status",
            auth=requests.auth.HTTPBasicAuth(
                username=self.admin_env_vars["PF_ADMIN_USER_USERNAME"],
                password=self.passwords["PF_ADMIN_USER_PASSWORD"],
            ),
            headers={"X-XSRF-Header": "PingFederate"},
            verify=False,
        )
        self.assertEqual(200, res.status_code)
