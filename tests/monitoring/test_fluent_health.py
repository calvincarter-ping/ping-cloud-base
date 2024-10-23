import subprocess
import time
import requests
from kubernetes import client, config
import urllib3
import unittest 

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

config.load_kube_config()

class PrometheusPortForward:
    process = None

    @staticmethod
    def start():
        if PrometheusPortForward.process:
            PrometheusPortForward.stop()
        PrometheusPortForward.process = subprocess.Popen(
            ["kubectl", "port-forward", "svc/prometheus", "9090:9090", "-n", "prometheus"],
            stdout=subprocess.PIPE
        )
        time.sleep(60)
        return PrometheusPortForward.process

    @staticmethod
    def stop():
        if PrometheusPortForward.process:
            PrometheusPortForward.process.terminate()
            PrometheusPortForward.process = None

def query_metric(metric_name, prometheus_url):
    try:
        response = requests.get(f"{prometheus_url}?query={metric_name}", verify=False)
        if response.status_code == 200:
            result = response.json()['data']['result']
            return float(result[0]['value'][1]) if result else None
    except requests.exceptions.ConnectionError as e:
        print(f"Error querying Prometheus: {e}")
    return None

class TestFluentBitMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prometheus_url = "http://localhost:9090/api/v1/query"

    def test_fluentbit_pods_health(self):
        api = client.CoreV1Api()
        pods = api.list_namespaced_pod("elastic-stack-logging", label_selector="k8s-app=fluent-bit").items
        for pod in pods:
            pod_name = pod.metadata.name
            pod_status = pod.status.conditions[-1].status
            self.assertTrue(pod_status == "True", f"Pod {pod_name} is not ready")
            print(f"Pod {pod_name} is ready")
        print("All pods are up and running.")

    def test_check_fluentbit_metrics(self):
        self.test_fluentbit_pods_health()

        time.sleep(120)  # 2-minute wait

        PrometheusPortForward.start()

        attempt = 0
        while True:
            input_records = query_metric("fluentbit_input_records_total", self.prometheus_url)
            output_records = query_metric("fluentbit_output_proc_records_total", self.prometheus_url)

            if input_records is None or output_records is None:
                print("Metrics not found or connection issue. Restarting port-forward and retrying...")
                PrometheusPortForward.start()
            elif input_records > 0 and output_records > 0:
                print(f"Attempt {attempt+1}: Metrics found.")
                print(f"fluentbit_input_records_total: {input_records}")
                print(f"fluentbit_output_proc_records_total: {output_records}")
                break
            else:
                print(f"Attempt {attempt+1}: Metrics issue: input={input_records}, output={output_records}")

            attempt += 1
            time.sleep(60)

        print(f"Metrics appeared after {attempt+1} attempts.")
        PrometheusPortForward.stop()

if __name__ == '__main__':
    unittest.main()
