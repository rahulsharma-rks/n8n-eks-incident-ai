import base64
import json
import os
import ssl
import urllib.parse
import urllib.request

import boto3
from botocore.signers import RequestSigner


# ============================================================
# Configuration
# ============================================================

REGION = os.environ.get(
    "AWS_REGION",
    "ap-south-1"
)

CLUSTER_NAME = os.environ.get(
    "CLUSTER_NAME",
    "n8n-eks-lab"
)

DEFAULT_NAMESPACE = os.environ.get(
    "DEFAULT_NAMESPACE",
    "n8n-demo"
)


# ============================================================
# AWS session / clients
# ============================================================

session = boto3.session.Session()

eks = session.client(
    "eks",
    region_name=REGION
)


# ============================================================
# EKS cluster information
# ============================================================

def get_cluster():
    """
    Retrieve EKS cluster configuration.
    """

    response = eks.describe_cluster(
        name=CLUSTER_NAME
    )

    return response["cluster"]


# ============================================================
# EKS CA certificate / TLS
# ============================================================

def get_ssl_context(cluster):
    """
    Build an SSL context using the CA certificate
    provided by the EKS cluster.
    """

    ca_data = (
        cluster[
            "certificateAuthority"
        ][
            "data"
        ]
    )

    ca_certificate = base64.b64decode(
        ca_data
    )

    ca_path = "/tmp/eks-ca.crt"

    with open(
        ca_path,
        "wb"
    ) as ca_file:

        ca_file.write(
            ca_certificate
        )

    return ssl.create_default_context(
        cafile=ca_path
    )


# ============================================================
# EKS authentication token
# ============================================================

def get_eks_token():
    """
    Generate an EKS IAM authentication token
    using the Lambda execution role.
    """

    credentials = (
        session.get_credentials()
    )

    sts_client = session.client(
        "sts",
        region_name=REGION
    )

    # Get the actual Botocore service-model ID.
    # Do not use the literal string "sts" here.
    service_id = (
        sts_client
        .meta
        .service_model
        .service_id
    )

    signer = RequestSigner(
        service_id,
        REGION,
        "sts",
        "v4",
        credentials,
        session._session.get_component(
            "event_emitter"
        )
    )

    params = {
        "method": "GET",

        "url": (
            f"https://sts.{REGION}.amazonaws.com/"
            "?Action=GetCallerIdentity"
            "&Version=2011-06-15"
        ),

        "body": {},

        "headers": {
            "x-k8s-aws-id": CLUSTER_NAME
        },

        "context": {}
    }

    signed_url = (
        signer.generate_presigned_url(
            params,
            region_name=REGION,
            expires_in=60,
            operation_name=""
        )
    )

    token = (
        "k8s-aws-v1."
        + base64.urlsafe_b64encode(
            signed_url.encode("utf-8")
        )
        .decode("utf-8")
        .rstrip("=")
    )

    return token


# ============================================================
# Kubernetes API - JSON response
# ============================================================

def kubernetes_json_request(
    cluster,
    path
):
    """
    Perform a read-only GET request against
    the Kubernetes API and parse JSON.
    """

    token = get_eks_token()

    url = (
        cluster["endpoint"]
        + path
    )

    request = urllib.request.Request(
        url,

        headers={
            "Authorization":
                f"Bearer {token}",

            "Accept":
                "application/json"
        },

        method="GET"
    )

    ssl_context = get_ssl_context(
        cluster
    )

    with urllib.request.urlopen(
        request,
        timeout=10,
        context=ssl_context
    ) as response:

        response_body = (
            response
            .read()
            .decode("utf-8")
        )

        return json.loads(
            response_body
        )


# ============================================================
# Kubernetes API - text response
# ============================================================

