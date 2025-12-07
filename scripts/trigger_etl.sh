#!/bin/bash
set -e

# Trigger ETL Task on AWS ECS
# This script runs the same logic as the GitHub Actions workflow locally

echo "=== HC-TAP Cloud ETL Trigger ==="
echo ""

AWS_REGION=${AWS_REGION:-us-east-1}
RAW_BUCKET_NAME=${RAW_BUCKET:-hc-tap-raw-notes}
ENRICHED_BUCKET_NAME=${ENRICHED_BUCKET:-hc-tap-enriched-entities}
RUN_ID=${RUN_ID:-cloud-latest}

echo "Configuration:"
echo "  Region: $AWS_REGION"
echo "  Raw Bucket: $RAW_BUCKET_NAME"
echo "  Enriched Bucket: $ENRICHED_BUCKET_NAME"
echo "  Run ID: $RUN_ID"
echo ""

# Find the ETL Task Definition
echo "Finding ETL Task Definition..."
TASK_DEF_FAMILY=$(aws ecs list-task-definition-families \
  --status ACTIVE \
  --region $AWS_REGION \
  --query "families[?contains(@, 'EtlTaskDef')]" \
  --output text | head -n 1)

if [ -z "$TASK_DEF_FAMILY" ]; then
  echo "❌ Error: Could not find EtlTaskDef family."
  echo "Available task definitions:"
  aws ecs list-task-definition-families --status ACTIVE --region $AWS_REGION
  exit 1
fi

TASK_DEF=$(aws ecs list-task-definitions \
  --family-prefix $TASK_DEF_FAMILY \
  --sort DESC \
  --max-items 1 \
  --region $AWS_REGION \
  --query "taskDefinitionArns[0]" \
  --output text)

echo "✓ Task Definition: $TASK_DEF"

# Find Cluster
echo "Finding ECS Cluster..."
CLUSTER=$(aws ecs list-clusters \
  --region $AWS_REGION \
  --query "clusterArns[?contains(@, 'HcTapStack')]" \
  --output text)

if [ -z "$CLUSTER" ]; then
  echo "❌ Error: Could not find HcTapStack cluster."
  echo "Available clusters:"
  aws ecs list-clusters --region $AWS_REGION
  exit 1
fi

echo "✓ Cluster: $CLUSTER"

# Get network configuration from existing service
echo "Getting network configuration..."
SERVICE_ARN=$(aws ecs list-services \
  --cluster $CLUSTER \
  --region $AWS_REGION \
  --max-items 1 \
  --query "serviceArns[0]" \
  --output text)

NET_CONF=$(aws ecs describe-services \
  --cluster $CLUSTER \
  --services $SERVICE_ARN \
  --region $AWS_REGION \
  --query "services[0].networkConfiguration" \
  --output json)

SUBNETS=$(echo $NET_CONF | jq -r '.awsvpcConfiguration.subnets | join(",")')
SGS=$(echo $NET_CONF | jq -r '.awsvpcConfiguration.securityGroups | join(",")')

echo "✓ Network configured"
echo ""

# Run the ETL Task
echo "Starting ETL Task..."
TASK_ARN=$(aws ecs run-task \
  --cluster $CLUSTER \
  --task-definition $TASK_DEF \
  --launch-type FARGATE \
  --region $AWS_REGION \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SGS],assignPublicIp=ENABLED}" \
  --overrides "{\"containerOverrides\":[{\"name\":\"EtlContainer\",\"command\":[\"python\",\"services/etl/etl_cloud.py\"],\"environment\":[{\"name\":\"RAW_BUCKET\",\"value\":\"$RAW_BUCKET_NAME\"},{\"name\":\"ENRICHED_BUCKET\",\"value\":\"$ENRICHED_BUCKET_NAME\"},{\"name\":\"RUN_ID\",\"value\":\"$RUN_ID\"},{\"name\":\"HC_TAP_ENV\",\"value\":\"cloud\"}]}]}" \
  --query "tasks[0].taskArn" \
  --output text)

if [ -z "$TASK_ARN" ]; then
  echo "❌ Error: Failed to start task."
  exit 1
fi

echo "✓ Task Started: $TASK_ARN"
echo ""
echo "Waiting for task to complete (this may take 5-10 minutes for 4966 notes)..."
echo ""

# Wait for task to stop
aws ecs wait tasks-stopped \
  --cluster $CLUSTER \
  --tasks $TASK_ARN \
  --region $AWS_REGION

# Check task exit code
TASK_STATUS=$(aws ecs describe-tasks \
  --cluster $CLUSTER \
  --tasks $TASK_ARN \
  --region $AWS_REGION \
  --query "tasks[0].containers[0].exitCode" \
  --output text)

echo ""
echo "=== ETL Task Completed ==="
echo "Exit Code: $TASK_STATUS"
echo ""

if [ "$TASK_STATUS" != "0" ]; then
  echo "❌ Task failed with exit code $TASK_STATUS"
fi

# Fetch and display logs
echo "Fetching logs..."
LOG_STREAM=$(aws logs describe-log-streams \
  --log-group-name /ecs/HcTapEtl \
  --region $AWS_REGION \
  --order-by LastEventTime \
  --descending \
  --limit 1 \
  --query "logStreams[0].logStreamName" \
  --output text 2>/dev/null || echo "")

if [ -n "$LOG_STREAM" ] && [ "$LOG_STREAM" != "None" ]; then
  echo ""
  echo "=== Recent ETL Logs ==="
  aws logs get-log-events \
    --log-group-name /ecs/HcTapEtl \
    --log-stream-name "$LOG_STREAM" \
    --region $AWS_REGION \
    --limit 50 \
    --query "events[*].message" \
    --output text
else
  echo "⚠️  No logs found in /ecs/HcTapEtl"
fi

# Verify output in S3
echo ""
echo "=== Verifying S3 Output ==="
echo "Checking s3://$ENRICHED_BUCKET_NAME/runs/latest.json..."

if aws s3 ls s3://$ENRICHED_BUCKET_NAME/runs/latest.json --region $AWS_REGION > /dev/null 2>&1; then
  echo "✓ Manifest exists"
  echo ""
  echo "Manifest contents:"
  aws s3 cp s3://$ENRICHED_BUCKET_NAME/runs/latest.json - --region $AWS_REGION
  echo ""
else
  echo "❌ Manifest not found. ETL may have failed."
fi

echo ""
echo "=== Next Steps ==="
echo "1. Verify dashboard shows data:"
echo "   Dashboard URL: Check your deployment outputs"
echo ""
echo "2. Test API health:"
echo "   curl <API_URL>/health"
echo ""
echo "3. If data doesn't appear, check:"
echo "   - S3 bucket contents: aws s3 ls s3://$ENRICHED_BUCKET_NAME/runs/ --recursive"
echo "   - CloudWatch logs: /ecs/HcTapEtl"
echo "   - IAM permissions for ECS task role"
