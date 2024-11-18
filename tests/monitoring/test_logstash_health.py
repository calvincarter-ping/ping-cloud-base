import unittest
import logging
from k8s_utils import K8sUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TestLogstash(unittest.TestCase):
    namespace = "elastic-stack-logging"
    logstash_pods = ["logstash-elastic-0", "logstash-elastic-1"]
    pipeline_patterns = ["logstash-pipeline-customer"]
    required_plugins = [
        "logstash-filter-opensearch-manticore", "logstash-input-opensearch",
        "logstash-output-awslogs", "logstash-output-newrelic",
        "logstash-output-opensearch", "logstash-output-syslog"
    ]

    def check_pod_status(self, pod_name):
        command = f"kubectl get pod {pod_name} -n {self.namespace} -o jsonpath='{{.status.phase}}'"
        status = self.k8s_utils.run_command(command)
        logging.info(f"Pod '{pod_name}' status: {status}")
        return status

    def check_container_status(self, pod_name):
        command = f"kubectl get pod {pod_name} -n {self.namespace} -o jsonpath='{{range .status.containerStatuses[?(@.name==\"logstash\")].state}}'"
        state = self.k8s_utils.run_command(command)
        logging.info(f"Container 'logstash' in pod '{pod_name}' state: {state}")
        return state

    def check_plugins(self, pod_name):
        command = f"kubectl exec -it {pod_name} -n {self.namespace} -- curl -s http://localhost:9600/_node/plugins?pretty"
        plugin_data = self.k8s_utils.run_command(command)
        return plugin_data

    def check_pipeline(self, pod_name):
        command = f"kubectl exec -it {pod_name} -n {self.namespace} -- curl -s http://localhost:9600/_node/stats/pipelines/customer?pretty"
        pipeline_data = self.k8s_utils.run_command(command)
        return pipeline_data

    def test_logstash_pods_status(self):
        for pod_name in self.logstash_pods:
            status = self.check_pod_status(pod_name)
            self.assertEqual(status, "Running", f"Pod '{pod_name}' is not running.")

    def test_logstash_container_status(self):
        for pod_name in self.logstash_pods:
            state = self.check_container_status(pod_name)
            self.assertIn("running", state, f"Container 'logstash' in pod '{pod_name}' is not running.")

    def test_plugins_existence(self):
        for pod_name in self.logstash_pods:
            plugin_data = self.check_plugins(pod_name)
            missing_plugins = [plugin for plugin in self.required_plugins if plugin not in plugin_data]
            self.assertFalse(missing_plugins, f"Missing plugins in pod '{pod_name}': {', '.join(missing_plugins)}")

    def test_logstash_pipeline_verification(self):
        for pod_name in self.logstash_pods:
            pipeline_data = self.check_pipeline(pod_name)
            missing_pipelines = [pipeline for pipeline in self.pipeline_patterns if pipeline not in pipeline_data]
            self.assertFalse(missing_pipelines, f"Missing pipelines in pod '{pod_name}': {', '.join(missing_pipelines)}")

if __name__ == '__main__':
    unittest.main()
