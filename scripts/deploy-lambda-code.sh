#!/usr/bin/env bash
set -euo pipefail

# Adjust these variables for your environment.
REGION="${AWS_REGION:-ap-south-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-520701146276}"
CLUSTER_NAME="${EKS_CLUSTER_NAME:-n8n-eks-lab}"

CLOUDWATCH_ROLE="n8n-cloudwatch-reader-role"
CONTEXT_ROLE="n8n-eks-context-reader-role"

echo "Region: $REGION"
echo "Account: $ACCOUNT_ID"
echo "Cluster: $CLUSTER_NAME"

# This script creates/updates the Lambda deployment artifacts only.
# API Gateway routes/authorizers and n8n credentials are configured separately
# as described in the main README.

aws iam put-role-policy \
  --role-name "$CLOUDWATCH_ROLE" \
  --policy-name n8n-cloudwatch-reader-inline \
  --policy-document file://../iam/n8n-cloudwatch-reader-policy.json \
  --region "$REGION"

aws iam put-role-policy \
  --role-name "$CONTEXT_ROLE" \
  --policy-name n8n-eks-context-reader-inline \
  --policy-document file://../iam/n8n-eks-context-reader-policy.json \
  --region "$REGION"

aws lambda update-function-code \
  --function-name n8n-cloudwatch-incident-reader \
  --zip-file fileb://../lambda-packages/n8n-cloudwatch-incident-reader.zip \
  --region "$REGION"

aws lambda update-function-code \
  --function-name n8n-eks-context-reader \
  --zip-file fileb://../lambda-packages/n8n-eks-context-reader.zip \
  --region "$REGION"

aws lambda update-function-code \
  --function-name n8n-api-authorizer \
  --zip-file fileb://../lambda-packages/n8n-api-authorizer.zip \
  --region "$REGION"

echo
echo "Lambda deployment packages uploaded successfully."
echo "Next: configure API Gateway, EKS access entries, and n8n as described in README.md."
