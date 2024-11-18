import unittest
import logging
from k8s_utils import K8sUtils

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
    logstash_pods = ["logstash-elastic-0", "logstash-elastic-1"]

    @classmethod
    def setUpClass(cls):
        cls.k8s_utils = K8sUtils()
        logging.info(f"Detected Logstash pods: {', '.join(cls.logstash_pods)}")

    def execute_command(self, pod_name, command):
        try:
            output = self.k8s_utils.exec_command(pod_name, self.namespace, command)
            logging.info(f"Executed command in pod '{pod_name}': {command}")
            logging.info(f"Command output: {output.strip()}")
            return output.strip()
        except Exception as e:
            logging.error(f"Failed to execute command in pod '{pod_name}': {e}")
            return ""

    def test_logstash_pods_status(self):
        logging.info("Checking Logstash pod statuses...")
        for pod_name in self.logstash_pods:
            command = (
                f"kubectl get pod {pod_name} -n {self.namespace} -o jsonpath='{{.status.phase}}'"
            )
            status = self.execute_command(pod_name, command)
            self.assertEqual(status, "Running", f"Pod '{pod_name}' is not running.")
            logging.info(f"Pod '{pod_name}' status: {status}")

    def test_logstash_container_status(self):
        logging.info("Checking Logstash container readiness...")
        for pod_name in self.logstash_pods:
            command = (
                f"kubectl get pod {pod_name} -n {self.namespace} -o jsonpath='{{range .status.containerStatuses[?(@.name==\"{self.container_name}\")]}}{{.state.running}}{{end}}'"
            )
            state = self.execute_command(pod_name, command)
            self.assertEqual(state, "true", f"Container '{self.container_name}' in pod '{pod_name}' is not running.")
            logging.info(f"Container '{self.container_name}' in pod '{pod_name}' is running.")

    def test_customer_pipeline_exists(self):
        logging.info("Checking if customer pipeline exists...")
        for pod_name in self.logstash_pods:
            command = f"curl -s http://localhost:9600/_node/pipelines?pretty | grep customer"
            pipeline_data = self.execute_command(pod_name, command)
            self.assertIn("customer", pipeline_data, f"Customer pipeline not found in pod '{pod_name}'.")
            logging.info(f"Customer pipeline existence in pod '{pod_name}': {pipeline_data}")

    def test_customer_pipeline_status(self):
        logging.info("Checking customer pipeline status...")
        for pod_name in self.logstash_pods:
            command = f"curl -s http://localhost:9600/_node/stats/pipelines/customer?pretty | grep '\"status\"'"
            status = self.execute_command(pod_name, command)
            self.assertIn("green", status, f"Customer pipeline in pod '{pod_name}' is not in a healthy state.")
            logging.info(f"Customer pipeline status in pod '{pod_name}': {status}")

    def test_plugins_existence(self):
        logging.info("Checking required plugins in Logstash...")
        for pod_name in self.logstash_pods:
            command = f"curl -s http://localhost:9600/_node/plugins?pretty"
            plugin_data = self.execute_command(pod_name, command)
            missing_plugins = [plugin for plugin in self.required_plugins if plugin not in plugin_data]
            self.assertFalse(missing_plugins, f"Missing plugins in pod '{pod_name}': {', '.join(missing_plugins)}")
            logging.info(f"Plugins in pod '{pod_name}': {plugin_data}")


if __name__ == '__main__':
    unittest.main()
