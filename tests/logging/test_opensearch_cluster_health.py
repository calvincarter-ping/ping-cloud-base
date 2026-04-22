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


class TestOpenSearchClusterHealth(unittest.TestCase):
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
        cls.port_forward_process = subprocess.Popen(
            ["kubectl", "port-forward", "service/opensearch-cluster-headless", "9200:9200",
             "-n", "elastic-stack-logging"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
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
            ssl_show_warn=False,
            timeout=240
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

    def test_cluster_health_status(self):
        # Check the health status of the cluster
        deadline = time.time() + OPENSEARCH_ASSERT_TIMEOUT_SECONDS
        while time.time() < deadline:
            health = self.opensearch_client.cluster.health()
            cluster_status = health.get('status', 'unknown')
            print(f"Cluster health status: {cluster_status}")
            if cluster_status == "green":
                return
            time.sleep(OPENSEARCH_ASSERT_INTERVAL_SECONDS)
        self.fail(f"Cluster status is not green within timeout: {cluster_status}")


    def test_logstash_pods_and_bootstrap_index(self):
        print("Checking if Logstash pods are running...")
        self.k8s.wait_for_pod_running(
            label="app=logstash-elastic", namespace="elastic-stack-logging")

        deadline = time.time() + OPENSEARCH_ASSERT_TIMEOUT_SECONDS
        while time.time() < deadline:
            exists = self.opensearch_client.indices.exists(index="bootstrap-status")
            print(f"bootstrap-status index exists: {exists}")
            if exists:
                return
            time.sleep(OPENSEARCH_ASSERT_INTERVAL_SECONDS)

        self.fail("bootstrap-status index does not exist in OpenSearch while logstash pod is running")

if __name__ == '__main__':
    unittest.main()
