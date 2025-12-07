#!/bin/bash
echo "🔍 Checking ECS Deployment Status..."
echo ""

CLUSTER="HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG"
DASHBOARD_SVC="HcTapStack-DashboardService4A4198DA-BbF2TLrVEnLf"
API_SVC="HcTapStack-ApiService199661B5-urAVIcCzyEsP"

echo "📊 Dashboard Service:"
aws ecs describe-services \
  --cluster "$CLUSTER" \
  --service "$DASHBOARD_SVC" \
  --query 'services[0].deployments[*].[status,runningCount,desiredCount]' \
  --output table

echo ""
echo "📊 API Service:"
aws ecs describe-services \
  --cluster "$CLUSTER" \
  --service "$API_SVC" \
  --query 'services[0].deployments[*].[status,runningCount,desiredCount]' \
  --output table

echo ""
echo "🕐 Dashboard Task Started At:"
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER" \
  --service-name "$DASHBOARD_SVC" \
  --query 'taskArns[0]' --output text)
  
if [ -n "$TASK_ARN" ]; then
  aws ecs describe-tasks \
    --cluster "$CLUSTER" \
    --tasks "$TASK_ARN" \
    --query 'tasks[0].[startedAt,lastStatus]' \
    --output table
else
  echo "⏳ No tasks running yet (containers starting...)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment complete when:"
echo "   • Only 1 deployment (PRIMARY)"
echo "   • runningCount = desiredCount = 1"
echo "   • Task started after 11:47 PM"
echo ""
echo "Run again in 30 seconds: ./check-deployment.sh"
