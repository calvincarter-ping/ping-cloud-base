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
        pods_ready = self.k8s_utils.wait_for_pod_ready("app=logstash", self.namespace)
        self.assertTrue(pods_ready, "Not all Logstash pods are ready.")
        pod_names = self.k8s_utils.get_deployment_pod_names("app=logstash", self.namespace)
        
        for pod_name in pod_names:
            pod = self.k8s_utils.core_client.read_namespaced_pod(name=pod_name, namespace=self.namespace)
            container_statuses = pod.status.container_statuses
            self.assertIsNotNone(container_statuses, f"Pod '{pod_name}' has no container statuses.")
            for container_status in container_statuses:
                self.assertTrue(container_status.ready, f"Container in pod '{pod_name}' is not ready.")
            logging.info(f"Pod {pod_name} is ready")

    def test_logstash_pods_running(self):
        self.check_logstash_pods_ready()

    def test_logstash_pipeline_verification(self):
        logging.info("Verifying existence of Logstash pipelines in Logstash instance.")
        for pod_name in self.logstash_pods:
            try:
                command = ["curl", "-s", "http://localhost:9600/_node/pipelines?pretty"]
                pipeline_data = self.k8s_utils.exec_command(pod_name, self.namespace, command)
                found_pipelines = []
                missing_pipelines = []
                for pipeline_pattern in self.pipeline_patterns:
                    if pipeline_pattern in pipeline_data:
                        found_pipelines.append(pipeline_pattern)
                        logging.info(f"Pipeline '{pipeline_pattern}' is present in pod '{pod_name}'.")
                    else:
                        missing_pipelines.append(pipeline_pattern)
                        logging.error(f"Pipeline '{pipeline_pattern}' is missing in pod '{pod_name}'.")
                if missing_pipelines:
                    self.fail(f"Missing pipelines in pod '{pod_name}': {', '.join(missing_pipelines)}")
            except Exception as e:
                logging.error(f"Failed to retrieve pipelines from Logstash pod {pod_name}: {e}")
                self.fail(f"Test failed for pod '{pod_name}'")

    def test_plugin_existence(self):
        pod_name = self.logstash_pods[0]
        logging.info(f"Verifying plugins in pod '{pod_name}'.")
        try:
            command = ["curl", "-s", "http://localhost:9600/_node/plugins?pretty"]
            plugin_data = self.k8s_utils.exec_command(pod_name, self.namespace, command)
            found_plugins = []
            missing_plugins = []
            for plugin in self.required_plugins:
                if plugin in plugin_data:
                    found_plugins.append(plugin)
                    logging.info(f"Plugin '{plugin}' is installed in pod '{pod_name}'.")
                else:
                    missing_plugins.append(plugin)
                    logging.error(f"Plugin '{plugin}' is missing in pod '{pod_name}'.")
            if missing_plugins:
                self.fail(f"Missing plugins in pod '{pod_name}': {', '.join(missing_plugins)}")
        except Exception as e:
            logging.error(f"Failed to retrieve plugins from Logstash pod {pod_name}: {e}")
            self.fail(f"Test failed for pod '{pod_name}'")

if __name__ == '__main__':
    unittest.main()
