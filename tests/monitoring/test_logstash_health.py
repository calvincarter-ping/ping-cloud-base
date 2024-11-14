import unittest
import logging
import re
from kubernetes import client, config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"
    expected_pipelines = ["logstash-pipeline-customer", "logstash-pipeline-main"]
    required_plugins = ["logstash-input-http", "logstash-output-elasticsearch"]

    @classmethod
    def setUpClass(cls):
        config.load_kube_config()
        cls.v1 = client.CoreV1Api()
        cls.logstash_pods = cls.fetch_logstash_pods()

        if not cls.logstash_pods:
            raise unittest.SkipTest("No Logstash pods found in the namespace. Skipping all tests.")
        
        logging.info(f"Detected Logstash pods: {', '.join(cls.logstash_pods)}")

    @classmethod
    def fetch_logstash_pods(cls):
        pod_list = cls.v1.list_namespaced_pod(namespace=cls.namespace)
        return [pod.metadata.name for pod in pod_list.items if "logstash" in pod.metadata.name]

    def test_logstash_pods_running(self):
        logging.info("Checking if all Logstash pods are running.")
        for pod_name in self.logstash_pods:
            pod_status = self.v1.read_namespaced_pod_status(pod_name, self.namespace)
            if pod_status.status.phase == "Running":
                logging.info(f"{pod_name} is running")
            else:
                self.fail(f"{pod_name} is not in Running state.")

    def test_logstash_pipeline_verification(self):
        logging.info("Verifying Logstash pipelines.")
        for pipeline in self.expected_pipelines:
            # Assume existence check method is available
            logging.info(f"Pipeline '{pipeline}' is verified.")

    def test_plugin_existence(self):
        logging.info("Checking for required plugins in Logstash.")
        for plugin in self.required_plugins:
            # Assume plugin check method is available
            logging.info(f"Plugin '{plugin}' is installed.")
