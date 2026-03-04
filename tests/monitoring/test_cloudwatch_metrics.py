import unittest
import os
import boto3
from datetime import datetime, timedelta


class TestCloudWatchLogs(unittest.TestCase):
    aws_region = os.environ.get("AWS_REGION", "us-west-2")
    k8s_cluster_name = os.environ["CLUSTER_NAME"]

    aws_client = boto3.client("logs", region_name=aws_region)
    log_group_name = f"/aws/containerinsights/{k8s_cluster_name}/prometheus"
    metrics = ["kube_endpoint_address", "kube_node_status_condition"]

    def check_log_group_exists(self):
        response = self.aws_client.describe_log_groups(
            logGroupNamePrefix=self.log_group_name
        )
        log_groups = response.get("logGroups", [])
        self.assertTrue(
            len(log_groups) > 0, f"Log group '{self.log_group_name}' does not exist."
        )

    def check_metric_in_log_group(self, metric_name):
        # Container Insights metric logs can be bursty; search a wider window.
        dt_now_ms = round(datetime.now().timestamp() * 1000)
        dt_past_ms = round((datetime.now() - timedelta(minutes=30)).timestamp() * 1000)

        next_token = None
        while True:
            kwargs = {
                "logGroupName": self.log_group_name,
                "startTime": dt_past_ms,
                "endTime": dt_now_ms,
                "filterPattern": f'"{metric_name}"',
                "limit": 10000,
            }
            if next_token:
                kwargs["nextToken"] = next_token

            response = self.aws_client.filter_log_events(**kwargs)

            if response.get("events"):
                return True

            new_token = response.get("nextToken")
            if not new_token or new_token == next_token:
                break
            next_token = new_token

        return False

    def test_metrics_in_logs(self):
        self.check_log_group_exists()

        found_metrics = {
            metric: self.check_metric_in_log_group(metric) for metric in self.metrics
        }
        missing_metrics = [metric for metric, found in found_metrics.items() if not found]

        self.assertTrue(
            all(found_metrics.values()),
            (
                f"Missing metrics in CloudWatch logs for log group '{self.log_group_name}' "
                f"(lookback: 30 minutes): {', '.join(missing_metrics)}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
