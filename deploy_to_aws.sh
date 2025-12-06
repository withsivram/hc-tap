#!/bin/bash
# HC-TAP AWS Deployment Verification and Deploy Script
# Run this in your local terminal: bash deploy_to_aws.sh

set -e  # Exit on any error

echo "======================================================================="
echo "HC-TAP - AWS Deployment Verification & Deploy"
echo "======================================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check AWS CLI
echo "=== STEP 1: Checking AWS CLI ==="
if command -v aws &> /dev/null; then
    echo -e "${GREEN}✅ AWS CLI is installed${NC}"
    aws --version
else
    echo -e "${RED}❌ AWS CLI not found${NC}"
    echo ""
    echo "Install AWS CLI:"
    echo "  macOS:   brew install awscli"
    echo "  Linux:   pip install awscli"
    echo "  Windows: Download from https://aws.amazon.com/cli/"
    echo ""
    exit 1
fi
echo ""

# Step 2: Check AWS Authentication
echo "=== STEP 2: Verifying AWS Credentials ==="
if aws sts get-caller-identity &> /dev/null; then
    echo -e "${GREEN}✅ AWS credentials configured${NC}"
    aws sts get-caller-identity
    
    # Get account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    echo ""
    echo "Your AWS Account ID: $ACCOUNT_ID"
    
    if [ "$ACCOUNT_ID" != "099200121087" ]; then
        echo -e "${YELLOW}⚠️  Warning: Account ID doesn't match expected value${NC}"
        echo "   Expected: 099200121087"
        echo "   Got: $ACCOUNT_ID"
    fi
else
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    echo ""
    echo "Configure AWS credentials:"
    echo "  aws configure"
    echo ""
    echo "Or set environment variables:"
    echo "  export AWS_ACCESS_KEY_ID=your_key"
    echo "  export AWS_SECRET_ACCESS_KEY=your_secret"
    echo "  export AWS_DEFAULT_REGION=us-east-1"
    echo ""
    exit 1
fi
echo ""

# Step 3: Verify IAM Role
echo "=== STEP 3: Checking IAM Role ==="
ROLE_NAME="hc-tap-github-deploy-role"
if aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
    echo -e "${GREEN}✅ IAM role exists: $ROLE_NAME${NC}"
    aws iam get-role --role-name $ROLE_NAME --query 'Role.{RoleName:RoleName,Arn:Arn,CreateDate:CreateDate}' --output table
else
    echo -e "${YELLOW}⚠️  IAM role not found or no permission to check${NC}"
    echo "   Role: $ROLE_NAME"
    echo ""
    echo "   This might be okay if:"
    echo "   1. You don't have IAM permissions (deployment will still work)"
    echo "   2. The role is in a different account"
    echo "   3. The role will be created during deployment"
fi
echo ""

# Step 4: Check GitHub Secrets
echo "=== STEP 4: Verify GitHub Secrets Status ==="
echo -e "${GREEN}✅ You confirmed GitHub secrets are configured${NC}"
echo "   Required secrets:"
echo "   • AWS_ACCOUNT_ID = 099200121087"
echo "   • AWS_ROLE_ARN = arn:aws:iam::099200121087:role/hc-tap-github-deploy-role"
echo ""

# Step 5: Check existing infrastructure
echo "=== STEP 5: Checking Existing AWS Infrastructure ==="

echo "Checking ECS clusters..."
if aws ecs list-clusters --region us-east-1 &> /dev/null; then
    CLUSTERS=$(aws ecs list-clusters --region us-east-1 --query 'clusterArns' --output text)
    if [ -n "$CLUSTERS" ]; then
        echo -e "${GREEN}✅ Found ECS clusters:${NC}"
        aws ecs list-clusters --region us-east-1 --query 'clusterArns[]' --output table
    else
        echo "   No ECS clusters found (will be created during deployment)"
    fi
else
    echo "   Could not check ECS clusters (might be permission issue)"
fi
echo ""

