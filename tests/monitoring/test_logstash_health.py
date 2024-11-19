import unittest
from k8s_utils import K8sUtils

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
        cls.k8s_utils = K8sUtils()
        # Detect Logstash pods
        cls.logstash_pods = cls.k8s_utils.get_pod_names(cls.namespace, "app=logstash")
        if not cls.logstash_pods:
            raise RuntimeError("No Logstash pods found in the namespace!")

    def test_pod_status(self):
        """Verify if all Logstash pods are in the Running state."""
        for pod in self.logstash_pods:
            status = self.k8s_utils.get_pod_status(pod, self.namespace)
            self.assertEqual(status, "Running", f"Pod {pod} is not in Running state.")
        print("OK: All Logstash pods are in Running state.")

    def test_container_status(self):
        """Verify if the logstash container in each pod is running."""
        for pod in self.logstash_pods:
            state = self.k8s_utils.get_container_status(pod, self.namespace, "logstash")
            self.assertEqual(state, "Running", f"Container logstash in pod {pod} is not running.")
        print("OK: All Logstash containers are running.")

    def test_customer_pipeline_exists(self):
        """Verify if the customer pipeline exists."""
        for pod in self.logstash_pods:
            command = "curl -s http://localhost:9600/_node/pipelines?pretty | grep customer"
            output = self.k8s_utils.exec_command(pod, self.namespace, command)
            self.assertIn("customer", output, f"Customer pipeline not found in pod {pod}.")
        print("OK: Customer pipeline exists in all Logstash pods.")

    def test_customer_pipeline_status(self):
        """Check the health status of the customer pipeline."""
        for pod in self.logstash_pods:
            command = "curl -s http://localhost:9600/_node/stats/pipelines/customer?pretty | grep '\"status\"'"
            output = self.k8s_utils.exec_command(pod, self.namespace, command)
            self.assertIn('"status" : "green"', output, f"Customer pipeline in pod {pod} is not healthy.")
        print("OK: Customer pipeline status is green in all Logstash pods.")

    def test_plugins_existence(self):
        """Verify the presence of required plugins."""
        for pod in self.logstash_pods:
            command = "curl -s http://localhost:9600/_node/plugins?pretty"
            output = self.k8s_utils.exec_command(pod, self.namespace, command)
            for plugin in self.required_plugins:
                self.assertIn(plugin, output, f"Plugin {plugin} not found in pod {pod}.")
        print("OK: All required plugins are present in Logstash pods.")
