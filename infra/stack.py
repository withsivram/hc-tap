from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_s3 as s3,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_logs as logs,
    aws_kms as kms,
)
from constructs import Construct
import os

class HcTapStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Constants & Config ---
        # Use provided context
        account_id = "099200121087" # Hardcoded as per prompt for resource names where needed
        region = "us-east-1"
        
        kms_key_arn = "arn:aws:kms:us-east-1:099200121087:key/6071ee8f-e2d0-4957-8efc-0a813ebd243a"
        raw_bucket_name = f"hc-tap-raw-{account_id}-{region}-dev"
        enriched_bucket_name = f"hc-tap-enriched-{account_id}-{region}-dev"
        
        # Image tags
        image_tag = os.getenv("IMAGE_TAG", "latest-dev")

        # --- VPC ---
        vpc = ec2.Vpc.from_lookup(self, "VPC", is_default=True)

        # --- KMS Key ---
        key = kms.Key.from_key_arn(self, "KmsKey", kms_key_arn)

        # --- S3 Buckets ---
        raw_bucket = s3.Bucket(
            self, "RawBucket",
            bucket_name=raw_bucket_name,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=key,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

        enriched_bucket = s3.Bucket(
            self, "EnrichedBucket",
            bucket_name=enriched_bucket_name,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=key,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # --- ECR Repositories ---
        repos = {}
        for name in ["api", "dashboard", "etl"]:
            repo = ecr.Repository(
                self, f"Repo{name.capitalize()}",
                repository_name=f"hc-tap/{name}",
                image_scan_on_push=True,
                removal_policy=RemovalPolicy.RETAIN,
            )
            repo.add_lifecycle_rule(max_image_count=10)
            repos[name] = repo

        # --- ECS Cluster ---
        cluster = ecs.Cluster(
            self, "Cluster",
            cluster_name="hc-tap-dev",
            vpc=vpc,
            container_insights=True,
        )

        # --- IAM Roles ---
        # Task Execution Role (pull images, logs)
        execution_role = iam.Role(
            self, "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )

        # Task Roles
        # API/Dash: Read S3
        api_dash_task_role = iam.Role(
            self, "ApiDashTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        raw_bucket.grant_read(api_dash_task_role)
        enriched_bucket.grant_read(api_dash_task_role)

        # ETL: Read/Write S3
        etl_task_role = iam.Role(
            self, "EtlTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        raw_bucket.grant_read_write(etl_task_role)
        enriched_bucket.grant_read_write(etl_task_role)

        # --- Log Groups ---
        api_log_group = logs.LogGroup(
            self, "ApiLogGroup",
            log_group_name="/ecs/hc-tap/api-dev",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        dash_log_group = logs.LogGroup(
            self, "DashLogGroup",
            log_group_name="/ecs/hc-tap/dash-dev",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY
        )

        # --- Fargate Services ---

        # 1. API Service
        api_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "ApiService",
            cluster=cluster,
            cpu=256, # 0.25 vCPU
            memory_limit_mib=512,
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(repos["api"], tag=image_tag),
                container_port=8000,
                environment={
                    "AWS_REGION": region,
                    "RAW_BUCKET": raw_bucket.bucket_name,
                    "ENRICHED_BUCKET": enriched_bucket.bucket_name,
                    "LOG_LEVEL": "info",
                },
                execution_role=execution_role,
                task_role=api_dash_task_role,
                log_driver=ecs.LogDriver.aws_logs(stream_prefix="api", log_group=api_log_group),
            ),
            public_load_balancer=True,
            assign_public_ip=True, # Fargate platform 1.4+ default
        )
        # Health check
        api_service.target_group.configure_health_check(
            path="/health",
            interval=Duration.seconds(30),
        )

        # 2. Dashboard Service
        # Requirement: Separate ALB or separate hostname. Choosing Separate ALB as "simpler".
        dash_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "DashService",
            cluster=cluster,
            cpu=512, # 0.5 vCPU
            memory_limit_mib=1024, # 1 GiB
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(repos["dashboard"], tag=image_tag),
                container_port=8501,
                environment={
                    "AWS_REGION": region,
                    "API_BASE": f"http://{api_service.load_balancer.load_balancer_dns_name}",
                    "LOG_LEVEL": "info",
                },
                execution_role=execution_role,
                task_role=api_dash_task_role,
                log_driver=ecs.LogDriver.aws_logs(stream_prefix="dashboard", log_group=dash_log_group),
            ),
            public_load_balancer=True,
            assign_public_ip=True,
        )

        # --- ETL Task Definition (No Service) ---
        etl_task_def = ecs.FargateTaskDefinition(
            self, "EtlTaskDef",
            cpu=512, # 0.5 vCPU default/guess
            memory_limit_mib=1024, # 1 GiB default/guess
            execution_role=execution_role,
            task_role=etl_task_role,
        )
        
        etl_container = etl_task_def.add_container(
            "EtlContainer",
            image=ecs.ContainerImage.from_ecr_repository(repos["etl"], tag=image_tag),
            logging=ecs.LogDriver.aws_logs(stream_prefix="etl"),
            environment={
                "AWS_REGION": region,
                "RAW_BUCKET": raw_bucket.bucket_name,
                "ENRICHED_BUCKET": enriched_bucket.bucket_name,
            }
        )

        # --- Outputs ---
        CfnOutput(self, "ApiAlbUrl", value=f"http://{api_service.load_balancer.load_balancer_dns_name}")
        CfnOutput(self, "DashAlbUrl", value=f"http://{dash_service.load_balancer.load_balancer_dns_name}")
