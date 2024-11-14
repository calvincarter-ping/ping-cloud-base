import unittest
import logging
from kubernetes import client, config
from kubernetes.stream import stream

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"
    pipeline_configmaps = [
        "logstash-pipeline-customer-tkfmg2b5f9",
        "logstash-pipeline-main-26mmhgk2cc"
    ]
    required_plugins = ["logstash-input-http", "logstash-output-elasticsearch"]

    @classmethod
    def setUpClass(cls):
        config.load_kube_config()
        cls.v1 = client.CoreV1Api()
        cls.logstash_pods = cls.fetch_logstash_pods()

        if not cls.logstash_pods:
            message = "No Logstash pods found in the namespace. Marking test as failed."
            logging.error(message)
            raise unittest.SkipTest(message)
        
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
        logging.info("Verifying existence of Logstash pipeline ConfigMaps.")
        for configmap_name in self.pipeline_configmaps:
            try:
                config_map = self.v1.read_namespaced_config_map(configmap_name, self.namespace)
                logging.info(f"Pipeline ConfigMap '{configmap_name}' is present and verified.")
            except client.exceptions.ApiException as e:
                self.fail(f"Pipeline ConfigMap '{configmap_name}' is missing or inaccessible: {e}")

    def test_plugin_existence(self):
        logging.info("Checking for required plugins in Logstash.")
        pod_name = self.logstash_pods[0]
        command = ["bin/logstash-plugin", "list"]
        
        try:
            plugin_list = stream(self.v1.connect_get_namespaced_pod_exec,
                                 pod_name,
                                 self.namespace,
                                 container="logstash",
                                 command=command,
                                 stderr=True, stdin=False,
                                 stdout=True, tty=False)
            
            for plugin in self.required_plugins:
                self.assertIn(plugin, plugin_list, f"Plugin '{plugin}' is not installed in Logstash.")
                logging.info(f"Plugin '{plugin}' is verified.")
        except client.exceptions.ApiException as e:
            self.fail(f"Failed to execute command in Logstash pod: {e}")

if __name__ == '__main__':
    unittest.main()