echo "Checking ECR repositories..."
if aws ecr describe-repositories --region us-east-1 &> /dev/null; then
    REPOS=$(aws ecr describe-repositories --region us-east-1 --query 'repositories[?contains(repositoryName, `hc-tap`)].repositoryName' --output text 2>/dev/null)
    if [ -n "$REPOS" ]; then
        echo -e "${GREEN}✅ Found HC-TAP ECR repositories:${NC}"
        aws ecr describe-repositories --region us-east-1 --query 'repositories[?contains(repositoryName, `hc-tap`)].{Name:repositoryName,URI:repositoryUri}' --output table
    else
        echo "   No HC-TAP ECR repos found (will be created during deployment)"
    fi
else
    echo "   Could not check ECR repositories"
fi
echo ""

echo "Checking S3 buckets..."
BUCKETS=$(aws s3 ls 2>/dev/null | grep hc-tap || echo "")
if [ -n "$BUCKETS" ]; then
    echo -e "${GREEN}✅ Found HC-TAP S3 buckets:${NC}"
    aws s3 ls | grep hc-tap
else
    echo "   No HC-TAP S3 buckets found (will be created during deployment)"
fi
echo ""

# Step 6: Check local code status
echo "=== STEP 6: Checking Local Code Status ==="
if [ -d .git ]; then
    echo -e "${GREEN}✅ Git repository detected${NC}"
    echo "Current branch: $(git branch --show-current)"
    echo "Latest commit: $(git log --oneline -1)"
    
    # Check if there are uncommitted changes
    if [ -n "$(git status --porcelain)" ]; then
        echo -e "${YELLOW}⚠️  You have uncommitted changes${NC}"
        echo ""
        git status --short
        echo ""
        echo "Commit these changes before deploying!"
    else
        echo -e "${GREEN}✅ No uncommitted changes${NC}"
    fi
    
    # Check if ahead of remote
    if git rev-list @{u}.. &> /dev/null; then
        COMMITS_AHEAD=$(git rev-list --count @{u}.. 2>/dev/null || echo "0")
        if [ "$COMMITS_AHEAD" -gt 0 ]; then
            echo -e "${YELLOW}⚠️  You have $COMMITS_AHEAD commit(s) not pushed to remote${NC}"
            echo ""
            git log @{u}.. --oneline
        else
            echo -e "${GREEN}✅ Local is in sync with remote${NC}"
        fi
    fi
else
    echo -e "${RED}❌ Not in a git repository${NC}"
    exit 1
fi
echo ""

# Step 7: Deployment options
echo "======================================================================="
echo "READY TO DEPLOY!"
echo "======================================================================="
echo ""
echo "Choose your deployment method:"
echo ""
echo "METHOD 1: GitHub Actions (Recommended)"
echo "  1. Push your code:"
echo "     git push origin main"
echo ""
echo "  2. Monitor deployment:"
echo "     https://github.com/YOUR_USERNAME/YOUR_REPO/actions"
echo ""
echo "  3. Or trigger manually:"
echo "     - Go to: Actions → Deploy to AWS → Run workflow"
echo ""
echo "-----------------------------------------------------------------------"
echo ""
echo "METHOD 2: Local CDK Deployment"
echo "  Prerequisites:"
echo "    - Node.js and npm installed"
echo "    - AWS CDK installed: npm install -g aws-cdk"
echo ""
echo "  Commands:"
echo "    cd infra"
echo "    pip install -r requirements.txt"
echo "    cdk bootstrap  # First time only"
echo "    cdk deploy"
echo ""
echo "-----------------------------------------------------------------------"
echo ""

# Ask user what to do
echo "What would you like to do?"
echo "  [1] Push to GitHub and deploy via Actions (recommended)"
echo "  [2] Show me the git push command"
echo "  [3] Check infrastructure status only (no deployment)"
echo "  [4] Exit"
echo ""
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo ""
        echo "Pushing to GitHub..."
        git push origin $(git branch --show-current)
        echo ""
        echo -e "${GREEN}✅ Code pushed!${NC}"
        echo ""
        echo "Monitor deployment at:"
        echo "https://github.com/$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/actions"
        ;;
    2)
        echo ""
        echo "Run this command to push and trigger deployment:"
        echo ""
        echo "  git push origin $(git branch --show-current)"
        echo ""
        ;;
    3)
        echo ""
        echo "Infrastructure check complete. See output above."
        ;;
    4)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "======================================================================="
echo "For post-deployment verification, see: CLOUD_INFRASTRUCTURE_STATUS.md"
echo "======================================================================="
