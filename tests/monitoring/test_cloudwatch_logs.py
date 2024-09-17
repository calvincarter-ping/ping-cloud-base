import unittest
import os
import json
import boto3
from datetime import datetime, timedelta
from botocore.exceptions import ParamValidationError

# Timestamps for log fetching
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
        max_iterations = 10  
        iteration = 0

        # Get log streams in the log group
        try:
            log_streams_response = self.aws_client.describe_log_streams(
                logGroupName=self.log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=5  # Fetch up to 5 log streams to avoid excessive data
            )
        except ParamValidationError as e:
            self.fail(f"Param validation failed: {str(e)}")
            return []
        except Exception as e:
            self.fail(f"Error describing log streams: {str(e)}")
            return []

        if not log_streams_response.get('logStreams'):
            self.fail(f"No log streams found in log group: {self.log_group_name}")
            return []

        for log_stream in log_streams_response.get('logStreams', []):
            log_stream_name = log_stream.get('logStreamName')
            if not log_stream_name:
                self.fail(f"Log stream name is missing for stream: {log_stream}")
                continue

            try:
                # Fetch log events from each stream
                response = self.aws_client.get_log_events(
                    logGroupName=self.log_group_name,
                    logStreamName=log_stream_name,
                    startTime=dt_past_ms,
                    endTime=dt_now_ms,
                    startFromHead=True
                )
            except ParamValidationError as e:
                self.fail(f"Param validation failed in get_log_events: {str(e)}")
                continue
            except Exception as e:
                self.fail(f"Error fetching log events: {str(e)}")
                continue

            events.extend(response.get('events', []))

            while response['nextForwardToken'] != response.get('prev_token', None) and iteration < max_iterations:
                iteration += 1
                response['prev_token'] = response['nextForwardToken']
                response = self.aws_client.get_log_events(
                    logGroupName=self.log_group_name,
                    logStreamName=log_stream_name,
                    nextToken=response['nextForwardToken']
                )
                new_events = response.get('events', [])
                if not new_events:
                    break 
                events.extend(new_events)

            if iteration >= max_iterations:
                self.fail(f"Max iterations ({max_iterations}) reached, stopping log fetching.")
                break

        return [json.loads(event["message"])["log"].strip() for event in events]

    def test_log_group_exists(self):
        try:
            response = self.aws_client.describe_log_groups(logGroupNamePrefix=self.log_group_name)
            self.assertTrue(response["logGroups"], "Log group not found")
        except ParamValidationError as e:
            self.fail(f"Param validation failed: {str(e)}")
        except Exception as e:
            self.fail(f"Error describing log group: {str(e)}")

    def test_metrics_in_logs(self):
        cw_logs = self.get_cloudwatch_logs()
        for metric in self.metrics:
            self.assertTrue(any(metric in log for log in cw_logs), f"{metric} not found in logs")


if __name__ == "__main__":
    unittest.main()
