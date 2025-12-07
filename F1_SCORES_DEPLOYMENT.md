# 🎯 Adding F1 Scores to Cloud Deployment

**Status:** Deployment in progress  
**Time:** 12:00 AM

---

## ✅ What Was Done

### 1. **Uploaded Gold Data to S3** ✅
```bash
aws s3 cp gold/gold_LOCAL.jsonl s3://hc-tap-enriched-entities/gold/gold_LOCAL.jsonl
```

- 56 gold entities uploaded
- 14 annotated notes
- Location: `s3://hc-tap-enriched-entities/gold/gold_LOCAL.jsonl`

### 2. **Modified Cloud ETL** ✅

Added evaluation logic to `services/etl/etl_cloud.py`:

**New Features:**
- Load gold standard from S3
- Calculate F1 scores (exact & relaxed)
- Calculate intersection F1 scores
- Include metrics in manifest

**Functions Added:**
```python
- load_gold_from_s3()  # Load gold entities
- normalize_text()      # Text normalization
- spans_overlap()       # Check span overlap
- matchable()           # Check if entities match
- greedy_match()        # 1:1 entity matching
- prf1()                # Precision, Recall, F1
- evaluate()            # Calculate F1 scores
- filter_by_notes()     # Filter entities by note
```

**Manifest Now Includes:**
```json
{
  "f1_exact_micro": 0.XXX,
  "f1_relaxed_micro": 0.XXX,
  "f1_exact_micro_intersection": 0.XXX,
  "f1_relaxed_micro_intersection": 0.XXX
}
```

### 3. **Committed & Pushed** ✅
- Commit: `85a7a15`
- Message: "Add F1 score evaluation to cloud ETL"
- GitHub Actions: Building ETL image now...

---

## 🚀 Next Steps

### Step 1: Wait for GitHub Actions (5-8 min)
The workflow will:
1. Build new ETL Docker image with evaluation code
2. Push to ECR as `hc-tap/etl:latest-dev`
3. Deploy CDK (ETL task definition updated)

### Step 2: Trigger Cloud ETL
Once deployment completes, run:
```bash
bash scripts/trigger_etl.sh
```

This will:
- Run ETL task with new evaluation code
- Load gold data from S3
- Calculate F1 scores
- Write updated manifest to S3

### Step 3: Verify F1 Scores
Check the updated manifest:
```bash
aws s3 cp s3://hc-tap-enriched-entities/runs/latest.json - | jq .
```

Expected:
```json
{
  "run_id": "cloud-latest",
  "f1_exact_micro": 0.431,        ← Should match localhost!
  "f1_relaxed_micro": 0.XXX,
  "f1_exact_micro_intersection": 0.XXX,
  "f1_relaxed_micro_intersection": 0.XXX,
  ...
}
```

### Step 4: Check Dashboard
Open dashboard and verify F1 scores display:
```bash
open http://HcTapS-Dashb-sA1M6VoIpRJL-250085734.us-east-1.elb.amazonaws.com
```

Expected:
- Strict F1: Should show actual value (not 0.000)
- Relaxed F1: Should show actual value
- Intersection F1: Should show actual value

---

## 📊 What This Changes

| Before | After |
|--------|-------|
| F1 Scores: 0.0 (hardcoded) | F1 Scores: Calculated from gold data |
| No evaluation in cloud | Full evaluation matching localhost |
| Cloud ≠ Localhost behavior | Cloud = Localhost behavior ✅ |

---

## ⏰ Timeline

| Time | Action |
|------|--------|
| 12:00 AM | Code committed & pushed |
| 12:05 AM | GitHub Actions building |
| ~12:08 AM | ETL image pushed to ECR |
| ~12:10 AM | CDK deployment complete |
| **12:10 AM** | ⏰ **Ready to run ETL with evaluation** |

---

## 🎯 Expected Results

After running ETL with new code:

### Manifest Will Show:
```json
{
  "run_id": "cloud-latest",
  "note_count": 4966,
  "entity_count": 5421,
  "f1_exact_micro": 0.431,  ← From localhost: 43.1%
  "f1_relaxed_micro": 0.XXX,
  "f1_exact_micro_intersection": 0.XXX,
  "f1_relaxed_micro_intersection": 0.XXX
}
```

### Dashboard Will Show:
- KPI — Strict F1: **0.431** (43.1%)
- KPI — Relaxed F1: Actual calculated value
- KPI — Intersection F1: Actual calculated values

**Just like localhost!** ✅

---

## 📝 Commands Reference

### Check GitHub Actions Status
```bash
gh run list --limit 1
```

### Trigger ETL After Deployment
```bash
bash scripts/trigger_etl.sh
```

### Check ETL Task Status
```bash
# Get cluster ARN
CLUSTER=$(aws ecs list-clusters --query 'clusterArns[0]' --output text)

# List tasks
aws ecs list-tasks --cluster "$CLUSTER" --family HcTapStack-EtlTaskDef

# Get task status
aws ecs describe-tasks --cluster "$CLUSTER" --tasks TASK_ARN
```

### Check Manifest
```bash
aws s3 cp s3://hc-tap-enriched-entities/runs/latest.json - | jq .
```

### Force Dashboard Restart (if needed)
```bash
aws ecs update-service --force-new-deployment \
  --cluster HcTapStack-HcTapCluster7E2888D7-mDjWx5ME4lxG \
  --service HcTapStack-DashboardService4A4198DA-BbF2TLrVEnLf
```

---

**Status:** 🚀 **Waiting for GitHub Actions to complete** (~8 minutes)

Then: Run ETL → Verify manifest → Check dashboard!
