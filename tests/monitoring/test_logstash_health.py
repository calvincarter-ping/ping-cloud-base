import unittest
import logging
from kubernetes import client, config
import subprocess

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"
    container_name = "logstash"
    required_plugins = [
        "logstash-filter-opensearch-manticore",
        "logstash-input-opensearch",
        "logstash-output-awslogs",
        "logstash-output-newrelic",
        "logstash-output-opensearch",
        "logstash-output-syslog"
    ]

    @classmethod
    def setUpClass(cls):
        config.load_kube_config()  # Ensure that the Kubernetes config is loaded
        cls.core_client = client.CoreV1Api()
        pod_list = cls.core_client.list_namespaced_pod(namespace=cls.namespace)
        cls.logstash_pods = [pod.metadata.name for pod in pod_list.items if "logstash-elastic" in pod.metadata.name]
        if not cls.logstash_pods:
            raise RuntimeError("No Logstash pods found in the namespace.")
        logging.info(f"Detected Logstash pods: {', '.join(cls.logstash_pods)}")

    def kubectl_exec(self, pod_name, command):
        """Helper method to execute commands in the pod"""
        result = subprocess.run(
            ["kubectl", "exec", "-it", pod_name, "-n", self.namespace, "--"] + command,
            capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to execute command: {result.stderr}")
        return result.stdout.strip()

    def test_logstash_pods_status(self):
        """Check if Logstash pods are in Running state."""
        for pod_name in self.logstash_pods:
            command = ["kubectl", "get", "pods", "-n", self.namespace, "-o", "jsonpath='{.status.phase}'"]
            status = self.kubectl_exec(pod_name, command)
            logging.info(f"Pod '{pod_name}' status: {status}")
            self.assertEqual(status, "Running", f"Pod '{pod_name}' is not running.")

    def test_logstash_container_status(self):
        """Check if Logstash container in each pod is running."""
        for pod_name in self.logstash_pods:
            command = [
                "kubectl", "get", "pod", pod_name, "-n", self.namespace, "-o", "jsonpath='{.status.containerStatuses[?(@.name==\"logstash\")].state.running}'"
            ]
            state = self.kubectl_exec(pod_name, command)
            logging.info(f"Container '{self.container_name}' in pod '{pod_name}' state: {state}")
            self.assertEqual(state, "true", f"Container '{self.container_name}' in pod '{pod_name}' is not running.")

    def test_customer_pipeline_exists(self):
        """Verify if the customer pipeline exists."""
        for pod_name in self.logstash_pods:
            command = ["curl", "-s", "http://localhost:9600/_node/pipelines?pretty"]
            pipeline_data = self.kubectl_exec(pod_name, command)
            logging.info(f"Customer pipeline existence in pod '{pod_name}': {pipeline_data}")
            self.assertIn("customer", pipeline_data, f"Customer pipeline not found in pod '{pod_name}'.")

    def test_customer_pipeline_status(self):
        """Check the health status of the customer pipeline."""
        for pod_name in self.logstash_pods:
            command = ["curl", "-s", "http://localhost:9600/_node/stats/pipelines/customer?pretty"]
            status = self.kubectl_exec(pod_name, command)
            logging.info(f"Customer pipeline status in pod '{pod_name}': {status}")
            self.assertIn("green", status, f"Customer pipeline in pod '{pod_name}' is not in a healthy state.")

    def test_plugins_existence(self):
        """Verify the presence of required plugins."""
        for pod_name in self.logstash_pods:
            command = ["curl", "-s", "http://localhost:9600/_node/plugins?pretty"]
            plugin_data = self.kubectl_exec(pod_name, command)
            logging.info(f"Plugins in pod '{pod_name}': {plugin_data}")
            missing_plugins = [plugin for plugin in self.required_plugins if plugin not in plugin_data]
            self.assertFalse(missing_plugins, f"Missing plugins in pod '{pod_name}': {', '.join(missing_plugins)}")


if __name__ == '__main__':
    unittest.main()
