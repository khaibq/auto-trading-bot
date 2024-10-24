from aws_cdk import (
    aws_iam,
    aws_lambda,
    aws_apigateway,
    Aws, RemovalPolicy, CfnOutput, Stack, Duration
)
from constructs import Construct

class AutoTradingBotRestApiStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, props, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bot_lambda_function = aws_lambda.DockerImageFunction(self, "AutoTradingBotLambda",
            function_name=props['function_name'],
            code=aws_lambda.DockerImageCode.from_ecr(props["ECR"]),
            timeout=Duration.seconds(29)
        )
        bot_lambda_role = bot_lambda_function.role
        secret_policy_statement = {
            "Sid": "GetSecretValuePolicy",
            "Effect": "Allow",
            "Action": ["secretsmanager:GetSecretValue"],
            "Resource": f"arn:aws:secretsmanager:{Aws.REGION}:{Aws.ACCOUNT_ID}:secret:{props["SECRET_NAME"]}*"
        }
        ssm_policy_statement = {
            "Sid": "RetrieveSSMParameterPolicy",
            "Effect": "Allow",
            "Action": ["ssm:GetParameter"],
            "Resource": f"arn:aws:ssm:{Aws.REGION}:{Aws.ACCOUNT_ID}:parameter/{props["MESSAGE_NAME"]}*"
        }
        bot_lambda_role.add_to_principal_policy(aws_iam.PolicyStatement.from_json(secret_policy_statement))
        bot_lambda_role.add_to_principal_policy(aws_iam.PolicyStatement.from_json(ssm_policy_statement))

        bot_lambda_function.add_environment("SECRET_NAME", props["SECRET_NAME"])
        bot_lambda_function.add_environment("MESSAGE_NAME", props["MESSAGE_NAME"])
        bot_lambda_function.add_environment("REGION_NAME", props["REGION_NAME"])

        custom_auth_lambda = aws_lambda.Function(self, "CustomAuth",
            function_name=props["custom_auth_function_name"],
            description="Lambda function for custom authorization",
            handler="customauthlambda.lambda_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_12,
            code=aws_lambda.Code.from_asset("./custom_auth_lambda_function"),
            timeout=Duration.seconds(29))
        # Add policy to retrieve SSM Parameter
        ssm_custom_auth_policy_statement = {
            "Sid": "GetSSMParameterPolicy",
            "Effect": "Allow",
            "Action": ["ssm:GetParameter"],
            "Resource": f"arn:aws:ssm:{Aws.REGION}:{Aws.ACCOUNT_ID}:parameter/{props["WEBHOOK_SSM_NAME"]}*"
        }
        custom_auth_lambda.add_to_role_policy(aws_iam.PolicyStatement.from_json(ssm_custom_auth_policy_statement))

        custom_auth_lambda.add_environment("WEBHOOK_SSM_NAME", props["WEBHOOK_SSM_NAME"])
        custom_auth_lambda.add_environment("REGION_NAME", props["REGION_NAME"])

        bot_rest_api = aws_apigateway.RestApi(self, "TradingBotRestApi",
            cloud_watch_role=True,
            cloud_watch_role_removal_policy=RemovalPolicy.DESTROY,
            endpoint_types=[aws_apigateway.EndpointType.REGIONAL],
            default_method_options=aws_apigateway.MethodOptions(
                method_responses=[aws_apigateway.MethodResponse(status_code="200")]
            )
        )
        rest_api_integration = aws_apigateway.LambdaIntegration(
            handler=bot_lambda_function,
            proxy=True,
            timeout=Duration.seconds(29)
        )
        bot_rest_api_resource = bot_rest_api.root.add_resource("webhook")

        custom_auth = aws_apigateway.RequestAuthorizer(self, "TradingBotCustomAuth",
            authorizer_name="TradingBotCustomAuthorizer",
            handler=custom_auth_lambda,
            identity_sources=[aws_apigateway.IdentitySource.header("X-Forwarded-For")]
        )
        bot_rest_api_resource.add_method("GET",
            integration=rest_api_integration,
            authorization_type=aws_apigateway.AuthorizationType.CUSTOM,
            authorizer=custom_auth
        )
        bot_rest_api_resource.add_method("POST",
            integration=rest_api_integration,
            authorization_type=aws_apigateway.AuthorizationType.CUSTOM,
            authorizer=custom_auth
        )

        CfnOutput(self, "OutputRestApi",
            description="Trading Bot Rest API",
            value=bot_rest_api.rest_api_id
        )