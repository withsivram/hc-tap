# AWS Cloud Infrastructure Review - HC-TAP

**Date:** December 6, 2025  
**Status:** Ready for deployment with bug fixes applied

---

## 📊 Infrastructure Overview

### **Architecture Components**

Your HC-TAP cloud infrastructure consists of:

1. **AWS Services:**
   - ECS Fargate (API + Dashboard services)
   - ECR (Container Registry)
   - S3 (Data storage)
   - VPC (Networking)
   - Application Load Balancers
   - CloudWatch Logs

2. **GitHub Workflows:**
   - Continuous Deployment (`.github/workflows/deploy.yml`)
   - Cloud ETL Runner (`.github/workflows/run-etl.yml`)
   - CI/Smoke Tests (`.github/workflows/ci.yml`)

3. **Docker Images:**
   - `Dockerfile.api` - FastAPI backend
   - `Dockerfile.dashboard` - Streamlit frontend
   - `Dockerfile.etl` - ETL pipeline

---

## ✅ What's Working (After Bug Fixes)

### **1. Security ✅**
- ✅ AWS credentials moved to GitHub secrets
- ✅ Workflows now use `${{ secrets.AWS_ROLE_ARN }}` and `${{ secrets.AWS_ACCOUNT_ID }}`
- ✅ S3 buckets have versioning enabled
- ✅ Proper IAM permissions for ECS tasks

### **2. Infrastructure Code ✅**
- ✅ CDK stack properly defines all resources
- ✅ ECR repositories referenced correctly
- ✅ S3 buckets created with proper lifecycle policies
- ✅ ECS services configured with load balancers
- ✅ CloudWatch logging configured for ETL

### **3. Deployment Workflow ✅**
- ✅ Docker images built for correct platforms (linux/amd64)
- ✅ ECR repos created before pushing images
- ✅ CDK deployment automated
- ✅ Proper build order (images → CDK)

---

## 🔧 Cloud Infrastructure Configuration

### **S3 Buckets**
```
hc-tap-raw-notes          → Raw clinical notes
hc-tap-enriched-entities  → Extracted entities + manifests
```

### **ECS Services**
```
API Service:
  - CPU: 256
  - Memory: 512 MB
  - Port: 8000
  - Load Balancer: Public ALB
  - Permissions: Read/Write to both S3 buckets

Dashboard Service:
  - CPU: 256
  - Memory: 512 MB  
  - Port: 8501
  - Load Balancer: Public ALB
  - Permissions: Read from enriched bucket
  - Connects to API via internal DNS

ETL Task (On-demand):
  - CPU: 512
  - Memory: 1024 MB
  - Runs via GitHub workflow
  - Logs to CloudWatch: /ecs/HcTapEtl
```

### **VPC Configuration**
```
- max_azs: 2 (Multi-AZ deployment)
- Default settings (public + private subnets)
```

---

## 🚀 Deployment Steps

### **Prerequisites**

1. **GitHub Secrets** (REQUIRED - see SECURITY_AWS_CREDENTIALS.md):
   ```
   AWS_ACCOUNT_ID = 099200121087
   AWS_ROLE_ARN = arn:aws:iam::099200121087:role/hc-tap-github-deploy-role
   ```

2. **AWS IAM Role:**
   - Must have OIDC trust relationship with GitHub
   - Needs permissions for: ECR, ECS, S3, VPC, CloudWatch, CloudFormation

### **Deploy to AWS**

```bash
# Method 1: Push to main branch (auto-deploys)
git push origin main

# Method 2: Manual deployment via GitHub UI
# Go to: Actions → Deploy to AWS → Run workflow

# Method 3: Local CDK deployment
cd infra
cdk bootstrap  # First time only
cdk deploy
```

### **Monitor Deployment**

```bash
# Watch GitHub Actions
# Go to: https://github.com/YOUR_REPO/actions

# Or use AWS CLI:
aws ecs list-services --cluster $(aws ecs list-clusters --query 'clusterArns[0]' --output text)
aws ecs describe-services --cluster CLUSTER_NAME --services SERVICE_NAME
```

---

## 🔍 Health Checks

### **After Deployment**

1. **Check ECS Services:**
   ```bash
   aws ecs list-clusters
   aws ecs list-services --cluster HcTapStack-HcTapCluster...
   ```

2. **Get Load Balancer URLs:**
   ```bash
   aws elbv2 describe-load-balancers --query 'LoadBalancers[*].[DNSName,LoadBalancerName]'
   ```

3. **Test API:**
   ```bash
   curl http://YOUR_ALB_DNS/health
   ```

4. **Test Dashboard:**
   ```
   Open: http://YOUR_DASHBOARD_ALB_DNS
   ```

