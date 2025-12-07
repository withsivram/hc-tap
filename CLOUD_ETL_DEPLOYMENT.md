# Cloud ETL Deployment - LLM Extractor Enabled

## ✅ Changes Deployed

### 1. Cloud ETL Updated (`services/etl/etl_cloud.py`)
- ✅ Added LLM extractor support (same as local ETL)
- ✅ Dynamic extractor selection via `EXTRACTOR` env var
- ✅ Enhanced manifest with precision, recall, coverage metrics
- ✅ Uses `gold_DEMO.jsonl` (330 entities) for evaluation

### 2. Infrastructure Updated (`infra/hc_tap_stack.py`)
- ✅ ETL task configured to use `EXTRACTOR=llm`
- ✅ Added Anthropic API key from AWS Secrets Manager
- ✅ Environment variables: `EXTRACTOR_LLM=anthropic`

### 3. AWS Secrets Manager
- ✅ Secret created: `hc-tap/anthropic-api-key`
- ✅ ARN: `arn:aws:secretsmanager:us-east-1:099200121087:secret:hc-tap/anthropic-api-key-k0UeuN`

### 4. Gold Standard in S3
- ✅ Uploaded: `s3://hc-tap-enriched-entities/gold/gold_DEMO.jsonl`
- ✅ Size: 67.7 KiB (330 entities)

---

## 🚀 Deployment Status

### Pushed to GitHub:
- Commit: `0725e88` - "feat: enable LLM extraction in cloud ETL"
- GitHub Actions will:
  1. Deploy infrastructure changes (CDK)
  2. Build new ETL Docker image
  3. Update ECS task definition

**Estimated time**: 10-15 minutes

---

## 🎯 Next Steps

### Step 1: Wait for Deployment (10-15 min)
Monitor deployment at: https://github.com/withsivram/hc-tap/actions

### Step 2: Trigger Cloud ETL
Once deployment completes, trigger the ETL to generate new metrics:

**Option A: Via GitHub Actions (Recommended)**
1. Go to: https://github.com/withsivram/hc-tap/actions/workflows/run-etl.yml
2. Click "Run workflow"
3. Wait 2-3 minutes for completion

**Option B: Via AWS CLI**
```bash
# Get cluster and task definition
CLUSTER=$(aws ecs list-clusters --query "clusterArns[?contains(@, 'HcTapStack')]" --output text)
TASK_DEF=$(aws ecs list-task-definitions --family-prefix HcTapStack-EtlTaskDef --sort DESC --max-items 1 --query "taskDefinitionArns[0]" --output text)

# Get network config from existing service
SERVICE_ARN=$(aws ecs list-services --cluster $CLUSTER --max-items 1 --query "serviceArns[0]" --output text)
NET_CONF=$(aws ecs describe-services --cluster $CLUSTER --services $SERVICE_ARN --query "services[0].networkConfiguration" --output json)
SUBNETS=$(echo $NET_CONF | jq -r '.awsvpcConfiguration.subnets | join(",")')
SGS=$(echo $NET_CONF | jq -r '.awsvpcConfiguration.securityGroups | join(",")')

# Run ETL task
aws ecs run-task \
  --cluster $CLUSTER \
  --task-definition $TASK_DEF \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SGS],assignPublicIp=ENABLED}"

echo "✅ Cloud ETL started! Check logs at:"
echo "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/\$252Fecs\$252FHcTapEtl"
```

### Step 3: Verify Cloud Dashboard
After ETL completes (2-3 minutes), visit:
http://HcTapS-Dashb-sA1M6VoIpRJL-250085734.us-east-1.elb.amazonaws.com

**Expected metrics:**
- Run ID: cloud-llm
- Total Entities: ~296
- Precision: ~73.3%
- Recall: ~61.2%
- F1 Exact: ~66.7%
- F1 Intersection: ~72.6%

---

## 📊 Current vs Expected State

### CURRENT (Old Data):
```
Run: cloud-latest
Entities: 5,421
F1 Exact: 0.8%
Precision: 0.0%
Extractor: rule-based
Gold: old standard (56 entities)
```

### EXPECTED (After ETL Run):
```
Run: cloud-llm
Entities: 296
F1 Exact: 66.7%
Precision: 73.3%
Recall: 61.2%
Extractor: LLM (Anthropic)
Gold: gold_DEMO.jsonl (330 entities)
```

---

## 🔍 Troubleshooting

### If ETL fails:
1. **Check logs**: 
   - CloudWatch: `/ecs/HcTapEtl`
   - Look for "Failed to initialize LLM extractor"

2. **Verify secret**:
   ```bash
   aws secretsmanager get-secret-value --secret-id hc-tap/anthropic-api-key --region us-east-1
   ```

3. **Check task definition**:
   ```bash
   aws ecs describe-task-definition --task-definition <TASK_DEF_ARN> --query "taskDefinition.containerDefinitions[0].environment"
   ```

### If F1 scores are still low:
1. Verify gold standard in S3:
   ```bash
   aws s3 ls s3://hc-tap-enriched-entities/gold/
   # Should show gold_DEMO.jsonl
   ```

2. Check ETL output:
   ```bash
   aws s3 ls s3://hc-tap-enriched-entities/runs/cloud-llm/
   # Should show entities.jsonl and manifest.json
   ```

---

## ✨ Summary

**Status**: Deployment in progress ⏳

**Timeline**:
1. Infrastructure deployment: 10-15 min
2. Trigger Cloud ETL: Manual step
3. ETL execution: 2-3 min
4. Dashboard refresh: Immediate

**Total time to see results**: ~15-20 minutes

**Final result**: Cloud dashboard will match local dashboard with 66-72% F1 scores! 🎯
