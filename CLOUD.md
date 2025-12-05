# Cloud Deployment (AWS)

The HC-TAP application is deployed to AWS using [AWS CDK](https://aws.amazon.com/cdk/) and GitHub Actions.

## Architecture

- **API**: FastAPI service running on AWS Fargate behind a public Application Load Balancer.
- **Dashboard**: Streamlit app running on AWS Fargate behind a separate public Application Load Balancer.
- **ETL**: Scheduled/On-demand Fargate tasks (currently defined but not scheduled).
- **Storage**: S3 buckets for raw (`hc-tap-raw-...`) and enriched (`hc-tap-enriched-...`) data, encrypted with KMS.
- **Registry**: ECR repositories for Docker images.

## Access

- **API Endpoint:** [Placeholder - See GitHub Deploy Job Summary]
- **Dashboard URL:** [Placeholder - See GitHub Deploy Job Summary]

## Deployment

Deployment is automated via GitHub Actions:

1.  **Infrastructure**: Managed via `infra/` (CDK).
2.  **CI/CD**:
    - **Build**: Push to `main` triggers Docker build and push to ECR (`.github/workflows/docker.yml`).
    - **Deploy**: Push to `main` triggers `cdk deploy` (`.github/workflows/deploy.yml`).
    - **Bootstrap**: Run `.github/workflows/bootstrap.yml` manually once to initialize CDK environment.

## Logs

Application logs are available in CloudWatch Logs:
- API: `/ecs/hc-tap/api-dev`
- Dashboard: `/ecs/hc-tap/dash-dev`

## Local Development

To run locally, see [README.md](./README.md).
