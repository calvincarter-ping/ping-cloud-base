import subprocess
import unittest


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
        except Exception as e:
            raise RuntimeError(f"Error detecting Logstash pods: {e}")

    def test_logstash_pods_status(self):
        for pod in self.logstash_pods:
            command = f"kubectl get pod {pod} -n {self.namespace} -o jsonpath='{{.status.phase}}'"
            status = subprocess.check_output(command, shell=True, text=True).strip()
            self.assertEqual(status, "Running", f"Pod {pod} is not in Running state.")

    def test_logstash_container_status(self):
        for pod in self.logstash_pods:
            command = f"kubectl get pod {pod} -n {self.namespace} -o jsonpath='{{range .status.containerStatuses[?(@.name==\"logstash\")]}}{{.state.running}}{{end}}'"
            container_state = subprocess.check_output(command, shell=True, text=True).strip()
            self.assertIn("startedAt", container_state, f"Container 'logstash' in pod {pod} is not running.")

    def test_customer_pipeline_exists(self):
        for pod in self.logstash_pods:
            command = f"kubectl exec {pod} -n {self.namespace} -- curl -s http://localhost:9600/_node/pipelines?pretty | grep customer"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(result.returncode, 0, f"Customer pipeline not found in pod {pod}.")

    def test_customer_pipeline_status(self):
        for pod in self.logstash_pods:
            command = f"kubectl exec {pod} -n {self.namespace} -- curl -s http://localhost:9600/_node/stats/pipelines/customer?pretty | grep '\"status\"'"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertIn('"status" : "green"', result.stdout, f"Customer pipeline in pod {pod} is not in a healthy state.")

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
            command = f"kubectl exec {pod} -n {self.namespace} -- curl -s http://localhost:9600/_node/plugins?pretty"
            plugins_output = subprocess.check_output(command, shell=True, text=True)
            installed_plugins = [plugin.strip() for plugin in plugins_output.splitlines() if plugin.strip()]
            missing_plugins = [plugin for plugin in required_plugins if plugin not in installed_plugins]
            self.assertFalse(missing_plugins, f"Missing plugins in pod {pod}: {', '.join(missing_plugins)}")


if __name__ == "__main__":
    unittest.main()
