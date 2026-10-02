import json
import time
import boto3
from datetime import datetime, timezone

logs = boto3.client("logs", region_name="ap-south-1")

LOG_GROUP = "/aws/containerinsights/n8n-eks-lab/application"

QUERY = r"""
fields @timestamp, @message
| filter @message like /ERROR|CRITICAL/
| sort @timestamp desc
| limit 50
"""


def parse_message(message):
    try:
        return json.loads(message)
    except (TypeError, json.JSONDecodeError):
        return {
            "time": None,
            "log": message,
            "kubernetes": {}
        }


def lambda_handler(event, context):
    now = int(time.time())
    start_time = now - 300

    response = logs.start_query(
        logGroupName=LOG_GROUP,
        startTime=start_time,
        endTime=now,
        queryString=QUERY,
        limit=50
    )

    query_id = response["queryId"]

    # CloudWatch Logs Insights queries are asynchronous.
    # Poll until the query completes.
    status = "Scheduled"

    for _ in range(10):
        result = logs.get_query_results(queryId=query_id)
        status = result.get("status")

        if status == "Complete":
            break

        if status in ["Failed", "Cancelled", "Timeout", "Unknown"]:
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "CloudWatch query failed",
                    "query_status": status,
                    "query_id": query_id
                })
            }

        time.sleep(0.5)

    incidents = []

    for row in result.get("results", []):
        fields = {}

        for field in row:
            fields[field.get("field")] = field.get("value")

        message = fields.get("@message", "")
        parsed = parse_message(message)

        kubernetes = parsed.get("kubernetes", {})

        incidents.append({
            "timestamp": parsed.get("time") or fields.get("@timestamp"),
            "severity": (
                "CRITICAL"
                if "CRITICAL" in parsed.get("log", "")
                else "ERROR"
            ),
            "message": parsed.get("log", message),
            "cluster": "n8n-eks-lab",
            "namespace": kubernetes.get("namespace_name"),
            "pod": kubernetes.get("pod_name"),
            "container": kubernetes.get("container_name"),
            "node": kubernetes.get("host"),
            "pod_ip": kubernetes.get("pod_ip"),
            "image": kubernetes.get("container_image")
        })

    return {
        "statusCode": 200,
        "body": json.dumps({
            "source": "cloudwatch",
            "log_group": LOG_GROUP,
            "query_status": status,
            "query_id": query_id,
            "window_seconds": 300,
            "incident_count": len(incidents),
            "incidents": incidents
        })
    }
