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

    def check_logstash_pods_ready(self):
        all_pods_ready = True
        for pod_name in self.logstash_pods:
            pod = self.k8s_utils.core_client.read_namespaced_pod(name=pod_name, namespace=self.namespace)
            container_statuses = pod.status.container_statuses
            if not container_statuses or not all(cs.ready for cs in container_statuses):
                all_pods_ready = False
                logging.error(f"Pod '{pod_name}' is not ready.")
            else:
                logging.info(f"Pod '{pod_name}' is ready.")
        self.assertTrue(all_pods_ready, "Not all Logstash pods are ready.")

    def test_logstash_pods_running(self):
        self.check_logstash_pods_ready()

    def test_logstash_pipeline_verification(self):
        logging.info("Verifying existence of Logstash pipelines in Logstash instance.")
        for pod_name in self.logstash_pods:
            command = ["curl", "-s", "http://localhost:9600/_node/pipelines?pretty"]
            try:
                pipeline_data = self.k8s_utils.exec_command(pod_name, self.namespace, command)
                missing_pipelines = []
                for pipeline_pattern in self.pipeline_patterns:
                    if pipeline_pattern not in pipeline_data:
                        missing_pipelines.append(pipeline_pattern)
                        logging.error(f"Pipeline '{pipeline_pattern}' is missing in pod '{pod_name}'.")
                    else:
                        logging.info(f"Pipeline '{pipeline_pattern}' is present in pod '{pod_name}'.")
                if missing_pipelines:
                    self.fail(f"Missing pipelines in pod '{pod_name}': {', '.join(missing_pipelines)}")
            except Exception as e:
                logging.error(f"Failed to retrieve pipelines from Logstash pod {pod_name}: {e}")
                self.fail(f"Test failed for pod '{pod_name}'")

    def test_plugin_existence(self):
        logging.info("Checking for required plugins in Logstash.")
        all_pods_checked = True
        for pod_name in self.logstash_pods:
            command = ["curl", "-s", "http://localhost:9600/_node/plugins?pretty"]
            try:
                plugin_data = self.k8s_utils.exec_command(pod_name, self.namespace, command)
                missing_plugins = []
                for plugin in self.required_plugins:
                    if plugin not in plugin_data:
                        missing_plugins.append(plugin)
                        logging.error(f"Plugin '{plugin}' is missing in pod '{pod_name}'.")
                    else:
                        logging.info(f"Plugin '{plugin}' is present in pod '{pod_name}'.")
                if missing_plugins:
                    all_pods_checked = False
                    self.fail(f"Missing plugins in pod '{pod_name}': {', '.join(missing_plugins)}")
            except Exception as e:
                logging.error(f"Failed to retrieve plugins from Logstash pod {pod_name}: {e}")
                self.fail(f"Test failed for pod '{pod_name}'")
        self.assertTrue(all_pods_checked, "Plugins check failed for one or more pods.")

if __name__ == '__main__':
    unittest.main()
