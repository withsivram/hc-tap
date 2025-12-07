#!/bin/bash
# Redeploy both API and Dashboard with fixes

set -e

echo "🚀 Redeploying HC-TAP Services with Fixes"
echo "=========================================="
echo ""
echo "Fixes:"
echo "  • API: Cloud-aware health check"
echo "  • Dashboard: Load entities from S3"
echo ""

AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="099200121087"
ECR_BASE="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/hc-tap"

# Login to ECR once
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push API
echo ""
echo "1️⃣  Building API image (AMD64)..."
docker build --platform linux/amd64 -t hc-tap-api:latest -f Dockerfile.api . > /dev/null 2>&1 || {
    echo "❌ API build failed"
    exit 1
}
docker tag hc-tap-api:latest $ECR_BASE/api:latest-dev
echo "   ✓ API built"

echo "   Pushing API to ECR..."
docker push $ECR_BASE/api:latest-dev > /dev/null 2>&1
echo "   ✓ API pushed"

# Build and push Dashboard
echo ""
echo "2️⃣  Building Dashboard image (AMD64)..."
docker build --platform linux/amd64 -t hc-tap-dashboard:latest -f Dockerfile.dashboard . > /dev/null 2>&1 || {
    echo "❌ Dashboard build failed"
    exit 1
}
docker tag hc-tap-dashboard:latest $ECR_BASE/dashboard:latest-dev
echo "   ✓ Dashboard built"

echo "   Pushing Dashboard to ECR..."
docker push $ECR_BASE/dashboard:latest-dev > /dev/null 2>&1
echo "   ✓ Dashboard pushed"

# Update ECS services
echo ""
echo "3️⃣  Updating ECS services..."
CLUSTER=$(aws ecs list-clusters --region $AWS_REGION --query "clusterArns[?contains(@, 'HcTapStack')]" --output text)

# Update API service
API_SERVICE=$(aws ecs list-services --cluster $CLUSTER --region $AWS_REGION --query "serviceArns[?contains(@, 'ApiService')]" --output text)
aws ecs update-service \
    --cluster $CLUSTER \
    --service $API_SERVICE \
    --force-new-deployment \
    --region $AWS_REGION > /dev/null
echo "   ✓ API service updating"

# Update Dashboard service
DASH_SERVICE=$(aws ecs list-services --cluster $CLUSTER --region $AWS_REGION --query "serviceArns[?contains(@, 'DashboardService')]" --output text)
aws ecs update-service \
    --cluster $CLUSTER \
    --service $DASH_SERVICE \
    --force-new-deployment \
    --region $AWS_REGION > /dev/null
echo "   ✓ Dashboard service updating"

echo ""
echo "✅ Deployment initiated!"
echo ""
echo "⏳ Services are updating (takes ~3-5 minutes)..."
echo ""
echo "📊 To check status:"
echo "   aws ecs describe-services --cluster \$CLUSTER --services $API_SERVICE $DASH_SERVICE --region $AWS_REGION --query 'services[*].[serviceName,deployments[0].status]'"
echo ""
echo "🧪 Once deployed, test:"
echo "   API Health:    curl http://HcTapS-ApiSe-W4A6277ppDFW-1985105748.us-east-1.elb.amazonaws.com/health"
echo "   Dashboard:     http://HcTapS-Dashb-sA1M6VoIpRJL-250085734.us-east-1.elb.amazonaws.com"
echo ""
echo "Expected: Dashboard should now show 5,421 entities!"
