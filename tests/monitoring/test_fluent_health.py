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
        time.sleep(60)  # Allow time for port-forward to establish

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
        PrometheusPortForward.start()

    @classmethod
    def tearDownClass(cls):
        PrometheusPortForward.stop()

    def check_fluentbit_pod_health(self):
        api = client.CoreV1Api()
        pods = api.list_namespaced_pod(namespace="elastic-stack-logging", label_selector="k8s-app=fluent-bit").items
        all_pods_ready = True
        for pod in pods:
            pod_name = pod.metadata.name
            pod_status = all([container.ready for container in pod.status.container_statuses])
            print(f"Pod {pod_name} is {'ready' if pod_status else 'not ready'}")
            all_pods_ready = all_pods_ready and pod_status
        return all_pods_ready

    def test_fluentbit_pods_health(self):
        self.assertTrue(self.check_fluentbit_pod_health(), "Not all Fluent Bit pods are healthy.")

    def test_check_fluentbit_metrics(self):
        self.assertTrue(self.check_fluentbit_pod_health(), "Fluent Bit DaemonSet is not fully ready.")
        print("All pods are up. Waiting 2 minutes before checking the metrics...")
        time.sleep(120)

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
                print("Both Fluent Bit metrics are generating fine.")
                break
            else:
                print(f"Attempt {attempt+1}: Metrics issue: input={input_records}, output={output_records}")

            attempt += 1
            time.sleep(60)

        print(f"Metrics appeared after {attempt+1} attempts.")

if __name__ == '__main__':
    unittest.main()
