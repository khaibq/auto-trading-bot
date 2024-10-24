import json

from aws_cdk import (
    aws_iam,
    aws_ssm,
    aws_s3,
    aws_s3_deployment,
    aws_ecr,
    aws_codebuild,
    aws_codepipeline,
    aws_codepipeline_actions,
    App, Aws, Duration, RemovalPolicy, Stack
)

class AutoTradingBotEcrStack(Stack):
    def __init__(self, app: App, id: str, props, **kwargs) -> None:
        super().__init__(app, id, **kwargs)

        # SSM parameter to get webhook allowed IP list
        webhook_params = aws_ssm.StringListParameter(self, "WebhookParameter",
            parameter_name=props["WEBHOOK_SSM_NAME"],
            string_list_value=props["WEBHOOK_IP_ALLOWED_LIST"],
            description="TradingView Webhook allowed IP list"
        )
        # SSM parameter to get message token and message ID for Dicord
        message_params = aws_ssm.StringParameter(
            self, "MessageParameter",
            parameter_name=props["MESSAGE_NAME"],
            string_value=json.dumps(props["MESSAGE_CONFIG"]),
            description="Token and ID to send message"
        )

        # Pipeline requires versioned bucket
        bot_bucket = aws_s3.Bucket(
            self, "SourceBucket",
            bucket_name=props['bucket_name'],
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY)

        aws_s3_deployment.BucketDeployment(self, "DeployFiles",
            sources=[aws_s3_deployment.Source.asset("./s3source")],
            destination_bucket=bot_bucket
        )
        # Create ECR to hold docker image
        ecr = aws_ecr.Repository(
            self, "ECR",
            repository_name=f"{props['namespace']}",
            removal_policy=RemovalPolicy.DESTROY
        )

        # CodeBuild to pull docker image to ECR
        docker_build_from_github = aws_codebuild.Project(self, "DockerBuild",
            project_name=props["docker_build_project_name"],
            build_spec=aws_codebuild.BuildSpec.from_source_filename('docker-build/docker_build_buildspec.yml'),
            environment=aws_codebuild.BuildEnvironment(
                privileged=True,
                build_image=aws_codebuild.LinuxBuildImage.AMAZON_LINUX_2_5,
            ),
            source=aws_codebuild.Source.git_hub(
                owner=props["GIT_HUB_OWNER"],
                repo=props["GIT_HUB_REPO"],
                branch_or_ref=props["GIT_HUB_BRANCH"],
                webhook=True
            ),
            environment_variables={
                "ACCOUNT_ID": aws_codebuild.BuildEnvironmentVariable(value=Aws.ACCOUNT_ID),
                "ECR_URI": aws_codebuild.BuildEnvironmentVariable(value=ecr.repository_uri),
                "IMAGE_NAME": aws_codebuild.BuildEnvironmentVariable(value=ecr.repository_name),
                "FUNCTION_NAME": aws_codebuild.BuildEnvironmentVariable(value=props["function_name"])
            },
            description="CodeBuild for Lambda run on container",
            timeout=Duration.minutes(15)
        )
        lambda_function_update_policy = {
            "Sid": "LambdaFunctionUpdatePolicy",
            "Effect": "Allow",
            "Action": ["lambda:UpdateFunctionCode"],
            "Resource": f"arn:aws:lambda:{Aws.REGION}:{Aws.ACCOUNT_ID}:function:{props["function_name"]}"
        }
        # Add policy to update function code
        docker_build_from_github.add_to_role_policy(aws_iam.PolicyStatement.from_json(lambda_function_update_policy))
        # CodeBuild permissions to interact with ECR
        ecr.grant_pull_push(docker_build_from_github)

        # Define CopePipeline action
        bot_pipeline = aws_codepipeline.Pipeline(self, "Pipeline",
            pipeline_name=props['pipeline_name'],
            pipeline_type=aws_codepipeline.PipelineType.V2
        )
        source_output = aws_codepipeline.Artifact(artifact_name="source")
        bot_pipeline.add_stage(
            stage_name="Source",
            actions=[
                aws_codepipeline_actions.S3SourceAction(
                    bucket=bot_bucket,
                    bucket_key='docker-build.zip',
                    action_name='S3Source',
                    run_order=1,
                    output=source_output
                )
            ]
        )
        bot_pipeline.add_stage(
            stage_name="Build",
            actions=[
                aws_codepipeline_actions.CodeBuildAction(
                    action_name='DockerBuildImages',
                    input=source_output,
                    project=docker_build_from_github,
                    run_order=2
                )
            ]
        )
        self.output_props = props.copy()
        self.output_props['ECR']=ecr
    # Pass objects to another stack
    @property
    def outputs(self):
        return self.output_props
