import subprocess
import unittest

class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"
    logstash_pods = []

    @classmethod
    def setUpClass(cls):
        # Correct label for Logstash pods
        command = f"kubectl get pods -n {cls.namespace} -l app=logstash-elastic -o jsonpath='{{.items[*].metadata.name}}'"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to fetch pods: {result.stderr.strip()}")

        cls.logstash_pods = result.stdout.strip().split()
        
        if not cls.logstash_pods:
            raise RuntimeError("No Logstash pods found in the namespace!")

    def test_logstash_pods_status(self):
        for pod in self.logstash_pods:
            command = f"kubectl get pod {pod} -n {self.namespace} -o jsonpath='{{.status.phase}}'"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(result.stdout.strip(), "Running", f"Pod {pod} is not running")

    def test_customer_pipeline_exists(self):
        for pod in self.logstash_pods:
            command = f"kubectl exec -n {self.namespace} {pod} -- curl -s http://localhost:9600/_node/pipelines?pretty | grep customer"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertIn("customer", result.stdout, f"Customer pipeline not found in pod {pod}")

    def test_customer_pipeline_status(self):
        for pod in self.logstash_pods:
            command = f"kubectl exec -n {self.namespace} {pod} -- curl -s http://localhost:9600/_node/stats/pipelines/customer?pretty | grep '\"status\"'"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertIn('"status" : "green"', result.stdout, f"Customer pipeline in pod {pod} is not in a healthy state")

    def test_plugins_existence(self):
        required_plugins = [
            "logstash-filter-opensearch-manticore",
            "logstash-input-opensearch",
            "logstash-output-awslogs",
            "logstash-output-newrelic",
            "logstash-output-opensearch",
            "logstash-output-syslog"
        ]
        for pod in self.logstash_pods:
            command = f"kubectl exec -n {self.namespace} {pod} -- curl -s http://localhost:9600/_node/plugins?pretty"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            plugins = [line.split(":")[1].strip().strip('"') for line in result.stdout.splitlines() if '"name"' in line]
            missing_plugins = [plugin for plugin in required_plugins if plugin not in plugins]
            self.assertFalse(missing_plugins, f"Missing plugins in pod {pod}: {', '.join(missing_plugins)}")


if __name__ == "__main__":
    unittest.main()
