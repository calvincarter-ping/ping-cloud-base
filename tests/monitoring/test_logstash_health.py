import unittest
import subprocess
import json

class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"

    @classmethod
    def setUpClass(cls):
        cls.logstash_pods = [
            "logstash-elastic-0",
            "logstash-elastic-1",
        ]

    def run_command(self, command):
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            self.fail(f"Command failed: {command}\nError: {result.stderr}")
        return result.stdout.strip()

    def test_logstash_pods_status(self):
        for pod in self.logstash_pods:
            command = f"kubectl get pod {pod} -n {self.namespace} -o jsonpath='{{.status.phase}}'"
            output = self.run_command(command)
            self.assertEqual(output, "Running", f"Pod {pod} is not in Running state")

    def test_logstash_container_status(self):
        for pod in self.logstash_pods:
            command = f"kubectl get pod {pod} -n {self.namespace} -o jsonpath='{{range .status.containerStatuses[?(@.name==\"logstash\")].state}}{json .running}{{end}}'"
            output = self.run_command(command)
            self.assertIn("startedAt", output, f"Container 'logstash' in pod {pod} is not running")

    def test_customer_pipeline_exists(self):
        for pod in self.logstash_pods:
            command = f"kubectl exec -n {self.namespace} {pod} -- curl -s http://localhost:9600/_node/pipelines?pretty | grep customer"
            output = self.run_command(command)
            self.assertIn("customer", output, f"Customer pipeline not found in pod {pod}")

    def test_customer_pipeline_status(self):
        for pod in self.logstash_pods:
            command = f"kubectl exec -n {self.namespace} {pod} -- curl -s http://localhost:9600/_node/stats/pipelines/customer?pretty | grep '\"status\"'"
            output = self.run_command(command)
            self.assertIn("green", output, f"Customer pipeline in pod {pod} is not healthy")

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
            command = f"kubectl exec -n {self.namespace} {pod} -- curl -s http://localhost:9600/_node/plugins?pretty"
            output = self.run_command(command)
            plugins = [plugin["name"] for plugin in json.loads(output).get("plugins", [])]
            missing_plugins = [plugin for plugin in required_plugins if plugin not in plugins]
            self.assertFalse(missing_plugins, f"Missing plugins in pod {pod}: {', '.join(missing_plugins)}")


if __name__ == "__main__":
    unittest.main()
