import subprocess
import unittest
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"
    logstash_pods = []

    @classmethod
    def setUpClass(cls):
        try:
            command = f"kubectl get pods -n {cls.namespace} -o jsonpath='{{.items[?(@.metadata.labels.app==\"logstash-elastic\")].metadata.name}}'"
            result = subprocess.check_output(command, shell=True, text=True).strip()
            cls.logstash_pods = result.split()
            if not cls.logstash_pods:
                raise RuntimeError("No Logstash pods found in the namespace!")
            logger.info(f"Detected Logstash pods: {', '.join(cls.logstash_pods)}")
        except Exception as e:
            logger.error(f"Error detecting Logstash pods: {e}")
            raise

    def test_logstash_pods_status(self):
        for pod in self.logstash_pods:
            logger.info(f"Checking status of pod: {pod}")
            command = f"kubectl get pod {pod} -n {self.namespace} -o jsonpath='{{.status.phase}}'"
            status = subprocess.check_output(command, shell=True, text=True).strip()
            self.assertEqual(status, "Running", f"Pod {pod} is not in Running state.")
            logger.info(f"Pod {pod} is in Running state.")

    def test_logstash_container_status(self):
        for pod in self.logstash_pods:
            logger.info(f"Checking container status in pod: {pod}")
            command = f"kubectl get pod {pod} -n {self.namespace} -o jsonpath='{{range .status.containerStatuses[?(@.name==\"logstash\")]}}{{.state.running}}{{end}}'"
            container_state = subprocess.check_output(command, shell=True, text=True).strip()
            self.assertIn("startedAt", container_state, f"Container 'logstash' in pod {pod} is not running.")
            logger.info(f"Container 'logstash' in pod {pod} is running.")

    def test_customer_pipeline_exists(self):
        for pod in self.logstash_pods:
            logger.info(f"Verifying customer pipeline existence in pod: {pod}")
            command = f"kubectl exec {pod} -n {self.namespace} -- curl -s http://localhost:9600/_node/pipelines?pretty | grep customer"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(result.returncode, 0, f"Customer pipeline not found in pod {pod}.")
            logger.info(f"Customer pipeline exists in pod {pod}.")

    def test_customer_pipeline_status(self):
        for pod in self.logstash_pods:
            logger.info(f"Checking customer pipeline status in pod: {pod}")
            command = f"kubectl exec {pod} -n {self.namespace} -- curl -s http://localhost:9600/_node/stats/pipelines/customer?pretty | grep '\"status\"'"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertIn('"status" : "green"', result.stdout, f"Customer pipeline in pod {pod} is not in a healthy state.")
            logger.info(f"Customer pipeline in pod {pod} is in a healthy state.")

    def test_plugins_existence(self):
        required_plugins = [
            "logstash-filter-opensearch-manticore",
            "logstash-input-opensearch",
            "logstash-output-awslogs",
            "logstash-output-newrelic",
            "logstash-output-opensearch",
            "logstash-output-syslog",
        ]
        for pod in self.logstash_pods:
            logger.info(f"Verifying plugins in pod: {pod}")
            command = f"kubectl exec {pod} -n {self.namespace} -- curl -s http://localhost:9600/_node/plugins?pretty"
            plugins_output = subprocess.check_output(command, shell=True, text=True)
            installed_plugins = [plugin.strip() for plugin in plugins_output.splitlines() if plugin.strip()]
            missing_plugins = [plugin for plugin in required_plugins if plugin not in installed_plugins]
            self.assertFalse(missing_plugins, f"Missing plugins in pod {pod}: {', '.join(missing_plugins)}")
            logger.info(f"All required plugins are present in pod {pod}.")

if __name__ == "__main__":
    unittest.main()
