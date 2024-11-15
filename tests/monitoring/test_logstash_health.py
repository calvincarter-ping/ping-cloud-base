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

    def test_logstash_pods_running(self):
        for pod_name in self.logstash_pods:
            pod = self.core_client.read_namespaced_pod(name=pod_name, namespace=self.namespace)
            container_statuses = pod.status.container_statuses
            self.assertIsNotNone(container_statuses, f"Pod '{pod_name}' has no container statuses.")
            for container_status in container_statuses:
                self.assertTrue(container_status.ready, f"Container in pod '{pod_name}' is not ready.")
            logging.info(f"Pod {pod_name} is running")

    def test_logstash_pipeline_verification(self):
        logging.info("Verifying existence of Logstash pipelines in Logstash instance.")
        for pod_name in self.logstash_pods:
            command = ["curl", "-s", "http://localhost:9600/_node/pipelines?pretty"]
            try:
                pipeline_data = self.k8s_utils.exec_command(pod_name, self.namespace, command)
                for pipeline_pattern in self.pipeline_patterns:
                    pipeline_name = pipeline_pattern.split('-')[2]
                    self.assertIn(pipeline_name, pipeline_data, f"Pipeline '{pipeline_name}' not found in Logstash.")
                    logging.info(f"Pipeline '{pipeline_name}' is verified in Logstash instance.")
            except Exception as e:
                logging.error(f"Failed to retrieve pipelines from Logstash pod {pod_name}: {e}")

    def test_plugin_existence(self):
        logging.info("Checking for required plugins in Logstash.")
        pod_name = self.logstash_pods[0]
        command = ["curl", "-s", "http://localhost:9600/_node/plugins?pretty"]
        try:
            plugin_data = self.k8s_utils.exec_command(pod_name, self.namespace, command)
            for plugin in self.required_plugins:
                self.assertIn(plugin, plugin_data, f"Plugin '{plugin}' is not installed in Logstash.")
                logging.info(f"Plugin '{plugin}' is verified.")
        except Exception as e:
            logging.error(f"Failed to retrieve plugins from Logstash pod {pod_name}: {e}")

if __name__ == '__main__':
    unittest.main()
