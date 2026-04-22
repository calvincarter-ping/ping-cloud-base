import re
import unittest
import subprocess
import time
import base64
import requests
import urllib3
from opensearchpy import OpenSearch
from k8s_utils import K8sUtils

PORT_FORWARD_READY_TIMEOUT_SECONDS = 20
REQUEST_TIMEOUT_SECONDS = 2
OPENSEARCH_ASSERT_TIMEOUT_SECONDS = 60
OPENSEARCH_ASSERT_INTERVAL_SECONDS = 5


class TestOpenSearchLogs(unittest.TestCase):
    @classmethod
    def wait_for_opensearch_port_forward(cls, username, password):
        deadline = time.time() + PORT_FORWARD_READY_TIMEOUT_SECONDS
        while time.time() < deadline:
            if cls.port_forward_process.poll() is not None:
                raise Exception("Port-forward failed. Exiting test.")
            try:
                response = requests.get(
                    "https://localhost:9200",
                    verify=False,
                    auth=(username, password),
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                if response.status_code == 200:
                    print("Port-forward established successfully.")
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)

        raise Exception("Timed out waiting for OpenSearch port-forward.")

    @classmethod
    def setUpClass(cls):
        cls.k8s = K8sUtils()
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # Port-forward the OpenSearch service (opensearch-cluster-headless)
        cls.port_forward_process = subprocess.Popen(
            ["kubectl", "port-forward", "service/opensearch-cluster-headless", "9200:9200", 
             "-n", "elastic-stack-logging"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        # Get OpenSearch Admin user/password from the secret in the 'opensearch-admin-credentials' secret
        opensearch_creds_secret = cls.k8s.get_namespaced_secret(
            "opensearch-admin-credentials", "elastic-stack-logging"
        )
        username = base64.b64decode(opensearch_creds_secret.data['username']).decode('utf-8')
        password = base64.b64decode(opensearch_creds_secret.data['password']).decode('utf-8')
        print(username, password)
        cls.wait_for_opensearch_port_forward(username, password)
        # Create OpenSearch client
        cls.opensearch_client = OpenSearch(
            hosts=[{'host': 'localhost', 'port': 9200}],
            http_auth=(username, password),
            use_ssl=True, 
            verify_certs=False,
            ssl_show_warn = False,
            timeout=240 # in seconds
        )
        print("OpenSearch client created")

    @classmethod
    def tearDownClass(cls):
        # Terminate the port-forward process after the test suite runs
        cls.port_forward_process.terminate()
        try:
            cls.port_forward_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.port_forward_process.kill()
            cls.port_forward_process.wait(timeout=5)

    def test_fluentbit_ingestion_field_timestamp(self):
        # Search logs in OpenSearch index template
        index_name = "logstash-*"  
        query = {
            "query": {
                "match_all": {}
            },
            "_source": ["fluentbit_ingest_timestamp"]
        }
        response = None
        deadline = time.time() + OPENSEARCH_ASSERT_TIMEOUT_SECONDS
        while time.time() < deadline:
            response = self.opensearch_client.search(index=index_name, body=query)
            if response['hits']['hits']:
                break
            time.sleep(OPENSEARCH_ASSERT_INTERVAL_SECONDS)

        self.assertTrue(response and response['hits']['hits'], "No log documents found in OpenSearch within timeout")

        # Verify that the fluentbit_ingestion_field has a time in milliseconds
        for hit in response['hits']['hits']:
            timestamp_field = hit['_source'].get('fluentbit_ingest_timestamp')
            self.assertIsNotNone(timestamp_field, "fluentbit_ingest_timestamp is missing")
             # Validate timestamp format matches (YYYY-MM-DDTHH:MM:SS.SSSSSSSSSZ)
             # Note milliseconds might be in range of 1-9 digits
            timestamp_regex = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,9}Z$'
            match = re.match(timestamp_regex, timestamp_field)
            self.assertIsNotNone(match,
                f"fluentbit_ingestion_field is not a valid timestamp: {timestamp_field}"
            )
if __name__ == '__main__':
    unittest.main()
