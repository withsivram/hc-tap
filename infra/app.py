#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infra.stack import HcTapStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

HcTapStack(app, "HcTapStack", env=env)

app.synth()
