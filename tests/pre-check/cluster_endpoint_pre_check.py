import os
import unittest
import warnings
from types import SimpleNamespace

import requests
from os import getenv

import urllib3
from tenacity import retry, stop_after_attempt, wait_fixed


class ClusterEndpointsPreCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Ignore warnings for insecure http requests
        warnings.filterwarnings(
            "ignore", category=urllib3.exceptions.InsecureRequestWarning
        )
        tenant_domain = getenv("PRIMARY_TENANT_DOMAIN", "ping-oasis.com")
        cls.domains = [
            f"argocd.{tenant_domain}",
            f"logs.{tenant_domain}",
            f"metadata.{tenant_domain}",
            f"self-service.{tenant_domain}",
            f"self-service-api.{tenant_domain}/docs",
            f"pingaccess-admin.{tenant_domain}",
            f"pingfederate-admin.{tenant_domain}",
            f"prometheus.{tenant_domain}",
        ]

        # Add optional domains
        if os.getenv("HEALTHCHECKS_ENABLED") == "true":
            cls.domains.append(f"healthcheck.{tenant_domain}")

    def test_ingress(self):
        for domain in self.domains:
            with self.subTest(msg=f"{domain} is not available"):
                try:
                    response = self.get_ingress_response(domain)
                except requests.exceptions.ConnectionError as err:
                    response = SimpleNamespace()
                    response.status_code = "ConnectionError"
                    response.text = err.message
                except requests.exceptions.HTTPError as err:
                    response = SimpleNamespace()
                    response.status_code = err.response.status_code
                    response.text = err.message
                self.assertEqual(
                    response.status_code,
                    200,
                    f"Unexpected status code for {domain}: {response.status_code}. Response: {response.text}"
                )

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def get_ingress_response(self, url_base):
        url = f"https://{url_base}"
        print(f"Checking URL: {url}")
        response = requests.get(url, verify=False, timeout=5)
        response.raise_for_status()        
        return response
