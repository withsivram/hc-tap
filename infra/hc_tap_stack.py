from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct


class HcTapStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. ECR Repositories
        # Reference existing repositories created by GitHub workflow
        # Workflow creates repos first, pushes images, then CDK deploys services
        # This avoids CloudFormation validation errors for non-existent images
        self.api_repo = ecr.Repository.from_repository_name(
            self, "ApiRepo", "hc-tap/api"
        )

        self.dashboard_repo = ecr.Repository.from_repository_name(
            self, "DashboardRepo", "hc-tap/dashboard"
        )

        self.etl_repo = ecr.Repository.from_repository_name(
            self, "EtlRepo", "hc-tap/etl"
        )

        # 2. S3 Buckets
        self.raw_bucket = s3.Bucket(
            self,
            "RawDataBucket",
            bucket_name="hc-tap-raw-notes",  # Suffix might be needed if taken
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        self.enriched_bucket = s3.Bucket(
            self,
            "EnrichedDataBucket",
            bucket_name="hc-tap-enriched-entities",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # 3. VPC
        self.vpc = ec2.Vpc(self, "HcTapVpc", max_azs=2)

        # 4. ECS Cluster
        self.cluster = ecs.Cluster(self, "HcTapCluster", vpc=self.vpc)

        # 5. API Fargate Service
        # Using ApplicationLoadBalancedFargateService for easy ALB setup
        self.api_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "ApiService",
            cluster=self.cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(
                    self.api_repo, "latest-dev"
                ),
                container_port=8000,
                environment={
                    "RAW_BUCKET": self.raw_bucket.bucket_name,
                    "ENRICHED_BUCKET": self.enriched_bucket.bucket_name,
                    "HC_TAP_ENV": "cloud",
                },
            ),
            public_load_balancer=True,
        )

        # Grant permissions
        self.raw_bucket.grant_read_write(self.api_service.task_definition.task_role)
        self.enriched_bucket.grant_read_write(
            self.api_service.task_definition.task_role
        )

        # 6. Dashboard Fargate Service
        # Needs to know API URL
        self.dashboard_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "DashboardService",
            cluster=self.cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(
                    self.dashboard_repo, "latest-dev"
                ),
                container_port=8501,
                environment={
                    "API_URL": f"http://{self.api_service.load_balancer.load_balancer_dns_name}",
                    "HC_TAP_ENV": "cloud",
                },
            ),
            public_load_balancer=True,
        )

        # Grant permissions (Dashboard might read directly from S3 for some views, ideally goes via API)
        self.enriched_bucket.grant_read(
            self.dashboard_service.task_definition.task_role
        )

        # 7. ETL Task Definition (Fargate)
        # This is not a Service (doesn't run continuously), but a Task Definition
        # that we can run on-demand via GitHub Actions or AWS CLI.
        
        # Create CloudWatch Log Group for ETL
        self.etl_log_group = logs.LogGroup(
            self,
            "EtlLogGroup",
            log_group_name="/ecs/HcTapEtl",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )
        
        self.etl_task_def = ecs.FargateTaskDefinition(
            self,
            "EtlTaskDef",
            cpu=512,
            memory_limit_mib=1024,  # Give ETL a bit more juice
        )

        self.etl_container = self.etl_task_def.add_container(
            "EtlContainer",
            image=ecs.ContainerImage.from_ecr_repository(self.etl_repo, "latest-dev"),
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="HcTapEtl",
                log_group=self.etl_log_group,
            ),
            environment={
                "RAW_BUCKET": self.raw_bucket.bucket_name,
                "ENRICHED_BUCKET": self.enriched_bucket.bucket_name,
                "HC_TAP_ENV": "cloud",
                "RUN_ID": "cloud-manual",  # Default, can be overridden
            },
        )

        # Grant permissions
        self.raw_bucket.grant_read(self.etl_task_def.task_role)
        self.enriched_bucket.grant_read_write(self.etl_task_def.task_role)
