import unittest
import os
import json
import boto3
from datetime import datetime, timedelta

dt_now_ms = round(datetime.now().timestamp() * 1000)
dt_past_ms = round((datetime.now() - timedelta(minutes=3)).timestamp() * 1000)

class TestCloudWatchLogs(unittest.TestCase):
    aws_region = os.environ.get("AWS_REGION", "us-west-2")
    k8s_cluster_name = os.environ.get("CLUSTER_NAME", "default-cluster")
    
    aws_client = boto3.client("logs", region_name=aws_region)
    log_group_name = f"/aws/containerinsights/{k8s_cluster_name}/prometheus"
    metrics = ["kube_endpoint_address_available", "kube_node_status_condition"]

    def get_latest_log_stream(self):
        try:
            response = self.aws_client.describe_log_streams(
                logGroupName=self.log_group_name,
                orderBy="LastEventTime",
                descending=True,
                limit=5
            )
            log_streams = response.get("logStreams", [])
            if log_streams:
                return log_streams[0]["logStreamName"]
            self.fail("No log streams found in the log group.")
        except Exception as e:
            self.fail(f"Error fetching log streams: {str(e)}")

    def check_metrics_in_logs(self, log_stream_name):
        found_metrics = {metric: False for metric in self.metrics}
        events = []
        iterations = 0
        max_iterations = 10
        start_time = datetime.now()
        max_duration = timedelta(minutes=2)

        try:
            while True:
                response = self.aws_client.get_log_events(
                    logGroupName=self.log_group_name,
                    logStreamName=log_stream_name,
                    startTime=dt_past_ms,
                    endTime=dt_now_ms,
                    limit=5
                )
                events.extend(response['events'])

                for event in events:
                    log_data = json.loads(event.get('message', '{}'))
                    for metric in self.metrics:
                        if metric in log_data:
                            found_metrics[metric] = True

                if all(found_metrics.values()):
                    return found_metrics

                if response.get('nextForwardToken') == response.get('prev_token', None):
                    break
                if (datetime.now() - start_time) > max_duration or len(events) >= max_iterations:
                    raise TimeoutError("Log fetching exceeded time or iteration limits.")

                response['prev_token'] = response['nextForwardToken']

        except Exception as e:
            self.fail(f"Error during log fetching: {str(e)}")

        return found_metrics

    def test_log_group_exists(self):
        response = self.aws_client.describe_log_groups(logGroupNamePrefix=self.log_group_name)
        self.assertTrue(response.get("logGroups"), "Log group not found")

    def test_metrics_in_logs(self):
        log_stream_name = self.get_latest_log_stream()
        found_metrics = self.check_metrics_in_logs(log_stream_name)

        if any(found_metrics.values()):
            found_metrics_str = ", ".join([metric for metric, found in found_metrics.items() if found])
            print(f"Test passed: Metrics found in log group '{self.log_group_name}': {found_metrics_str}.")
        else:
            self.fail(f"Neither metric was found in the logs for log group '{self.log_group_name}'.")

if __name__ == "__main__":
    unittest.main()