def kubernetes_text_request(
    cluster,
    path
):
    """
    Perform a read-only GET request against
    the Kubernetes API and return text.
    """

    token = get_eks_token()

    url = (
        cluster["endpoint"]
        + path
    )

    request = urllib.request.Request(
        url,

        headers={
            "Authorization":
                f"Bearer {token}"
        },

        method="GET"
    )

    ssl_context = get_ssl_context(
        cluster
    )

    with urllib.request.urlopen(
        request,
        timeout=10,
        context=ssl_context
    ) as response:

        return (
            response
            .read()
            .decode("utf-8")
        )


# ============================================================
# Get Pod
# ============================================================

def get_pod(
    cluster,
    namespace,
    pod_name
):
    """
    Retrieve a Kubernetes Pod.
    """

    namespace_encoded = (
        urllib.parse.quote(
            namespace,
            safe=""
        )
    )

    pod_encoded = (
        urllib.parse.quote(
            pod_name,
            safe=""
        )
    )

    path = (
        f"/api/v1/namespaces/"
        f"{namespace_encoded}/pods/"
        f"{pod_encoded}"
    )

    return kubernetes_json_request(
        cluster,
        path
    )


# ============================================================
# Get Pod Logs
# ============================================================

def get_pod_logs(
    cluster,
    namespace,
    pod_name,
    container_name
):
    """
    Retrieve the latest 50 lines of
    logs from a Kubernetes container.
    """

    namespace_encoded = (
        urllib.parse.quote(
            namespace,
            safe=""
        )
    )

    pod_encoded = (
        urllib.parse.quote(
            pod_name,
            safe=""
        )
    )

    container_encoded = (
        urllib.parse.quote(
            container_name,
            safe=""
        )
    )

    path = (
        f"/api/v1/namespaces/"
        f"{namespace_encoded}"
        f"/pods/{pod_encoded}/log?"
        f"container={container_encoded}"
        f"&tailLines=50"
    )

    return kubernetes_text_request(
        cluster,
        path
    )


# ============================================================
# Get Kubernetes Events
# ============================================================

def get_pod_events(
    cluster,
    namespace,
    pod_name
):
    """
    Retrieve Kubernetes events associated
    with the specified Pod.
    """

    namespace_encoded = (
        urllib.parse.quote(
            namespace,
            safe=""
        )
    )

    selector = (
        "involvedObject.kind=Pod,"
        f"involvedObject.name={pod_name}"
    )

    selector_encoded = (
        urllib.parse.quote(
            selector,
            safe=""
        )
    )

    path = (
        f"/api/v1/namespaces/"
        f"{namespace_encoded}/events?"
        f"fieldSelector={selector_encoded}"
    )

    response = kubernetes_json_request(
        cluster,
        path
    )

    events = []

    for item in response.get(
        "items",
        []
    ):

        events.append({

            "type":
                item.get("type"),

            "reason":
                item.get("reason"),

            "message":
                item.get("message"),

            "count":
                item.get("count"),

            "first_timestamp":
                item.get(
                    "firstTimestamp"
                ),

            "last_timestamp":
                item.get(
                    "lastTimestamp"
                )
        })

    return events[-20:]


# ============================================================
# Container status processing
# ============================================================

def build_container_statuses(
    status
):
    """
    Extract useful container runtime
    information from Pod status.
    """

    result = []

    for container in status.get(
        "containerStatuses",
        []
    ):

        result.append({

            "name":
                container.get(
                    "name"
                ),

            "ready":
                container.get(
                    "ready"
                ),

            "restart_count":
                container.get(
                    "restartCount"
                ),

            "image":
                container.get(
                    "image"
                ),

            "image_id":
                container.get(
                    "imageID"
                ),

            "state":
                container.get(
                    "state"
                ),

            "last_state":
                container.get(
                    "lastState"
                )
        })

    return result


# ============================================================
# HTTP response helpers
# ============================================================

def json_response(
    status_code,
    body
):
    """
    Create a standard API response.
    """

    return {

        "statusCode":
            status_code,

        "headers": {
            "Content-Type":
                "application/json"
        },

        "body":
            json.dumps(body)
    }


