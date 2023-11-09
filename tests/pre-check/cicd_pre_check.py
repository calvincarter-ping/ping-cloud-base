import unittest
import requests
from os import getenv
from dotenv import load_dotenv

CI_SCRIPTS_DIR = getenv("SHARED_CI_SCRIPTS_DIR")

class CicdPreCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_dotenv(f"{CI_SCRIPTS_DIR}/k8s/deploy/ci-cd-cluster.properties")

    def test_ingress(self):
        dns_zone = getenv("PRIMARY_TENANT_DOMAIN", "ping-demo.com")
        subdomains = [
            "healthcheck",
            "metadata"
        ]
        for subdomain in subdomains:
            url = f"https://{subdomain}.{dns_zone}"
            try:
                response = requests.get(url, verify=False)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                self.fail(f"Failed to make GET request to {url}: {e}")

            self.assertEqual(response.status_code, 200)