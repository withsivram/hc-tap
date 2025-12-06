# Quick Deployment Guide

## ✅ GitHub Secrets Configured!

You've successfully added:
- `AWS_ACCOUNT_ID`
- `AWS_ROLE_ARN`

---

## 🚀 Deploy Now (Choose One Method)

### **METHOD 1: Automated Deployment via GitHub Actions** (RECOMMENDED)

Run in your **local terminal**:

```bash
# Run the deployment script
bash deploy_to_aws.sh
```

This script will:
1. ✅ Verify AWS CLI is installed
2. ✅ Check your AWS credentials
3. ✅ Verify IAM role exists
4. ✅ Check existing infrastructure
5. ✅ Push code to GitHub (triggers deployment)
6. ✅ Show you where to monitor progress

---

### **METHOD 2: Manual Push to GitHub**

```bash
# In your local terminal
git push origin main
```

Then monitor at: `https://github.com/YOUR_USERNAME/YOUR_REPO/actions`

---

### **METHOD 3: Manual Trigger in GitHub**

1. Go to your GitHub repository
2. Click **Actions** tab
3. Select **Deploy to AWS** workflow
4. Click **Run workflow** button
5. Select branch: `main`
6. Click green **Run workflow** button

---

## 📊 Monitor Deployment

### In GitHub:
1. Go to: `https://github.com/YOUR_USERNAME/YOUR_REPO/actions`
2. Click on the running workflow
3. Watch the steps execute:
   - ✅ Checkout code
   - ✅ Configure AWS credentials
   - ✅ Build Docker images
   - ✅ Push to ECR
   - ✅ Deploy CDK stack

### Expected Duration:
- **Docker builds**: 5-10 minutes
- **CDK deployment**: 10-15 minutes
- **Total**: ~15-25 minutes

---

## 🔍 Verify Deployment (After GitHub Actions Completes)

Run these commands in your **local terminal**:

```bash
# 1. Check ECS cluster
aws ecs list-clusters --region us-east-1

# 2. Check running services
aws ecs list-services --cluster HcTapStack-HcTapCluster... --region us-east-1

# 3. Get Load Balancer URLs
aws elbv2 describe-load-balancers --region us-east-1 \
  --query 'LoadBalancers[*].[LoadBalancerName,DNSName]' --output table

# 4. Test API (replace with your ALB DNS)
curl http://YOUR_API_ALB_DNS/health

# 5. Check S3 buckets
aws s3 ls | grep hc-tap
```

---

## 🎯 What Gets Deployed

### AWS Resources:
- **ECS Cluster** with 2 Fargate services
- **API Service** (Port 8000) with public ALB
- **Dashboard Service** (Port 8501) with public ALB  
- **ETL Task Definition** (on-demand)
- **2 S3 Buckets** (raw + enriched)
- **3 ECR Repositories** (api, dashboard, etl images)
- **VPC** with public/private subnets
- **CloudWatch Logs** for all services

### Docker Images Built:
- `hc-tap/api:latest-dev`
- `hc-tap/dashboard:latest-dev`
- `hc-tap/etl:latest-dev`

---

## 🐛 Troubleshooting

### "AWS CLI not found"
```bash
# Install AWS CLI
brew install awscli  # macOS
# or
pip install awscli  # Python
```

### "AWS credentials not configured"
```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter region: us-east-1
```

### "Deployment failed in GitHub Actions"
1. Go to Actions tab
2. Click on the failed workflow
3. Check error messages
4. Common issues:
   - IAM role doesn't exist → Create it in AWS
   - Permission denied → Check role permissions
   - ECR push failed → Check AWS credentials in GitHub secrets

### "IAM Role not found"
The role `hc-tap-github-deploy-role` needs to exist in your AWS account with:
- Trust policy for GitHub OIDC
- Permissions for: ECR, ECS, S3, VPC, CloudWatch, CloudFormation

---

## 📱 Access Your Deployed Services

After deployment completes:

### Get URLs:
```bash
aws elbv2 describe-load-balancers --region us-east-1 \
  --query 'LoadBalancers[*].[LoadBalancerName,DNSName]' --output table
```

### Access Points:
- **API**: `http://YOUR_API_ALB_DNS/health`
- **Dashboard**: `http://YOUR_DASHBOARD_ALB_DNS`
- **API Docs**: `http://YOUR_API_ALB_DNS/docs`

---

## ⚡ Quick Start Commands

```bash
# Run deployment script (does everything)
bash deploy_to_aws.sh

# Or manually push
git push origin main

# Monitor in real-time
watch -n 5 'aws ecs describe-services --cluster HcTapStack-HcTapCluster... --services ApiService DashboardService --query "services[*].[serviceName,status,runningCount,desiredCount]" --output table'
```

---

## 📚 Additional Resources

- Full guide: `CLOUD_INFRASTRUCTURE_STATUS.md`
- Security info: `SECURITY_AWS_CREDENTIALS.md`
- Bug fixes: `BUG_FIXES_SUMMARY.md`

---

**You're ready to deploy! Run: `bash deploy_to_aws.sh`** 🚀