# ============================================================
# Lambda handler
# ============================================================

def lambda_handler(
    event,
    context
):

    # --------------------------------------------------------
    # Read query parameters
    # --------------------------------------------------------

    query = (
        event.get(
            "queryStringParameters"
        )
        or {}
    )

    namespace = query.get(
        "namespace",
        DEFAULT_NAMESPACE
    )

    pod_name = query.get(
        "pod"
    )

    container_name = query.get(
        "container"
    )


    # --------------------------------------------------------
    # Validate required parameter
    # --------------------------------------------------------

    if not pod_name:

        return json_response(
            400,
            {
                "error":
                    "Missing required "
                    "query parameter: pod"
            }
        )


    # --------------------------------------------------------
    # Retrieve Kubernetes context
    # --------------------------------------------------------

    try:

        # Get EKS cluster metadata.
        cluster = get_cluster()


        # Get Pod information.
        pod = get_pod(
            cluster,
            namespace,
            pod_name
        )


        metadata = pod.get(
            "metadata",
            {}
        )

        spec = pod.get(
            "spec",
            {}
        )

        status = pod.get(
            "status",
            {}
        )


        # ----------------------------------------------------
        # Container statuses
        # ----------------------------------------------------

        container_statuses = (
            build_container_statuses(
                status
            )
        )


        # If no container was supplied,
        # use the first container.
        if (
            not container_name
            and container_statuses
        ):

            container_name = (
                container_statuses[0]
                .get("name")
            )


        # ----------------------------------------------------
        # Recent logs
        # ----------------------------------------------------

        recent_logs = None

        if container_name:

            try:

                recent_logs = (
                    get_pod_logs(
                        cluster,
                        namespace,
                        pod_name,
                        container_name
                    )
                )

            except Exception as exc:

                recent_logs = (
                    "Unable to retrieve "
                    "pod logs: "
                    + str(exc)
                )


        # ----------------------------------------------------
        # Kubernetes events
        # ----------------------------------------------------

        events = get_pod_events(
            cluster,
            namespace,
            pod_name
        )


        # ----------------------------------------------------
        # Build final response
        # ----------------------------------------------------

        result = {

            "source":
                "eks",

            "cluster":
                CLUSTER_NAME,

            "namespace":
                namespace,

            "pod":
                pod_name,


            "context": {

                "metadata": {

                    "name":
                        metadata.get(
                            "name"
                        ),

                    "namespace":
                        metadata.get(
                            "namespace"
                        ),

                    "labels":
                        metadata.get(
                            "labels",
                            {}
                        )
                },


                "spec": {

                    "node_name":
                        spec.get(
                            "nodeName"
                        ),

                    "containers": [

                        {

                            "name":
                                container.get(
                                    "name"
                                ),

                            "image":
                                container.get(
                                    "image"
                                )

                        }

                        for container
                        in spec.get(
                            "containers",
                            []
                        )
                    ]
                },


                "status": {

                    "phase":
                        status.get(
                            "phase"
                        ),

                    "pod_ip":
                        status.get(
                            "podIP"
                        ),

                    "host_ip":
                        status.get(
                            "hostIP"
                        ),

                    "start_time":
                        status.get(
                            "startTime"
                        ),

                    "container_statuses":
                        container_statuses
                },


                "recent_logs":
                    recent_logs
            },


            "events":
                events
        }


        return json_response(
            200,
            result
        )


    # --------------------------------------------------------
    # Error handling
    # --------------------------------------------------------

    except Exception as exc:

        error_details = str(
            exc
        )

        print(
            json.dumps({

                "error":
                    error_details,

                "cluster":
                    CLUSTER_NAME,

                "namespace":
                    namespace,

                "pod":
                    pod_name

            })
        )

        return json_response(
            500,
            {
                "error":
                    "Unable to retrieve "
                    "Kubernetes context",

                "details":
                    error_details
            }
        )
