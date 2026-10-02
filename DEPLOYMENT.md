# Deployment Package

This folder contains the deployment artifacts for **n8n EKS Incident AI**.

## Contents

```text
lambda-packages/
├── n8n-api-authorizer.zip
├── n8n-cloudwatch-incident-reader.zip
└── n8n-eks-context-reader.zip

iam/
├── n8n-cloudwatch-reader-policy.json
└── n8n-eks-context-reader-policy.json

scripts/
└── deploy-lambda-code.sh
```

## Deployment order

1. Create the Lambda execution roles and attach the AWS managed `AWSLambdaBasicExecutionRole`.
2. Attach the supplied IAM policies to the corresponding roles.
3. Create/update:
   - `n8n-cloudwatch-incident-reader`
   - `n8n-eks-context-reader`
   - `n8n-api-authorizer`
4. Configure the Lambda environment variables and handlers shown in the main README.
5. Configure EKS access entry for `n8n-eks-context-reader-role` with `AmazonEKSViewPolicy`, scoped to `n8n-demo`.
6. Configure API Gateway routes and the bearer-token authorizer.
7. Configure the n8n workflow and Gmail OAuth credential.

## Important

The ZIP files contain the Lambda source code and are intended to be deployed as Lambda function code packages. Do not commit live bearer tokens, OAuth secrets, or other credentials.

The supplied policies contain the reference environment used by the project (`ap-south-1`, account `5@0###14**7#`, cluster `n8n-eks-lab`). Update them for another AWS account/cluster before deployment.

See the repository README for the complete end-to-end replication guide.
