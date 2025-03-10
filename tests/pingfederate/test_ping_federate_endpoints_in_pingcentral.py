import http
import unittest
from unittest.mock import patch, MagicMock

import responses
import requests
import os

# Configuration
PINGCENTRAL_HOST = f"https://{os.getenv('PC_ADMIN_PRIVATE_SITE_HOSTNAME')}"
USERNAME = "administrator"
PASSWORD = "2Federate"
paHost = os.getenv("PA_ADMIN_API_PUBLIC_HOSTNAME")
pfHost = os.getenv("PF_ADMIN_API_PUBLIC_HOSTNAME")
print(f"paHost: {paHost}")
print(f"pfHost: {pfHost}")

class TestPingCentralAPI(unittest.TestCase):
    """System test for verifying PingFederate and PingAccess environments in PingCentral"""

    @classmethod
    def setUpClass(cls):
        cls.auth = (USERNAME, PASSWORD)
        cls.headers = {"x-xsrf-header": "PingCentral"}
        cls.url = f"{PINGCENTRAL_HOST}/api/v1/environments"

    @responses.activate
    def test_pingcentral_api_status(self):
        """Test that PingCentral API is reachable and returns HTTP 200"""
        responses.add(
            method=responses.GET,
            url=self.url,
            status=http.HTTPStatus.OK,
            match=[responses.matchers.header_matcher(self.headers)],
        )

        response = requests.get(self.url, headers=self.headers, auth=self.auth, verify=False)
        
        # Print actual response for debugging
        print(f"Received status code: {response.status_code}")
        print(f"Response body: {response.json()}")

        self.assertEqual(
            response.status_code, 
            200, 
            f"Expected status 200 but got {response.status_code}. Response body: {response.text}"
        )


    @responses.activate
    def test_pingcentral_environment_endpoints_exist(self):
        """Test that paTokenEndpoint and pfTokenEndpoint exist and match expected values"""

        response = requests.get(self.url, headers=self.headers, auth=self.auth, verify=False)

        # Print actual response for debugging
        print(f"Received status code: {response.status_code}")
        print(f"Response body: {response.json()}")

        self.assertEqual(response.status_code, 200, "Failed to retrieve environments")

        data = response.json()

        try:
            # Extract pfTokenEndpoint and paTokenEndpoint dynamically from the first item
            pf_token_endpoint = data["items"][0].get("pfHost")
            pa_token_endpoint = data["items"][0].get("paHost")

            # Print extracted values for debugging
            print(f"Extracted pfTokenEndpoint: {pf_token_endpoint}")
            print(f"Extracted paTokenEndpoint: {pa_token_endpoint}")

            # Assertions to ensure these values exist and are not empty
            self.assertTrue(pf_token_endpoint, "pfTokenEndpoint is missing or empty")
            self.assertTrue(pa_token_endpoint, "paTokenEndpoint is missing or empty")

            # Assert values match expected environment variables
            self.assertEqual(pf_token_endpoint, pfHost, f"Expected pfTokenEndpoint to be {pfHost} but got {pf_token_endpoint}")
            self.assertEqual(pa_token_endpoint, paHost, f"Expected paTokenEndpoint to be {paHost} but got {pa_token_endpoint}")

        except (KeyError, IndexError) as e:
            self.fail(f"Missing expected key or data in response JSON: {e}")

if __name__ == "__main__":
    unittest.main()
