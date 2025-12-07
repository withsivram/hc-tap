# 📊 Track ECS Deployment Progress

## Quick Status Check

### Option 1: Simple One-Liner (Recommended)
```bash
aws ecs describe-services \
  --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
  --services HcTapStack-DashboardService4A4198DA-BbF2TLrVEnLf HcTapStack-ApiService199661B5-urAVIcCzyEsP \
  --query 'services[*].[serviceName,deployments[*].[status,desiredCount,runningCount,createdAt]]' \
  --output table
```

**What to look for:**
- `PRIMARY` deployment with `runningCount = desiredCount` (both should be 1)
- `ACTIVE` deployment draining (will disappear when rollout completes)

---

## Step-by-Step Tracking

### 1. Check Dashboard Service Status
```bash
aws ecs describe-services \
  --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
  --service HcTapStack-DashboardService4A4198DA-BbF2TLrVEnLf \
  --query 'services[0].deployments[*].[status,runningCount,desiredCount,createdAt]' \
  --output table
```

**Expected progression:**
```
# Stage 1 (0-60 sec): New task starting
PRIMARY    0    1    2025-12-06T23:47:00
ACTIVE     1    1    2025-12-06T23:25:00

# Stage 2 (60-120 sec): New task running
PRIMARY    1    1    2025-12-06T23:47:00
ACTIVE     1    1    2025-12-06T23:25:00

# Stage 3 (120-180 sec): Old task draining
PRIMARY    1    1    2025-12-06T23:47:00

# COMPLETE (180+ sec): Only new task
PRIMARY    1    1    2025-12-06T23:47:00
```

### 2. Check API Service Status
```bash
aws ecs describe-services \
  --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
  --service HcTapStack-ApiService199661B5-urAVIcCzyEsP \
  --query 'services[0].deployments[*].[status,runningCount,desiredCount,createdAt]' \
  --output table
```

### 3. Check Running Task Timestamps
```bash
# Dashboard task
aws ecs list-tasks \
  --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
  --service-name HcTapStack-DashboardService4A4198DA-BbF2TLrVEnLf \
  --query 'taskArns[0]' --output text | xargs -I {} \
  aws ecs describe-tasks \
    --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
    --tasks {} \
    --query 'tasks[0].[startedAt,lastStatus]' \
    --output table

# API task
aws ecs list-tasks \
  --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
  --service-name HcTapStack-ApiService199661B5-urAVIcCzyEsP \
  --query 'taskArns[0]' --output text | xargs -I {} \
  aws ecs describe-tasks \
    --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
    --tasks {} \
    --query 'tasks[0].[startedAt,lastStatus]' \
    --output table
```

**What to look for:**
- `startedAt` should be **~11:48 PM or later** (after the force deployment)
- `lastStatus` should be `RUNNING`

---

## Live Monitoring (Auto-refresh)

### Watch Dashboard Deployment (Updates every 5 seconds)
```bash
watch -n 5 'aws ecs describe-services \
  --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
  --service HcTapStack-DashboardService4A4198DA-BbF2TLrVEnLf \
  --query "services[0].deployments[*].[status,runningCount,desiredCount]" \
  --output table'
```

Press `Ctrl+C` to stop watching.

---

## Quick Health Check

### Check if services are responding
```bash
# API Health
curl -s http://HcTapS-ApiSe-W4A6277ppDFW-1985105748.us-east-1.elb.amazonaws.com/health | jq .

# Dashboard (check HTTP status)
curl -I http://HcTapS-Dashb-sA1M6VoIpRJL-250085734.us-east-1.elb.amazonaws.com
```

---

## Timeline Expectations

### Typical ECS Rollout:

| Time | Status | What's Happening |
|------|--------|------------------|
| **T+0s** | Starting | Force deployment triggered |
| **T+30s** | Provisioning | New task created, container pulling image |
| **T+60s** | Starting | Container started, app initializing |
| **T+90s** | Running | Health checks passing, receiving traffic |
| **T+120s** | Draining | Old task stops receiving traffic |
| **T+180s** | Complete | Old task stopped, only new task running |

**Your deployment:**
- Started: **11:47 PM**
- Expected complete: **11:50 PM** (3 minutes)

---

## Verify New Code Is Running

### Test Dashboard (After rollout completes)
```bash
# Open in browser
open http://HcTapS-Dashb-sA1M6VoIpRJL-250085734.us-east-1.elb.amazonaws.com

# Or check HTML for changes
curl -s http://HcTapS-Dashb-sA1M6VoIpRJL-250085734.us-east-1.elb.amazonaws.com | grep -i "cloud-latest"
```

### Verify Task Is New
```bash
# Should show task started at ~11:48 PM (NOT 11:25 PM!)
aws ecs describe-tasks \
  --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
  --tasks $(aws ecs list-tasks \
    --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
    --service-name HcTapStack-DashboardService4A4198DA-BbF2TLrVEnLf \
    --query 'taskArns[0]' --output text) \
  --query 'tasks[0].[startedAt,containers[0].image]' \
  --output table
```

Expected:
```
----------------------------------------
|           DescribeTasks              |
+--------------------------------------+
|  2025-12-06T23:48:XX.XXX-05:00      |  ← NEW timestamp!
|  ...hc-tap/dashboard:latest-dev     |
+--------------------------------------+
```

---

## Troubleshooting

### If deployment is stuck
```bash
# Check events for errors
aws ecs describe-services \
  --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
  --service HcTapStack-DashboardService4A4198DA-BbF2TLrVEnLf \
  --query 'services[0].events[0:5]' \
  --output table
```

### If container fails to start
```bash
# Check CloudWatch logs
aws logs tail /ecs/HcTapDashboard --follow
```

---

## Success Indicators

### ✅ Deployment Complete When:
1. Only **ONE** deployment shows (status: PRIMARY)
2. `runningCount` = `desiredCount` = 1
3. Task `startedAt` is after 11:47 PM
4. Dashboard shows 5,421 entities
5. API returns healthy status

---

## Quick Test Script

Save this as `check-deployment.sh`:

```bash
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
echo "🕐 Dashboard Task Started:"
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER" \
  --service-name "$DASHBOARD_SVC" \
  --query 'taskArns[0]' --output text)
  
aws ecs describe-tasks \
  --cluster "$CLUSTER" \
  --tasks "$TASK_ARN" \
  --query 'tasks[0].[startedAt,lastStatus]' \
  --output table

echo ""
echo "✅ Run again in 30 seconds to check progress!"
```

Then run:
```bash
chmod +x check-deployment.sh
./check-deployment.sh
```

---

**Current Time:** 11:47 PM  
**Expected Complete:** 11:50 PM (3 minutes)  
**Check now, then again at 11:50 PM!**
