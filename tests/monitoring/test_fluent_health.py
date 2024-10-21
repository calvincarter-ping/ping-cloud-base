import subprocess
import time
import requests
from kubernetes import client, config
import urllib3
import unittest

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

config.load_kube_config()

class PrometheusPortForward:
    @staticmethod
    def start():
        process = subprocess.Popen(
            ["kubectl", "port-forward", "svc/prometheus", "9090:9090", "-n", "prometheus"],
            stdout=subprocess.PIPE
        )
        time.sleep(60)  # Allow time for port-forward to establish
        return process

    @staticmethod
    def stop(process):
        process.terminate()

def query_metric(metric_name, prometheus_url):
    response = requests.get(f"{prometheus_url}?query={metric_name}", verify=False)
    if response.status_code == 200:
        result = response.json()['data']['result']
        return float(result[0]['value'][1]) if result else None
    return None

class TestFluentBitMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port_forward_process = PrometheusPortForward.start()
        cls.prometheus_url = "http://localhost:9090/api/v1/query"

    @classmethod
    def tearDownClass(cls):
        PrometheusPortForward.stop(cls.port_forward_process)

    def check_fluentbit_daemonset_status(self):
        api = client.AppsV1Api()
        daemonset = api.read_namespaced_daemon_set_status("fluent-bit", "elastic-stack-logging")
        return daemonset.status.number_ready == daemonset.status.desired_number_scheduled

    def test_fluentbit_daemonset_status(self):
        print("Checking Fluent Bit DaemonSet status...")
        self.assertTrue(self.check_fluentbit_daemonset_status(), "Fluent Bit DaemonSet is not healthy.")
        print("All Fluent Bit pods are up and running.")

    def test_check_fluentbit_metrics(self):
        # First, ensure all Fluent Bit pods are up before proceeding
        self.assertTrue(self.check_fluentbit_daemonset_status(), "Fluent Bit DaemonSet is not fully ready.")

        # Wait for 2 minutes before starting the metrics test
        print("All pods are up. Waiting 2 minutes before checking the metrics...")
        time.sleep(120)  # 2-min delay

        retry_attempts = 5
        sleep_interval = 30  # 30 seconds between retries
        
        for attempt in range(retry_attempts):
            input_records = query_metric("fluentbit_input_records_total", self.prometheus_url)
            output_records = query_metric("fluentbit_output_proc_records_total", self.prometheus_url)

            if input_records is not None and output_records is not None:
                if input_records > 0 and output_records > 0:
                    print(f"Attempt {attempt+1}: Metrics found.")
                    print(f"fluentbit_input_records_total: {input_records}")
                    print(f"fluentbit_output_proc_records_total: {output_records}")
                    print("Both Fluent Bit metrics are generating fine.")
                    return  # Success, exit test case
                else:
                    print(f"Attempt {attempt+1}: Metrics issue: input={input_records}, output={output_records}")
            else:
                print(f"Attempt {attempt+1}: Metrics not found yet. Waiting {sleep_interval} seconds before retrying...")

            time.sleep(sleep_interval)  # Wait before retrying

        # If we exhaust all retry attempts, fail the test
        self.fail(f"Metrics issue after {retry_attempts} attempts: input={input_records}, output={output_records}")

if __name__ == '__main__':
    unittest.main()
