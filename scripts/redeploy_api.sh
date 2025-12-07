#!/bin/bash
# Quick redeploy script for API with updated health check

set -e

echo "🚀 Redeploying API with improved health check..."
echo ""

AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="099200121087"
ECR_REPO="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/hc-tap/api"

# Build for AMD64 (required for Fargate)
echo "1️⃣  Building Docker image for AMD64..."
docker build --platform linux/amd64 -t hc-tap-api:latest -f Dockerfile.api . || {
    echo "❌ Docker build failed"
    exit 1
}

# Tag for ECR
echo "2️⃣  Tagging image..."
docker tag hc-tap-api:latest $ECR_REPO:latest-dev

# Login to ECR
echo "3️⃣  Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO

# Push to ECR
echo "4️⃣  Pushing to ECR..."
docker push $ECR_REPO:latest-dev

# Force ECS service update
echo "5️⃣  Updating ECS service..."
CLUSTER=$(aws ecs list-clusters --region $AWS_REGION --query "clusterArns[?contains(@, 'HcTapStack')]" --output text)
SERVICE=$(aws ecs list-services --cluster $CLUSTER --region $AWS_REGION --query "serviceArns[?contains(@, 'ApiService')]" --output text)

aws ecs update-service \
    --cluster $CLUSTER \
    --service $SERVICE \
    --force-new-deployment \
    --region $AWS_REGION > /dev/null

echo "✅ Deployment initiated!"
echo ""
echo "⏳ Service is updating (takes ~2-3 minutes)..."
echo ""
echo "To check status:"
echo "  aws ecs describe-services --cluster \$CLUSTER --services \$SERVICE --region $AWS_REGION"
echo ""
echo "Once deployed, test:"
echo "  curl http://HcTapS-ApiSe-W4A6277ppDFW-1985105748.us-east-1.elb.amazonaws.com/health"
