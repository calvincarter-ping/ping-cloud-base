import unittest
import os
import json
import boto3
import k8s_utils
from datetime import datetime, timedelta

# Set time range for fetching logs (last 30 minutes)
dt_now_ms = round(datetime.now().timestamp() * 1000)
dt_past_ms = round((datetime.now() - timedelta(minutes=30)).timestamp() * 1000)

class TestCloudWatchLogs(k8s_utils.K8sUtils):
    # Get AWS region and cluster name, with fallback values
    aws_region = os.environ.get("AWS_REGION", "us-west-2")
    k8s_cluster_name = os.environ.get("CLUSTER_NAME", "default-cluster")
    
    # Initialize CloudWatch logs client
    aws_client = boto3.client("logs", region_name=aws_region)
    log_group_name = f"/aws/containerinsights/{k8s_cluster_name}/prometheus"
    
    # Metrics to check in CloudWatch logs
    metrics = ["kube_endpoint_address_available", "kube_node_status_condition"]

    def get_cloudwatch_logs(self):
        """Fetch logs from CloudWatch in the specified time range."""
        events = []
        response = self.aws_client.get_log_events(
            logGroupName=self.log_group_name,
            startTime=dt_past_ms,
            endTime=dt_now_ms,
            startFromHead=True
        )
        events.extend(response['events'])

        # Fetch remaining logs if there are more
        while response['nextForwardToken'] != response.get('prev_token', None):
            response['prev_token'] = response['nextForwardToken']
            response = self.aws_client.get_log_events(
                logGroupName=self.log_group_name,
                nextToken=response['nextForwardToken']
            )
            events.extend(response['events'])

        return [json.loads(event["message"])["log"].strip() for event in events]

    def test_log_group_exists(self):
        """Check if the CloudWatch log group exists."""
        response = self.aws_client.describe_log_groups(logGroupNamePrefix=self.log_group_name)
        self.assertTrue(response["logGroups"], "Log group not found")

    def test_metrics_in_logs(self):
        """Check if the required metrics are present in the logs."""
        cw_logs = self.get_cloudwatch_logs()
        for metric in self.metrics:
            self.assertTrue(any(metric in log for log in cw_logs), f"{metric} not found in logs")


if __name__ == "__main__":
    unittest.main()
