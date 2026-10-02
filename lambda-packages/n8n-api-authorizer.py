import os

TOKEN = os.environ["N8N_API_TOKEN"]


def lambda_handler(event, context):
    headers = event.get("headers") or {}

    authorization = headers.get("authorization", "")

    expected = f"Bearer {TOKEN}"

    if authorization == expected:
        return {
            "isAuthorized": True,
            "context": {
                "source": "n8n"
            }
        }

    return {
        "isAuthorized": False
    }
