# AWS Credentials Security Notice

## IMPORTANT: Security Configuration Required

The GitHub workflows currently have AWS account information exposed in the workflow files:
- `.github/workflows/run-etl.yml`
- `.github/workflows/deploy.yml`

## Action Required

Move the following to GitHub repository secrets:

1. Go to your repository Settings → Secrets and variables → Actions
2. Add the following secrets:
   - `AWS_ACCOUNT_ID`: Your AWS account ID (currently hardcoded: 099200121087)
   - `AWS_ROLE_ARN`: Your IAM role ARN (currently hardcoded in workflows)

3. Update the workflow files to use secrets instead of hardcoded values:

```yaml
env:
  AWS_REGION: us-east-1
  AWS_ACCOUNT_ID: ${{ secrets.AWS_ACCOUNT_ID }}
  AWS_ROLE_ARN: ${{ secrets.AWS_ROLE_ARN }}
```

## Why This Matters

While AWS account IDs are not as sensitive as access keys, exposing them can:
- Help attackers understand your infrastructure
- Make targeted attacks easier
- Violate security best practices

## Implementation

A backup workflow file with improved error handling has been created at:
`.github/workflows/run-etl.yml.bak`

Review and update your workflows accordingly.
