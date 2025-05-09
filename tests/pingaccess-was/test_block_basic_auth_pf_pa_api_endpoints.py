import os
import unittest
import urllib3
import requests
from requests.auth import HTTPBasicAuth

# The following conditions don't really matter for this test:
# 1) Username / Password
# 2) Including header: 'x-xsrf-header: PingFederate' or 'x-xsrf-header: PingAccess' which is mandator by PF and PA API.
# The reason being is PingAccess-WAS will be blocking the request before it ever gets to PingFederate or PingAccess
USERNAME = "fakeadmin"
PASSWORD = "test123"

# ── Mandatory environment variables for this test
PA_ADMIN_HOST = os.environ["PA_ADMIN_PUBLIC_HOSTNAME"]   # Use os.environ to purposely get KeyError in unittest if not set
PF_ADMIN_HOST = os.environ["PF_ADMIN_PUBLIC_HOSTNAME"]

# Any PingAccess and PingFederate API endpoints are fine.
API_TARGETS = [f"https://{PA_ADMIN_HOST}/pa-admin-api/v3/rules", f"https://{PF_ADMIN_HOST}/pf-admin-api/v1/keyPairs"]

SOME_SNIPPET_OF_PAWAS_HTML_ERROR_PAGE = "<p>The requested URL was not found on this server.</p>"

class TestItem404(unittest.TestCase):
    """Verify each API endpoint returns a 404 and the expected HTML."""

    @classmethod
    def setUpClass(cls):
        # Disable only InsecureRequestWarning warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def test_item_endpoints_return_404(self):

        # Build Basic Auth HTTP
        auth = HTTPBasicAuth(USERNAME, PASSWORD)

        for url in API_TARGETS:
            url = url.strip()  # in case spaces sneak in
            with self.subTest(url=url):
                resp = requests.get(url, auth=auth, timeout=10, verify=False)

                # 1) Verify PA-WAS presented 404 status code
                self.assertEqual(
                    resp.status_code, 404,
                    f"{url} should return HTTP 404"
                )

                # 2) Verify PA-WAS html page contained small error snippet
                self.assertIn(
                    SOME_SNIPPET_OF_PAWAS_HTML_ERROR_PAGE, resp.text,
                    f"{url} should contain the 404 paragraph"
                )


if __name__ == "__main__":
    unittest.main()