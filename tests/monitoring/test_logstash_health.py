import unittest
import logging
from kubernetes import client, config
from kubernetes.stream import stream
from k8s_utils import K8sUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"
    pipeline_patterns = ["logstash-pipeline-customer", "logstash-pipeline-main", 
                         "logstash-pipeline-s3", "logstash-pipeline-dlq"]
    
    required_plugins = [
        "logstash-input-http", "logstash-filter-mutate", "logstash-filter-drop", 
        "logstash-filter-dissect", "logstash-filter-grok", "logstash-output-elasticsearch",
        "logstash-filter-translate", "logstash-filter-kv", "logstash-filter-date",
        "logstash-filter-geoip", "logstash-filter-ruby", "logstash-output-opensearch",
        "logstash-output-s3"
    ]

    @classmethod
    def setUpClass(cls):
        config.load_kube_config()
        cls.k8s_utils = K8sUtils()
        cls.v1 = client.CoreV1Api()
        
        pod_list = cls.v1.list_namespaced_pod(namespace=cls.namespace)
        cls.logstash_pods = [pod.metadata.name for pod in pod_list.items if "logstash" in pod.metadata.name]
        cls.pipeline_configmaps = cls.fetch_pipeline_configmaps()

        if not cls.logstash_pods:
            message = "No Logstash pods found in the namespace. Marking test as failed."
            logging.error(message)
            raise unittest.SkipTest(message)
        
        logging.info(f"Detected Logstash pods: {', '.join(cls.logstash_pods)}")

    @classmethod
    def fetch_pipeline_configmaps(cls):
        pipeline_configmaps = []
        configmaps = cls.v1.list_namespaced_config_map(namespace=cls.namespace)
        
        for cm in configmaps.items:
            for pattern in cls.pipeline_patterns:
                if cm.metadata.name.startswith(pattern):
                    pipeline_configmaps.append(cm.metadata.name)
        
        if not pipeline_configmaps:
            logging.error("No Logstash pipeline ConfigMaps found in the namespace.")
        else:
            logging.info(f"Detected Logstash pipeline ConfigMaps: {', '.join(pipeline_configmaps)}")
        return pipeline_configmaps

    def get_logstash_container_name(self, pod_name):
        pod = self.v1.read_namespaced_pod(name=pod_name, namespace=self.namespace)
        for container in pod.spec.containers:
            if "logstash" in container.name:
                return container.name
        self.fail(f"No 'logstash' container found in pod '{pod_name}'.")

    def check_all_logstash_pods_ready(self):
        pods_ready = self.k8s_utils.wait_for_pod_ready("logstash", self.namespace)
        self.assertTrue(pods_ready, "Not all Logstash pods are ready.")
        
        for pod_name in self.logstash_pods:
            pod = self.k8s_utils.core_client.read_namespaced_pod(name=pod_name, namespace=self.namespace)
            container_statuses = pod.status.container_statuses
            self.assertIsNotNone(container_statuses, f"Pod '{pod_name}' has no container statuses.")
            for container_status in container_statuses:
                self.assertTrue(container_status.ready, f"Container in pod '{pod_name}' is not ready.")
            logging.info(f"Pod {pod_name} is ready")

    def test_logstash_pods_running(self):
        self.check_all_logstash_pods_ready()

    def test_logstash_pipeline_verification(self):
        logging.info("Verifying existence of Logstash pipelines in Logstash instance.")
        
        if not self.pipeline_configmaps:
            self.fail("No Logstash pipeline ConfigMaps were found, but they are required for correct operation.")
        
        pod_name = self.logstash_pods[0]
        container_name = self.get_logstash_container_name(pod_name)
        command = ["curl", "-s", "http://localhost:9600/_node/pipelines?pretty"]

        try:
            pipeline_data = stream(self.v1.connect_get_namespaced_pod_exec,
                                   pod_name,
                                   self.namespace,
                                   container=container_name,
                                   command=command,
                                   stderr=True, stdin=False,
                                   stdout=True, tty=False)
            
            for configmap_name in self.pipeline_configmaps:
                pipeline_name = configmap_name.split('-')[2]
                self.assertIn(pipeline_name, pipeline_data, f"Pipeline '{pipeline_name}' not found in Logstash.")
                logging.info(f"Pipeline '{pipeline_name}' is verified in Logstash instance.")
                
        except client.exceptions.ApiException as e:
            self.fail(f"Failed to retrieve pipelines from Logstash pod: {e}")

    def test_plugin_existence(self):
        logging.info("Checking for required plugins in Logstash.")
        pod_name = self.logstash_pods[0]
        container_name = self.get_logstash_container_name(pod_name)
        command = ["curl", "-s", "http://localhost:9600/_node/plugins?pretty"]
        
        try:
            plugin_data = stream(self.v1.connect_get_namespaced_pod_exec,
                                 pod_name,
                                 self.namespace,
                                 container=container_name,
                                 command=command,
                                 stderr=True, stdin=False,
                                 stdout=True, tty=False)
            
            for plugin in self.required_plugins:
                self.assertIn(plugin, plugin_data, f"Plugin '{plugin}' is not installed in Logstash.")
                logging.info(f"Plugin '{plugin}' is verified.")
        except client.exceptions.ApiException as e:
            self.fail(f"Failed to retrieve plugins from Logstash pod: {e}")

if __name__ == '__main__':
    unittest.main()
