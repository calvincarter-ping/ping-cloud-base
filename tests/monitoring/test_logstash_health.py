import unittest
import logging
from k8s_utils import K8sUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"
    container_name = "logstash"
    logstash_pods = ["logstash-elastic-0", "logstash-elastic-1"]
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
        cls.k8s_utils = K8sUtils()
        logging.info(f"Detected Logstash pods: {', '.join(cls.logstash_pods)}")

    def execute_command(self, pod_name, command):
        try:
            result = self.k8s_utils.exec_command(pod_name, self.namespace, command).strip()
            logging.info(f"Executed command in pod '{pod_name}': {command}")
            return result
        except Exception as e:
            logging.error(f"Failed to execute command in pod '{pod_name}': {e}")
            return ""

    def test_logstash_pods_status(self):
        for pod_name in self.logstash_pods:
            command = f"kubectl get pods -n {self.namespace} -o jsonpath='{{range .items[?(@.metadata.name==\"{pod_name}\")]}}{{.metadata.name}}{{\" - \"}}{{.status.phase}}{{\"\\n\"}}{{end}}'"
            status = self.execute_command(pod_name, command)
            logging.info(f"Pod '{pod_name}' status: {status}")
            self.assertEqual(status.split(" - ")[-1], "Running", f"Pod '{pod_name}' is not running.")

    def test_logstash_container_status(self):
        for pod_name in self.logstash_pods:
            command = f"kubectl get pod {pod_name} -n {self.namespace} -o jsonpath='{{range .status.containerStatuses[?(@.name==\"{self.container_name}\")]}}{{.name}}{{\" - \"}}{{.state}}{{\"\\n\"}}{{end}}'"
            state = self.execute_command(pod_name, command)
            logging.info(f"Container '{self.container_name}' in pod '{pod_name}' state: {state}")
            self.assertIn("running", state.lower(), f"Container '{self.container_name}' in pod '{pod_name}' is not running.")

    def test_customer_pipeline_exists(self):
        for pod_name in self.logstash_pods:
            command = "curl -s http://localhost:9600/_node/pipelines?pretty | grep customer"
            pipeline_data = self.execute_command(pod_name, command)
            logging.info(f"Customer pipeline existence in pod '{pod_name}': {pipeline_data}")
            self.assertIn("customer", pipeline_data, f"Customer pipeline not found in pod '{pod_name}'.")

    def test_customer_pipeline_status(self):
        for pod_name in self.logstash_pods:
            command = "curl -s http://localhost:9600/_node/stats/pipelines/customer?pretty | grep '\"status\"'"
            status = self.execute_command(pod_name, command)
            logging.info(f"Customer pipeline status in pod '{pod_name}': {status}")
            self.assertIn("green", status, f"Customer pipeline in pod '{pod_name}' is not in a healthy state.")

    def test_plugins_existence(self):
        for pod_name in self.logstash_pods:
            command = "curl -s http://localhost:9600/_node/plugins?pretty"
            plugin_data = self.execute_command(pod_name, command)
            logging.info(f"Plugins in pod '{pod_name}': {plugin_data}")
            missing_plugins = [plugin for plugin in self.required_plugins if plugin not in plugin_data]
            self.assertFalse(missing_plugins, f"Missing plugins in pod '{pod_name}': {', '.join(missing_plugins)}")


if __name__ == '__main__':
    unittest.main()
