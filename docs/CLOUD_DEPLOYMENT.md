# Phase 4: Cloud Deployment

## Status: Deployed ✅

**Dashboard URL:** `http://HcTapS-Dashb-5iBZJdx9Sd2t-704847677.us-east-1.elb.amazonaws.com`
**API URL:** `http://HcTapS-ApiSe-eriqR6HatRWP-860990366.us-east-1.elb.amazonaws.com`

## Architecture
- **Infrastructure:** AWS CDK (Python) -> CloudFormation
- **Compute:** AWS ECS Fargate (Serverless Containers)
- **Load Balancing:** Application Load Balancers (ALB)
- **Storage:** S3 (`hc-tap-raw-notes`, `hc-tap-enriched-entities`)
- **Registry:** Amazon ECR

## CI/CD Pipeline
- **Source:** GitHub (`main` branch)
- **Workflow:** `.github/workflows/deploy.yml`
- **Actions:**
    1. Create ECR Repositories (if missing)
    2. Build Docker Images (API, Dashboard)
    3. Push to ECR
    4. Deploy CDK Stack (`infra/`)

## Manual Deployment (Fallback)
If GitHub Actions fail (e.g. Docker Hub rate limits), use **AWS CloudShell**:

```bash
# 1. Clone & Setup
git clone https://github.com/withsivram/hc-tap.git
cd hc-tap
pip3 install -r infra/requirements.txt

# 2. Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 099200121087.dkr.ecr.us-east-1.amazonaws.com

# 3. Build & Push
docker build -f Dockerfile.api -t 099200121087.dkr.ecr.us-east-1.amazonaws.com/hc-tap/api:latest-dev .
docker push 099200121087.dkr.ecr.us-east-1.amazonaws.com/hc-tap/api:latest-dev

docker build -f Dockerfile.dashboard -t 099200121087.dkr.ecr.us-east-1.amazonaws.com/hc-tap/dashboard:latest-dev .
docker push 099200121087.dkr.ecr.us-east-1.amazonaws.com/hc-tap/dashboard:latest-dev

# 4. Deploy Infrastructure
cd infra
npx aws-cdk deploy --require-approval never

# 5. Force Service Update (if needed)
CLUSTER="HcTapStack-HcTapCluster7E2888D7-HmpLjPKHNhuc" # Check via `aws ecs list-clusters`
SERVICE=$(aws ecs list-services --cluster $CLUSTER --query "serviceArns[?contains(@, 'DashboardService')]" --output text | awk -F/ '{print $3}')
aws ecs update-service --cluster $CLUSTER --service $SERVICE --force-new-deployment
```

## Data Sync
To populate S3 buckets with local fixture data:
```bash
python3 scripts/sync_to_s3.py
```

