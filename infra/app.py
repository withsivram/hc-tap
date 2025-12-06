#!/usr/bin/env python3
import os

import aws_cdk as cdk
from hc_tap_stack import HcTapStack

app = cdk.App()
HcTapStack(
    app,
    "HcTapStack",
    # Explicitly set environment for account/region-dependent features
    # This is required for ECR repository lookups via from_repository_name()
    # The CDK_DEFAULT_* env vars are automatically set by AWS CDK CLI
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
)

app.synth()
