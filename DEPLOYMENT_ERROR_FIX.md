# Deployment Troubleshooting Guide

## 🔴 Current Error Analysis

**Error:** `AWS::EarlyValidation::ResourceExistenceCheck failed`

**Cause:** The CDK stack is trying to reference ECR repositories that don't exist yet.

---

## 🔧 Fix Options

### **OPTION 1: Create ECR Repos First** (Recommended)

The deployment workflow should create ECR repos, but they might not be created properly. Let's verify and fix:

#### Step 1: Check if ECR repos exist

Run in your terminal:
```bash
aws ecr describe-repositories --repository-names hc-tap/api --region us-east-1 2>&1
aws ecr describe-repositories --repository-names hc-tap/dashboard --region us-east-1 2>&1
aws ecr describe-repositories --repository-names hc-tap/etl --region us-east-1 2>&1
```

If any return "RepositoryNotFoundException", they need to be created.

#### Step 2: Manually create ECR repositories

```bash
# Create the three ECR repositories
aws ecr create-repository --repository-name hc-tap/api --region us-east-1
aws ecr create-repository --repository-name hc-tap/dashboard --region us-east-1
aws ecr create-repository --repository-name hc-tap/etl --region us-east-1
```

#### Step 3: Re-run the deployment

Go to: GitHub → Actions → Deploy to AWS → Re-run failed jobs

---

### **OPTION 2: Fix CDK Stack to Create Repos** (Better long-term)

Update the CDK stack to create ECR repos instead of referencing existing ones:

**Current code (lines 16-29 in hc_tap_stack.py):**
```python
# References existing repos - fails if they don't exist
self.api_repo = ecr.Repository.from_repository_name(
    self, "ApiRepo", "hc-tap/api"
)
```

**Should be:**
```python
# Creates repos if they don't exist
self.api_repo = ecr.Repository(
    self,
    "ApiRepo",
    repository_name="hc-tap/api",
    removal_policy=RemovalPolicy.DESTROY,
    auto_delete_images=True,
)
```

This change makes the CDK stack self-sufficient.

---

### **OPTION 3: Bootstrap CDK First**

CDK might not be bootstrapped in your AWS account:

```bash
# Bootstrap CDK (one-time setup)
cd infra
cdk bootstrap aws://099200121087/us-east-1
```

Then re-run deployment.

---

## 🎯 **Recommended Solution**

Since you don't have AWS CLI configured locally, use **GitHub workflow** to fix this:

### Update the deployment workflow to handle the error better:

The workflow already tries to create repos in step "Ensure ECR Repos Exist", but it might be failing silently.

Let me create a fixed version of the CDK stack that creates repos instead of referencing them.

---

## ⚡ **Quick Fix: Update CDK Stack**

I'll update the infrastructure code to create ECR repositories instead of referencing them. This will make deployment work on first run.

---

## 📋 **What to do next:**

1. I'll fix the CDK stack code
2. Commit the fix
3. Push to GitHub
4. Re-run the deployment

Would you like me to:
- **A)** Fix the CDK stack to create ECR repos (recommended)
- **B)** Show you how to create repos manually via AWS Console
- **C)** Create a script to set up ECR repos
