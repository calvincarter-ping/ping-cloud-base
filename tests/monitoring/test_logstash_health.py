import unittest
import subprocess


class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"
    logstash_pods = []
    required_plugins = [
        "logstash-filter-opensearch-manticore",
        "logstash-input-opensearch",
        "logstash-output-awslogs",
        "logstash-output-newrelic",
        "logstash-output-opensearch",
        "logstash-output-syslog",
    ]

    @classmethod
    def setUpClass(cls):
        # Get all pod names with label selector for Logstash
        command = f"kubectl get pods -n {cls.namespace} -l app=logstash -o jsonpath='{{.items[*].metadata.name}}'"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Error fetching pods: {result.stderr.strip()}")
        cls.logstash_pods = result.stdout.strip().split()
        if not cls.logstash_pods:
            raise RuntimeError("No Logstash pods found in the namespace!")

    def test_pod_status(self):
        """Verify if all Logstash pods are in the Running state."""
        for pod in self.logstash_pods:
            command = f"kubectl get pod {pod} -n {self.namespace} -o jsonpath='{{.status.phase}}'"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(result.returncode, 0, f"Error checking pod status: {result.stderr.strip()}")
            self.assertEqual(result.stdout.strip(), "Running", f"Pod {pod} is not in Running state.")
        print("OK: All Logstash pods are in Running state.")

    def test_container_status(self):
        """Verify if the Logstash container in each pod is running."""
        for pod in self.logstash_pods:
            command = (
                f"kubectl get pod {pod} -n {self.namespace} "
                f"-o jsonpath='{{.status.containerStatuses[?(@.name==\"logstash\")].state.running}}'"
            )
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(result.returncode, 0, f"Error checking container status: {result.stderr.strip()}")
            self.assertTrue(result.stdout.strip(), f"Container logstash in pod {pod} is not running.")
        print("OK: All Logstash containers are running.")

    def test_customer_pipeline_exists(self):
        """Verify if the customer pipeline exists."""
        for pod in self.logstash_pods:
            command = f"kubectl exec -n {self.namespace} {pod} -- curl -s http://localhost:9600/_node/pipelines?pretty | grep customer"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(result.returncode, 0, f"Customer pipeline not found in pod {pod}.")
        print("OK: Customer pipeline exists in all pods.")

    def test_customer_pipeline_status(self):
        """Check the health status of the customer pipeline."""
        for pod in self.logstash_pods:
            command = f"kubectl exec -n {self.namespace} {pod} -- curl -s http://localhost:9600/_node/stats/pipelines/customer?pretty | grep '\"status\"'"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(result.returncode, 0, f"Customer pipeline status is not green in pod {pod}.")
            self.assertIn('"status" : "green"', result.stdout, f"Customer pipeline in pod {pod} is not healthy.")
        print("OK: Customer pipeline is healthy in all pods.")

    def test_plugins_existence(self):
        """Verify the presence of required plugins."""
        for pod in self.logstash_pods:
            command = f"kubectl exec -n {self.namespace} {pod} -- curl -s http://localhost:9600/_node/plugins?pretty"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(result.returncode, 0, f"Error fetching plugins from pod {pod}: {result.stderr.strip()}")
            for plugin in self.required_plugins:
                self.assertIn(plugin, result.stdout, f"Plugin {plugin} not found in pod {pod}.")
        print("OK: All required plugins are present in all pods.")


if __name__ == "__main__":
    unittest.main()
