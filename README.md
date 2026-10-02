# n8n EKS Incident AI

An end-to-end AWS/Kubernetes/SRE automation project that detects application incidents from Amazon EKS and CloudWatch Logs, enriches them
with live Kubernetes context, analyzes them with an AI model, and sends a structured incident report by email.

<img width="1435" height="641" alt="n8n-Workflow" src="https://github.com/user-attachments/assets/e6567bea-7a1c-4f99-88a9-87d8a68b2c72" />


The workflow follows:

``` text

Detect → Analyze → Recommend → Notify → Human Approval → Remediate

```

The AI does **not** execute arbitrary `kubectl` or shell commands.

---

## 1. Quick introduction to n8n

[n8n](https://n8n.io/) is a workflow automation platform that connects APIs, cloud services, databases, AI models, applications, and custom
code through visual workflows.

For this project, n8n is the orchestration layer:

``` text

CloudWatch → API Gateway → n8n → Kubernetes API → AI → Gmail

```

n8n lets the workflow separate each stage into an observable node for retrieval, parsing, filtering, enrichment, AI analysis, routing, and
notification.

---

## 1.1 Deployment package

To make replication easier, this project includes a downloadable deployment package containing the Lambda ZIP artifacts, IAM policies, and a helper deployment script.

The package contains:

```text

n8n-eks-incident-ai-deployment/

├── lambda-packages/

│   ├── n8n-api-authorizer.zip

│   ├── n8n-cloudwatch-incident-reader.zip

│   └── n8n-eks-context-reader.zip

├── iam/

│   ├── n8n-cloudwatch-reader-policy.json

│   └── n8n-eks-context-reader-policy.json

├── scripts/

│   └── deploy-lambda-code.sh

└── DEPLOYMENT.md

```

The README intentionally does **not** embed the Lambda source code. Deploy the supplied ZIP files as Lambda function code packages. The Lambda configuration, IAM requirements, API Gateway setup, EKS access configuration, and n8n workflow configuration are documented below.

### Lambda deployment file mapping

| Component -> Deployment file -> Lambda function |

| API authorizer -> `lambda-packages/n8n-api-authorizer.zip` -> `n8n-api-authorizer` |

| CloudWatch incident reader -> `lambda-packages/n8n-cloudwatch-incident-reader.zip` -> `n8n-cloudwatch-incident-reader` |

| EKS context reader -> `lambda-packages/n8n-eks-context-reader.zip` -> `n8n-eks-context-reader` |

The deployment package is the source of truth for the Lambda implementation. The README documents how each function is configured and integrated, while the ZIP files contain the executable Lambda code.

> **Security:** Review and adapt the IAM policies for your own AWS account and cluster. Never commit bearer tokens, OAuth credentials, or other secrets to the repository.

---

## 2. Project architecture

``` mermaid

flowchart LR

    EKS["Amazon EKS<br/>Application Pods"]

    CW["CloudWatch Logs<br/>Container Insights"]

    L1["Lambda<br/>CloudWatch Incident Reader"]

    API1["API Gateway<br/>GET /incidents"]

    N8N["n8n Cloud<br/>Workflow"]

    API2["API Gateway<br/>GET /kubernetes-context"]

    L2["Lambda<br/>EKS Context Reader"]

    AI["AI SRE Analyzer<br/>OpenAI"]

    G["Gmail<br/>OAuth"]

    EKS -->|logs| CW

    CW --> L1

    L1 --> API1

    API1 --> N8N

    N8N -->|pod, namespace, container| API2

    API2 --> L2

    L2 --> EKS

    L2 --> N8N

    N8N --> AI

    AI --> N8N

    N8N -->|CRITICAL| G

```

### n8n workflow

``` mermaid

flowchart TD

    S["Schedule Trigger"]

    H["HTTP Request<br/>CloudWatch Incident API"]

    P["Parse JSON"]

    D["Deduplicate Incidents"]

    SP["Split Incidents"]

    N["Normalize / Aggregate Incident"]

    K["Get Kubernetes Context"]

    B["Build AI Incident"]

    A["AI Incident Analyzer"]

    SOP["Structured Output Parser"]

    NA["Normalize AI Output"]

    IF["IF severity == CRITICAL"]

    E["Build Incident Email"]

    G["Gmail"]

    S --> H --> P --> D --> SP --> N --> K --> B --> A --> SOP --> NA --> IF

    IF -->|TRUE| E --> G

```

---

## 3. Reference environment

The completed lab used:

  AWS Region:                         `ap-south-1`

  EKS Cluster:                        `n8n-eks-lab`

  Namespace:                          `n8n-demo`

  CloudWatch application log group:   `/aws/containerinsights/n8n-eks-lab/application`

  n8n:                                n8n Cloud Portal (Free Trial is Available)

  Incident API:                       `GET /incidents`

  Kubernetes Context API:             `GET /kubernetes-context`

Replace all environment-specific IDs, account numbers, API IDs, tokens, and addresses when reproducing the project.

---

## 4. Prerequisites

Install/configure:

-   AWS CLI
-   `kubectl`
-   AWS account
-   EKS cluster
-   CloudWatch Observability add-on
-   n8n Cloud
-   OpenAI credential in n8n
-   Gmail OAuth credential in n8n

Verify:

``` bash

aws --version

kubectl version --client

aws sts get-caller-identity

```

---

## 5. EKS setup

The completed environment used EKS Auto Mode. For a new environment, create an EKS cluster using your preferred
supported provisioning method. Ensure:

-   Kubernetes API access is enabled.
-   Workload subnets have outbound connectivity when public container

    images are used.

-   CloudWatch Observability is enabled.
-   EKS access entries are configured.
-   The Lambda execution role can reach the Kubernetes API endpoint.

Configure `kubectl`:

``` bash

aws eks update-kubeconfig \
  --region ap-south-1 \
  --name n8n-eks-lab

```

Verify:

``` bash

kubectl get nodes

```

---

## 6. EKS IAM access entry

Example:

``` bash

aws eks create-access-entry \
  --cluster-name n8n-eks-lab \
  --principal-arn arn:aws:iam::ACCOUNT_ID:user/YOUR_IAM_USER \
  --type STANDARD

```

Associate the required policy:

``` bash

aws eks associate-access-policy \
  --cluster-name n8n-eks-lab \
  --principal-arn arn:aws:iam::ACCOUNT_ID:user/YOUR_IAM_USER \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster

```

For production, use a narrower access policy than cluster-admin.

---

## 7. CloudWatch Observability

The completed project used the Amazon CloudWatch Observability EKS add-on.

Important log groups:

``` text

/aws/containerinsights/n8n-eks-lab/application
/aws/containerinsights/n8n-eks-lab/dataplane
/aws/containerinsights/n8n-eks-lab/host

```

Verify:

``` bash

aws logs describe-log-groups \
  --log-group-name-prefix "/aws/containerinsights/n8n-eks-lab" \
  --region ap-south-1

```

Logs Insights example:

``` text

fields @timestamp, @message
| filter @message like /log-failure-demo/
| sort @timestamp desc
| limit 50

```

---

## 8. VPC/NAT connectivity

The completed lab initially had private EKS subnets without NAT connectivity. Container image pulls failed with

`ImagePullBackOff`/`ErrImagePull`.

The final design added a NAT Gateway and a private-subnet default route:

``` text

0.0.0.0/0 → NAT Gateway

```

For a new environment, ensure EKS workload subnets can reach required external endpoints.

Inspect route tables:

``` bash

aws ec2 describe-route-tables \
  --filters "Name=vpc-id,Values=YOUR_VPC_ID" \
  --region ap-south-1

```

---

## 9. Create the demo namespace

``` bash

kubectl create namespace n8n-demo

```

---

## 10. Create the controlled failing application

Save as `log-failure-demo.yaml`:

``` yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: log-failure-demo
  namespace: n8n-demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: log-failure-demo
  template:
    metadata:
      labels:
        app: log-failure-demo
    spec:
      containers:
        - name: app
          image: public.ecr.aws/docker/library/alpine:3.20
          command: ["/bin/sh", "-c"]
          args:
            - |
              echo "INFO application starting"
              sleep 2
              echo "INFO loading application configuration"
              sleep 2
              echo "ERROR database connection failed: connection refused"
              echo "ERROR unable to initialize application"
              echo "CRITICAL application startup failed"
              exit 1

```

Apply:

``` bash

kubectl apply -f log-failure-demo.yaml

```

Verify:

``` bash

kubectl get pods -n n8n-demo -o wide
kubectl logs deployment/log-failure-demo -n n8n-demo

```

Expected:

``` text

INFO application starting
INFO loading application configuration
ERROR database connection failed: connection refused
ERROR unable to initialize application
CRITICAL application startup failed

```

Inspect:

``` bash

kubectl describe pod POD_NAME -n n8n-demo
kubectl logs POD_NAME -c app --previous -n n8n-demo
kubectl get events -n n8n-demo --sort-by=.lastTimestamp

```

---

## 11. CloudWatch Incident Reader IAM role

Create:

``` text

n8n-cloudwatch-reader-role

```

Attach:

-   `AWSLambdaBasicExecutionRole`

-   the following custom policy

``` json

{

  "Version": "2012-10-17",

  "Statement": [

    {

      "Sid": "StartApplicationLogQueries",

      "Effect": "Allow",

      "Action": [

        "logs:StartQuery"

      ],

      "Resource": [

        "arn:aws:logs:ap-south-1:ACCOUNT_ID:log-group:/aws/containerinsights/n8n-eks-lab/application",

        "arn:aws:logs:ap-south-1:ACCOUNT_ID:log-group:/aws/containerinsights/n8n-eks-lab/application:*"

      ]

    },

    {

      "Sid": "ReadQueryResults",

      "Effect": "Allow",

      "Action": [

        "logs:GetQueryResults"

      ],

      "Resource": "*"

    }

  ]

}

```

Replace `ACCOUNT_ID`.

---

## 12. CloudWatch Incident Reader Lambda

The Lambda source code is packaged separately so the README remains focused on architecture and deployment.

**Deployment file:** `lambda-packages/n8n-cloudwatch-incident-reader.zip`

Use the ZIP package from the deployment bundle. Do not paste the Lambda source code into the AWS console.

---

## 13. Incident API Gateway

Create HTTP API:

``` text

n8n-eks-incident-api

```

Route:

``` text

GET /incidents

```

Integration:

``` text

n8n-cloudwatch-incident-reader

```

Use Lambda proxy integration.

Protect the route with a request/Lambda authorizer using:

``` text

$request.header.Authorization

```

---

## 14. Bearer-token authorizer

The authorizer source code is packaged separately.

**Deployment file:** `lambda-packages/n8n-api-authorizer.zip`

Configure the Lambda with the following environment variable:

``` text

N8N_API_TOKEN

```

---

## 15. EKS Context Reader IAM role

Create:

``` text

n8n-eks-context-reader-role

```

Attach:

-   `AWSLambdaBasicExecutionRole`

-   this custom policy:

``` json

{

  "Version": "2012-10-17",

  "Statement": [

    {

      "Sid": "DescribeEKSCluster",

      "Effect": "Allow",

      "Action": [

        "eks:DescribeCluster"

      ],

      "Resource": "arn:aws:eks:ap-south-1:ACCOUNT_ID:cluster/n8n-eks-lab"

    }

  ]

}

```

---

## 16. EKS access entry for the context Lambda

Create an EKS access entry for:

``` text

arn:aws:iam::ACCOUNT_ID:role/n8n-eks-context-reader-role

```

Associate:

``` text

arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy

```

For the lab, scope access to the `n8n-demo` namespace.

---

## 17. EKS Context Reader Lambda

The Lambda source code is packaged separately.

**Deployment file:** `lambda-packages/n8n-eks-context-reader.zip`

Use the ZIP package from the deployment bundle. Do not paste the Lambda source code into the AWS console.

Runtime:

``` text

Python 3.13

```

Handler:

``` text

lambda_function.lambda_handler

```

Timeout:

``` text

20 seconds

```

Memory:

``` text

256 MB

```

Environment:

``` text

CLUSTER_NAME=n8n-eks-lab

DEFAULT_NAMESPACE=n8n-demo

```

---

## 18. Kubernetes Context API Gateway

Create:

``` text

n8n-eks-context-api

```

Route:

``` text

GET /kubernetes-context

```

Integration:

``` text

n8n-eks-context-reader

```

Protect it with the bearer-token authorizer.

Example:

``` bash

curl -s \

  -H "Authorization: Bearer $N8N_API_TOKEN" \

  "https://YOUR_CONTEXT_API_ID.execute-api.ap-south-1.amazonaws.com/kubernetes-context?namespace=n8n-demo&pod=$POD_NAME&container=app" \

  | python3 -m json.tool

```

---

# 19. n8n workflow configuration

Create:

``` text

AWS EKS AI Incident Response

```

Final workflow:

``` text

Schedule Trigger

 ↓

HTTP Request

 ↓

Parse JSON

 ↓

Deduplicate Incidents

 ↓

Split Incidents

 ↓

Normalize / Aggregate Incident

 ↓

Get Kubernetes Context

 ↓

Build AI Incident

 ↓

AI Incident Analyzer

 ↓

Normalize AI Output

 ↓

IF severity == CRITICAL

 ↓

Build Incident Email

 ↓

Gmail

```

---

## 19.1 Schedule Trigger

Add:

``` text

Schedule Trigger

```

For testing, use **Execute Workflow** manually.
For continuous monitoring, configure an interval such as five minutes, subject to your CloudWatch query volume and cost requirements.

---

## 19.2 HTTP Request --- CloudWatch incidents

Method:

``` text

GET

```

URL:

``` text

https://YOUR_INCIDENT_API_ID.execute-api.ap-south-1.amazonaws.com/incidents

```

Header:

``` text

Authorization: Bearer YOUR_TOKEN

```

Store the token securely in n8n rather than hard-coding it into the workflow.

---

## 19.3 Parse JSON

Code node:

``` javascript

const data = $input.first().json.data;

const parsed =

  typeof data === "string"

    ? JSON.parse(data)

    : data;

return [

  {

    json: parsed

  }

];

```

---

## 19.4 Deduplicate Incidents

Mode:

``` text

Run Once for All Items

```

Code:

``` javascript

const data = $input.first().json;

const incidents = data.incidents || [];

const unique = [];

const seen = new Set();

for (const incident of incidents) {

  const key = [

    incident.pod,

    incident.container,

    incident.severity,

    incident.message

  ].join("|");

  if (!seen.has(key)) {

    seen.add(key);

    unique.push(incident);

  }

}

return [

  {

    json: {

      ...data,

      incidents: unique,

      incident_count: unique.length

    }

  }

];

```

This is execution-local deduplication. Persistent deduplication is a future enhancement.

---

## 19.5 Split Incidents

Add:

``` text

Split Out

```

Field:

``` text

incidents

```

Use:

``` text

Include: No Other Fields

```

---

## 19.6 Normalize / Aggregate Incident

Mode:

``` text

Run Once for All Items

```

Code:

``` javascript

const items = $input.all();

const incidentsByResource = new Map();

for (const item of items) {

  const incident = item.json;

  const key = [

    incident.cluster,

    incident.namespace,

    incident.pod,

    incident.container,

  ].join("|");

  if (!incidentsByResource.has(key)) {

    incidentsByResource.set(key, {

      cluster: incident.cluster,

      namespace: incident.namespace,

      pod: incident.pod,

      container: incident.container,

      node: incident.node,

      pod_ip: incident.pod_ip,

      image: incident.image,

      highest_severity: incident.severity,

      timestamps: [],

      messages: [],

      evidence: [],

    });

  }

  const grouped =

    incidentsByResource.get(key);

  if (incident.timestamp) {

    grouped.timestamps.push(

      incident.timestamp

    );

  }

  if (incident.message) {

    grouped.messages.push(

      incident.message

    );

  }

  grouped.evidence.push({

    timestamp: incident.timestamp,

    severity: incident.severity,

    message: incident.message,

  });

  if (incident.severity === "CRITICAL") {

    grouped.highest_severity = "CRITICAL";

  }

}

return Array.from(

  incidentsByResource.values()

).map((incident) => ({

  json: {

    incident: {

      cluster: incident.cluster,

      namespace: incident.namespace,

      pod: incident.pod,

      container: incident.container,

      node: incident.node,

      pod_ip: incident.pod_ip,

      image: incident.image,

      severity: incident.highest_severity,

      timestamps: incident.timestamps,

      messages: [

        ...new Set(

          incident.messages

        )

      ],

      evidence: incident.evidence,

    }

  }

}));

```

---

## 19.7 Get Kubernetes Context

HTTP Request:

``` text

GET

```

URL:

``` text

https://YOUR_CONTEXT_API_ID.execute-api.ap-south-1.amazonaws.com/kubernetes-context

```

Query parameters:

``` text

namespace = {{ $json.incident.namespace }}

pod       = {{ $json.incident.pod }}

container = {{ $json.incident.container }}

```

Header:

``` text

Authorization: Bearer YOUR_TOKEN

```

---

## 19.8 Build AI Incident

Code:

``` javascript

const kubernetes =

  $input.first().json;

const normalized =

  $('Normalize / Aggregate Incident')

    .first()

    .json;

return [

  {

    json: {

      incident:

        normalized.incident,

      kubernetes:

        kubernetes

    }

  }

];

```

---

## 19.9 AI Incident Analyzer

Use an AI Agent node.

Prompt:

``` javascript

={{

  "Analyze this Kubernetes/EKS incident using the incident evidence and Kubernetes runtime context below.\n\n" +

  "INCIDENT DATA:\n" +

  JSON.stringify(

    $json.incident,

    null,

    2

  ) +

  "\n\nKUBERNETES CONTEXT:\n" +

  JSON.stringify(

    $json.kubernetes,

    null,

    2

  ) +

  "\n\nPerform an evidence-based incident diagnosis. Identify observed facts, probable causes, supporting evidence, safe investigation steps, and recommended remediation. Do not execute commands."

}}

```

System message:

``` text

You are a senior Kubernetes and AWS EKS SRE performing incident analysis. Analyze incidents using only the evidence provided.
Your analysis must consider:
- CloudWatch application logs
- Kubernetes pod phase
- container readiness
- restart count
- current container state
- previous container termination state
- exit code
- container image
- Kubernetes node
- recent pod logs
- Kubernetes events

Rules:

1\. Clearly distinguish observed FACTS from hypotheses.
2\. Correlate application logs with Kubernetes runtime state.
3\. Do not invent infrastructure state or dependencies that are not provided.
4\. Do not claim a dependency is unavailable without supporting evidence.
5\. Identify the most probable failure mechanism and explain the evidence.
6\. Identify alternative plausible causes when appropriate.
7\. Provide confidence from 0 to 100.
8\. Investigation commands must be read-only.
9\. Do not execute commands.
10\. Do not perform automatic destructive remediation.
11\. Recommended remediation must be proportional to the evidence.
12\. If evidence is insufficient, explicitly state what additional information is required.
13\. Return only the requested structured JSON.

```

---

## 19.10 OpenAI Chat Model

The completed workflow used:

``` text

Model: gpt-5-mini

Responses API: ON

```

Connect the model to the AI Agent. Store the API credential in n8n Credentials.

---

## 19.11 Structured Output Parser

Use:

``` text

Generate From JSON Example

```

Example:

``` json

{

  "output": {

    "incident": {
      "title": "Application CrashLoopBackOff: startup failure",
      "severity": "CRITICAL",
      "category": "Application startup failure",
      "confidence": 85

    },

    "resource": {

      "cluster": "n8n-eks-lab",
      "namespace": "n8n-demo",
      "pod": "log-failure-demo-66bdc888f7-zjdfx",
      "container": "app",
      "node": "i-051dda83712d5159a"

    },

    "observations": [

      "Pod is running but the application container is not ready.",
      "Container is repeatedly restarting with CrashLoopBackOff.",
      "The last container termination exited with code 1.",
      "Application logs report a database connection failure."

    ],

    "evidence": [

      "ERROR database connection failed: connection refused",
      "ERROR unable to initialize application",
      "CRITICAL application startup failed",
      "Kubernetes reports repeated BackOff events."

    ],

    "probable_causes": [

      {

        "cause": "Application cannot establish a connection to its configured database",
        "likelihood": "HIGH",
        "reason": "The application explicitly reports a database connection refusal immediately before exiting."

      }

    ],

    "recommended_actions": [

      {

        "priority": 1,
        "action": "Verify the configured database endpoint and connectivity from the application environment.",
        "command": "kubectl -n n8n-demo describe pod log-failure-demo-66bdc888f7-zjdfx",
        "risk": "LOW"

      }

    ],

    "investigation_commands": [

      "kubectl -n n8n-demo describe pod log-failure-demo-66bdc888f7-zjdfx",
      "kubectl -n n8n-demo logs log-failure-demo-66bdc888f7-zjdfx --previous"

    ],

    "summary": "The application is repeatedly failing during startup because its database connection is being refused, causing exit code 1 and CrashLoopBackOff."

  }

}

```

---

## 19.12 Normalize AI Output

Code:

``` javascript

const output =

  $json.output ??

  $json.response?.output ??

  $json;

return {

  json: output

};

```

---

## 19.13 IF severity routing

Expression:

``` javascript

{{ $json.incident.severity }}

```

Operation:

``` text

is equal to

```

Value:

``` text

CRITICAL

```

---

## 19.14 Build Incident Email

Code:

``` javascript

const incident = $json.incident;

const resource = $json.resource;

const escapeHtml = (value) =>

  String(value ?? "")

    .replace(/&/g, "&amp;")

    .replace(/</g, "&lt;")

    .replace(/>/g, "&gt;")

    .replace(/"/g, "&quot;")

    .replace(/'/g, "&#39;");

const observations = ($json.observations || [])

  .map(

    (item) => `

      <li>${escapeHtml(item)}</li>

    `

  )

  .join("");

const evidence = ($json.evidence || [])

  .map(

    (item) => `

      <li>${escapeHtml(item)}</li>

    `

  )

  .join("");

const causes = ($json.probable_causes || [])

  .map(

    (item) => `

      <li>

        <strong>${escapeHtml(item.cause)}</strong>

        — Likelihood: ${escapeHtml(item.likelihood)}

        <br>

        ${escapeHtml(item.reason)}

      </li>

    `

  )

  .join("");

const actions = ($json.recommended_actions || [])

  .map(

    (item) => `

      <li>

        <strong>Priority ${escapeHtml(item.priority)}:</strong>

        ${escapeHtml(item.action)}

        <br>

        <strong>Risk:</strong> ${escapeHtml(item.risk)}

        ${

          item.command

            ? `

              <br>

              <strong>Command:</strong>

              <code>${escapeHtml(item.command)}</code>

            `

            : ""

        }

      </li>

    `

  )

  .join("");

const investigation = ($json.investigation_commands || [])

  .map(

    (item) => `

      <li>

        <code>${escapeHtml(item)}</code>

      </li>

    `

  )

  .join("");

const html = `

<html>

  <body style="font-family: Arial, sans-serif; line-height: 1.5;">

    <h2>🚨 Kubernetes Critical Incident</h2>

    <p>

      <strong>Severity:</strong>

      ${escapeHtml(incident.severity)}

      <br>

      <strong>Confidence:</strong>

      ${escapeHtml(incident.confidence)}%

    </p>

    <h3>

      ${escapeHtml(incident.title)}

    </h3>

    <p>

      <strong>Category:</strong>

      ${escapeHtml(incident.category)}

    </p>

    <h3>Resource</h3>

    <ul>

      <li>

        <strong>Cluster:</strong>

        ${escapeHtml(resource.cluster)}

      </li>

      <li>

        <strong>Namespace:</strong>

        ${escapeHtml(resource.namespace)}

      </li>

      <li>

        <strong>Pod:</strong>

        ${escapeHtml(resource.pod)}

      </li>

      <li>

        <strong>Container:</strong>

        ${escapeHtml(resource.container)}

      </li>

      <li>

        <strong>Node:</strong>

        ${escapeHtml(resource.node)}

      </li>

    </ul>

    <h3>Summary</h3>

    <p>

      ${escapeHtml($json.summary)}

    </p>

    <h3>Observed Facts</h3>

    <ul>

      ${observations}

    </ul>

    <h3>Evidence</h3>

    <ul>

      ${evidence}

    </ul>

    <h3>Probable Causes</h3>

    <ul>

      ${causes}

    </ul>

    <h3>Recommended Actions</h3>

    <ul>

      ${actions}

    </ul>

    <h3>Investigation Commands</h3>

    <ul>

      ${investigation}

    </ul>

    <hr>

    <p style="font-size: 12px; color: #666;">
      Generated automatically by the AWS EKS AI Incident Analysis workflow.
    </p>

  </body>

</html>

`;

return {

  json: {

    ...$json,

    email_subject: `[${incident.severity}] ${incident.title}`,

    email_html: html

  }

};


```

---

## 19.15 Gmail node

Use the n8n Gmail node with Gmail OAuth.

Configuration:

``` text

Resource: Message

Operation: Send

```

Subject:

``` javascript

{{ $json.email_subject }}

```

Email format:

``` text

HTML

```

HTML:

``` javascript

{{ $json.email_html }}

```

Use an OAuth credential rather than a normal Gmail password.

---

# 20. Expected result

A successful email should contain:

``` text

[CRITICAL] Pod CrashLoopBackOff after application fails to connect to database

Severity: CRITICAL

Confidence: 80%

Category: Application Crash / Dependency Failure

Resource:

Cluster

Namespace

Pod

Container

Node

Summary:

...

Observed Facts:

...

Evidence:

...

Probable Causes:

...

Recommended Actions:

...

Investigation Commands:

...

```

The final working pipeline is:

``` text

EKS

 ↓

CloudWatch

 ↓

Incident Lambda

 ↓

API Gateway

 ↓

n8n

 ↓

Kubernetes Context Lambda/API

 ↓

AI SRE Analysis

 ↓

Structured JSON

 ↓

Severity Routing

 ↓

HTML Email

 ↓

Gmail

```

---

# 21. Multiple test incidents

## Missing configuration

``` bash

kubectl apply -f - <<'EOF'

apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-config-failure
  namespace: n8n-demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-config-failure
  template:
    metadata:
      labels:
        app: test-config-failure
    spec:
      containers:
        - name: app
          image: public.ecr.aws/docker/library/alpine:3.20
          command: ["/bin/sh", "-c"]
          args:
            - |
              echo "INFO application starting"
              sleep 2
              echo "INFO loading application configuration"
              sleep 2
              echo "ERROR required environment variable DATABASE_URL is missing"
              echo "ERROR configuration validation failed"
              echo "CRITICAL application startup failed"
              exit 1

EOF

```

## Permission failure

``` bash

kubectl apply -f - <<'EOF'

apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-permission-failure
  namespace: n8n-demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-permission-failure
  template:
    metadata:
      labels:
        app: test-permission-failure
    spec:
      containers:
        - name: app
          image: public.ecr.aws/docker/library/alpine:3.20
          command: ["/bin/sh", "-c"]
          args:
            - |
              echo "INFO application starting"
              sleep 2
              echo "INFO loading application configuration"
              sleep 2
              echo "ERROR permission denied while reading application configuration"
              echo "ERROR unable to initialize application"
              echo "CRITICAL application startup failed"
              exit 1

EOF

```

## Upstream timeout

``` bash

kubectl apply -f - <<'EOF'

apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-upstream-timeout
  namespace: n8n-demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-upstream-timeout
  template:
    metadata:
      labels:
        app: test-upstream-timeout
    spec:
      containers:
        - name: app
          image: public.ecr.aws/docker/library/alpine:3.20
          command: ["/bin/sh", "-c"]
          args:
            - |
              echo "INFO application starting"
              sleep 2
              echo "INFO connecting to upstream service"
              sleep 2
              echo "ERROR upstream API request timed out"
              echo "ERROR dependency health check failed"
              echo "CRITICAL application startup failed"
              exit 1

EOF

```

Verify:

``` bash
kubectl get pods -n n8n-demo
```

Then execute the n8n workflow manually.

---

# 22. API testing

Incident API:

``` bash

curl -s \
  -H "Authorization: Bearer $N8N_API_TOKEN" \
  "https://YOUR_INCIDENT_API_ID.execute-api.ap-south-1.amazonaws.com/incidents" \
  | python3 -m json.tool

```

Kubernetes context:

``` bash

export POD_NAME=$(kubectl get pods \
  -n n8n-demo \
  -l app=log-failure-demo \
  -o jsonpath='{.items[0].metadata.name}')

```

Then:

``` bash

curl -s \
  -H "Authorization: Bearer $N8N_API_TOKEN" \
  "https://YOUR_CONTEXT_API_ID.execute-api.ap-south-1.amazonaws.com/kubernetes-context?namespace=n8n-demo&pod=$POD_NAME&container=app" \
  | python3 -m json.tool

```

---

# 23. Troubleshooting

### ImagePullBackOff

``` bash
kubectl describe pod POD_NAME -n n8n-demo
```

Check private subnet routing/NAT connectivity.

### CrashLoopBackOff

``` bash

kubectl logs POD_NAME -n n8n-demo
kubectl logs POD_NAME --previous -n n8n-demo
kubectl describe pod POD_NAME -n n8n-demo

```

`CrashLoopBackOff` is a restart/backoff condition, not necessarily the root cause.

### CloudWatch logs missing

``` bash

aws logs describe-log-groups \
  --log-group-name-prefix "/aws/containerinsights" \
  --region ap-south-1

```

### Lambda AccessDenied

Verify:

``` text

logs:StartQuery
logs:GetQueryResults

```

and the correct log-group ARN.

### API 401

Verify the bearer token and authorizer environment variable.

### Kubernetes context 403

Verify:

-   IAM role
-   EKS access entry
-   EKS access policy
-   namespace scope
-   requested namespace/pod

### AI structured output error

Verify:

-   Structured Output Parser is connected.
-   JSON example is valid.
-   `Require Specific Output Format` is enabled.
-   AI model credential is valid.
-   `Normalize AI Output` handles the `output` wrapper.

### Email failure

Verify:

-   Gmail OAuth credential
-   recipient
-   subject expression
-   HTML expression
-   n8n execution output

---

# 24. Security model

Use dedicated IAM roles:

``` text

n8n-cloudwatch-reader-role
n8n-eks-context-reader-role

```

Never commit:

``` text

AWS keys
API tokens
OpenAI keys
Gmail credentials
OAuth client secrets
App passwords

```

Prefer:

``` text

IAM roles
n8n Credentials
AWS Secrets Manager

```

The APIs should remain authenticated.
The EKS context Lambda should remain read-only.

---

# 25. AI safety model

The AI receives evidence and generates analysis.
It should not have unrestricted infrastructure execution privileges.

Preferred model:

``` text

AI

 ↓

Diagnosis

 ↓

Recommendation

 ↓

Human review

 ↓

Approved action

 ↓

Controlled automation

 ↓

Verification

```

Investigation commands should be read-only:

``` bash

kubectl describe pod ...

kubectl logs ...

kubectl get pods ...

kubectl get events ...

kubectl get services ...

```

Do not automatically execute destructive commands.

---

# 26. Key technologies

### AWS

-   Amazon EKS
-   EKS Auto Mode
-   IAM
-   EKS Access Entries
-   CloudWatch Logs
-   CloudWatch Observability
-   Lambda
-   API Gateway
-   VPC
-   NAT Gateway

### Kubernetes

-   Deployments
-   Pods
-   Container lifecycle
-   CrashLoopBackOff
-   Container exit codes
-   Kubernetes Events
-   Pod logs
-   Kubernetes API
-   EKS authentication

### DevOps/SRE

-   Incident detection
-   Observability
-   Log analysis
-   Root-cause analysis
-   Severity classification
-   Incident notification
-   Least privilege
-   Failure simulation
-   Read-only investigation
-   Controlled remediation

### Automation

-   n8n
-   REST APIs
-   JavaScript transformations
-   Conditional routing
-   JSON normalization
-   Gmail OAuth

### AI

-   AI Agent
-   Structured output
-   Evidence-based analysis
-   Confidence scoring
-   Hypothesis generation
-   Investigation recommendations
-   Safe remediation recommendations

---

# 27. Cleanup

Delete test deployments:

``` bash

kubectl delete deployment \

  test-config-failure \

  test-permission-failure \

  test-upstream-timeout \

  -n n8n-demo

```

Delete the original controlled failure:

``` bash

kubectl delete deployment \

  log-failure-demo \

  -n n8n-demo

```

Delete the namespace:

``` bash

kubectl delete namespace n8n-demo

```

For complete teardown, remove the lab's:

-   Lambda functions
-   API Gateway APIs
-   IAM roles/policies
-   NAT Gateway
-   route-table changes
-   EKS cluster
-   VPC resources

Be careful: NAT Gateway, EKS, and related resources can incur AWS charges.

---

# 28. Final architecture summary

``` text

                         ┌─────────────────────┐

                         │     Amazon EKS      │

                         │                     │

                         │  Application Pods   │

                         └──────────┬──────────┘

                                    │

                                    │ Logs

                                    ▼

                         ┌─────────────────────┐

                         │   CloudWatch Logs   │

                         │ Container Insights  │

                         └──────────┬──────────┘

                                    │

                                    ▼

                         ┌─────────────────────┐

                         │ Incident Reader     │

                         │ Lambda              │

                         └──────────┬──────────┘

                                    │

                                    ▼

                         ┌─────────────────────┐

                         │ API Gateway         │

                         │ /incidents          │

                         └──────────┬──────────┘

                                    │

                                    ▼

                   ┌────────────────────────────────┐

                   │            n8n Cloud            │

                   │                                │

                   │ Parse → Deduplicate → Normalize│

                   │          ↓                     │

                   │ Kubernetes Context              │

                   │          ↓                     │

                   │ AI Incident Analysis            │

                   │          ↓                     │

                   │ Severity Routing                │

                   └───────────────┬────────────────┘

                                   │

                     ┌─────────────┴─────────────┐

                     │                           │

                     ▼                           ▼

          ┌─────────────────────┐      ┌──────────────────┐

          │ EKS Context Lambda  │      │ OpenAI Model     │

          │                     │      │                  │

          │ Pod status          │      │ Diagnosis        │

          │ Restart count       │      │ Evidence         │

          │ Exit code           │      │ Causes           │

          │ Logs                │      │ Actions          │

          │ Events              │      │ Confidence       │

          └──────────┬──────────┘      └────────┬─────────┘

                     │                          │

                     └──────────┬───────────────┘

                                │

                                ▼

                       ┌────────────────────┐

                       │ Structured AI JSON │

                       └─────────┬──────────┘

                                 │

                                 ▼

                       ┌────────────────────┐

                       │ HTML Email         │

                       │ Gmail OAuth        │

                       └────────────────────┘

```

---

## Final outcome

The project demonstrates an end-to-end:

``` text

AWS Observability

        \+

Kubernetes Runtime Context

        \+

Workflow Automation

        \+

AI Incident Analysis

        \+

Secure API Integration

        \+

Automated Notification

```

Core principle:

``` text

Evidence first → AI analysis second → human-controlled action third
```
<img width="1341" height="566" alt="sample-mail" src="https://github.com/user-attachments/assets/503ea1a8-485d-4f82-9b55-323da919206e" />