5. **Check S3 Buckets:**
   ```bash
   aws s3 ls s3://hc-tap-raw-notes/
   aws s3 ls s3://hc-tap-enriched-entities/
   ```

---

## 📋 Cloud Operations

### **Run ETL in Cloud**

```bash
# Via GitHub Actions
# Go to: Actions → Run Cloud ETL → Run workflow

# This will:
# 1. Read notes from s3://hc-tap-raw-notes/
# 2. Extract entities
# 3. Write to s3://hc-tap-enriched-entities/runs/
# 4. Create manifest at runs/latest.json
```

### **Sync Data to Cloud**

```bash
# Upload notes to S3
make sync-s3

# Or manually:
aws s3 sync fixtures/notes/ s3://hc-tap-raw-notes/
```

### **View Logs**

```bash
# ETL logs
aws logs tail /ecs/HcTapEtl --follow

# API service logs
aws logs tail /ecs/ApiService --follow

# Dashboard logs
aws logs tail /ecs/DashboardService --follow
```

---

## ⚠️ Known Considerations

### **1. Costs**
- **ECS Fargate:** ~$20-40/month for 2 services running 24/7
- **NAT Gateway:** ~$30/month (created by VPC)
- **Load Balancers:** ~$20/month each (2 ALBs)
- **S3:** Minimal (<$5/month for small datasets)
- **Total:** ~$70-120/month

**Cost Optimization Ideas:**
- Consider stopping non-prod services when not in use
- Use VPC endpoints for S3 (eliminate NAT gateway costs)
- Use single ALB with path-based routing
- Consider AWS Fargate Spot for ETL tasks

### **2. Security**
- ✅ ALBs are public (internet-accessible)
- ✅ Services run in private subnets via NAT
- ⚠️  Consider adding WAF for ALBs in production
- ⚠️  Consider restricting ALB to specific IPs/ranges

### **3. Scalability**
- Current: 1 task per service (fine for MVP)
- Consider auto-scaling based on CPU/memory
- ETL runs on-demand (good for batch processing)

---

## 🐛 Issues Fixed for Cloud

All 47 bugs have been fixed, including cloud-specific ones:

- ✅ **BUG-008:** AWS credentials now use GitHub secrets
- ✅ **BUG-002:** S3 error handling prevents ETL crashes
- ✅ **BUG-012:** CORS configured for cross-origin access
- ✅ **BUG-022:** Workflow uses dynamic cluster lookup
- ✅ **BUG-047:** All dependencies pinned (reproducible builds)

---

## 📝 Next Steps

### **Immediate Actions**

1. **Add GitHub Secrets** (CRITICAL):
   ```
   Repository Settings → Secrets → Actions → New repository secret
   
   Name: AWS_ACCOUNT_ID
   Value: 099200121087
   
   Name: AWS_ROLE_ARN  
   Value: arn:aws:iam::099200121087:role/hc-tap-github-deploy-role
   ```

2. **Test Deployment:**
   ```bash
   # Push code to trigger deployment
   git push origin main
   
   # Monitor in GitHub Actions UI
   ```

3. **Verify Infrastructure:**
   ```bash
   # Check ECS cluster exists
   aws ecs list-clusters
   
   # Check services are running
   aws ecs list-services --cluster YOUR_CLUSTER_NAME
   ```

### **Post-Deployment**

1. **Get Service URLs:**
   ```bash
   aws elbv2 describe-load-balancers
   ```

2. **Upload Test Data:**
   ```bash
   make sync-s3
   ```

3. **Run Cloud ETL:**
   ```bash
   # Via GitHub Actions: Run Cloud ETL workflow
   ```

4. **Access Dashboard:**
   ```
   http://YOUR_DASHBOARD_ALB_DNS
   ```

---

## 📞 Troubleshooting

### **If Deployment Fails**

1. **Check GitHub Actions logs:**
   - Look for ECR push failures
   - Check CDK deployment errors
   - Verify AWS credentials

2. **Common Issues:**
   - **"Role not found"** → Add AWS_ROLE_ARN to secrets
   - **"Access Denied"** → Check IAM role permissions
   - **"Repository not found"** → ECR repos will be created automatically
   - **"Stack already exists"** → Update instead of create (normal)

3. **Manual Verification:**
   ```bash
   # Test AWS access
   aws sts get-caller-identity
   
   # Check ECR repos
   aws ecr describe-repositories
   
   # Check CloudFormation stack
   aws cloudformation describe-stacks --stack-name HcTapStack
   ```

---

## ✅ Ready for Cloud Deployment

Your infrastructure code is solid and all bug fixes are applied. The main blocker is adding the GitHub secrets for AWS authentication.

**Status:** 🟢 Ready to deploy once secrets are configured

Would you like help with:
1. Adding GitHub secrets?
2. Running the deployment?
3. Verifying the infrastructure after deployment?
4. Cost optimization strategies?
