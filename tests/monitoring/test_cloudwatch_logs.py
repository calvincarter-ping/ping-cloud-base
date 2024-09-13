import unittest
import os
import json
import boto3
from datetime import datetime, timedelta

dt_now_ms = round(datetime.now().timestamp() * 1000)
dt_past_ms = round((datetime.now() - timedelta(minutes=30)).timestamp() * 1000)

class TestCloudWatchLogs(unittest.TestCase):
    aws_region = os.environ.get("AWS_REGION", "us-west-2")
    k8s_cluster_name = os.environ.get("CLUSTER_NAME", "default-cluster")
    
    aws_client = boto3.client("logs", region_name=aws_region)
    log_group_name = f"/aws/containerinsights/{k8s_cluster_name}/prometheus"
    
    metrics = ["kube_endpoint_address_available", "kube_node_status_condition"]

    def get_cloudwatch_logs(self):
        events = []
        response = self.aws_client.get_log_events(
            logGroupName=self.log_group_name,
            startTime=dt_past_ms,
            endTime=dt_now_ms,
            startFromHead=True
        )
        events.extend(response['events'])

        while response['nextForwardToken'] != response.get('prev_token', None):
            response['prev_token'] = response['nextForwardToken']
            response = self.aws_client.get_log_events(
                logGroupName=self.log_group_name,
                nextToken=response['nextForwardToken']
            )
            events.extend(response['events'])

        return [json.loads(event["message"])["log"].strip() for event in events]

    def test_log_group_exists(self):
        response = self.aws_client.describe_log_groups(logGroupNamePrefix=self.log_group_name)
        self.assertTrue(response["logGroups"], "Log group not found")

    def test_metrics_in_logs(self):
        cw_logs = self.get_cloudwatch_logs()
        for metric in self.metrics:
            self.assertTrue(any(metric in log for log in cw_logs), f"{metric} not found in logs")


if __name__ == "__main__":
    unittest.main()
