import unittest
import logging
from k8s_utils import K8sUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"
    pipeline_patterns = ["logstash-pipeline-customer"]
    required_plugins = [
        "logstash-filter-opensearch-manticore", "logstash-input-opensearch",
        "logstash-output-awslogs", "logstash-output-newrelic",
        "logstash-output-opensearch", "logstash-output-syslog"
    ]

    @classmethod
    def setUpClass(cls):
        cls.k8s_utils = K8sUtils()
        cls.core_client = cls.k8s_utils.core_client
        pod_list = cls.core_client.list_namespaced_pod(namespace=cls.namespace)
        cls.logstash_pods = [pod.metadata.name for pod in pod_list.items if "logstash" in pod.metadata.name]
        if not cls.logstash_pods:
            raise RuntimeError("No Logstash pods found in the namespace.")
        logging.info(f"Detected Logstash pods: {', '.join(cls.logstash_pods)}")

    def test_logstash_pods_status(self):
        logging.info("Checking Logstash pod status...")
        for pod_name in self.logstash_pods:
            command = [
                "kubectl", "get", "pod", pod_name, "-n", self.namespace,
                "-o", "jsonpath={.status.phase}"
            ]
            status = self.k8s_utils.exec_command(pod_name, self.namespace, command)
            logging.info(f"Pod '{pod_name}' status: {status}")
            self.assertEqual(status, "Running", f"Pod '{pod_name}' is not running.")

    def test_logstash_container_status(self):
        logging.info("Checking Logstash container status...")
        for pod_name in self.logstash_pods:
            command = [
                "kubectl", "get", "pod", pod_name, "-n", self.namespace,
                "-o", "jsonpath={.status.containerStatuses[?(@.name=='logstash')].state}"
            ]
            container_state = self.k8s_utils.exec_command(pod_name, self.namespace, command)
            logging.info(f"Container 'logstash' in pod '{pod_name}' state: {container_state}")
            self.assertIn("running", container_state.lower(), f"Container 'logstash' in pod '{pod_name}' is not running.")

    def test_plugins_existence(self):
        logging.info("Checking required plugins in Logstash...")
        for pod_name in self.logstash_pods:
            command = ["curl", "-s", "http://localhost:9600/_node/plugins?pretty"]
            plugin_data = self.k8s_utils.exec_command(pod_name, self.namespace, command)
            logging.info(f"Plugins in pod '{pod_name}': {plugin_data}")
            missing_plugins = [plugin for plugin in self.required_plugins if plugin not in plugin_data]
            self.assertFalse(missing_plugins, f"Missing plugins in pod '{pod_name}': {', '.join(missing_plugins)}")

    def test_logstash_pipeline_verification(self):
        logging.info("Checking Logstash pipelines...")
        for pod_name in self.logstash_pods:
            command = ["curl", "-s", "http://localhost:9600/_node/pipelines?pretty"]
            pipeline_data = self.k8s_utils.exec_command(pod_name, self.namespace, command)
            logging.info(f"Pipelines in pod '{pod_name}': {pipeline_data}")
            missing_pipelines = [pattern for pattern in self.pipeline_patterns if pattern not in pipeline_data]
            self.assertFalse(missing_pipelines, f"Missing pipelines in pod '{pod_name}': {', '.join(missing_pipelines)}")

    def test_customer_pipeline_status(self):
        logging.info("Checking customer pipeline status...")
        for pod_name in self.logstash_pods:
            command = ["curl", "-s", "http://localhost:9600/_node/stats/pipelines/customer?pretty"]
            pipeline_data = self.k8s_utils.exec_command(pod_name, self.namespace, command)
            status = next((line for line in pipeline_data.splitlines() if '"status"' in line), None)
            logging.info(f"Customer pipeline status in pod '{pod_name}': {status}")
            self.assertIsNotNone(status, f"Customer pipeline status not found in pod '{pod_name}'.")

if __name__ == '__main__':
    unittest.main()
