#!/usr/bin/env python3
import aws_cdk as cdk

from auto_trading_bot_api.auto_trading_bot_api_stack import AutoTradingBotRestApiStack
from auto_trading_bot_ecr.auto_trading_bot_ecr_stack import AutoTradingBotEcrStack

# Named the general namespace on your choice
namespace = <YOUR_NAMESPACE>

# IP list protection for webhook received (provided by TradingView)
webhook_ip_allowed_list = ["52.89.214.238", "34.212.75.30", "54.218.53.128", "52.32.178.7"]

# Configuration for message notification when placing the order
message_config = {
   "message_webhook_id": <YOUR_DISCORD_WEBHOOK_ID>,
   "message_webhook_token": <YOUR_DISCORD_WEBHOOK_TOKEN>
}
# Parameter format
props = {
    "SECRET_NAME": <YOUR_SECRET_NAME>,
    "REGION_NAME": <REGION_NAME>,
    "GIT_HUB_OWNER": <YOUR_GITHUB_OWNER_NAME>
    "GIT_HUB_REPO": <YOUR_REPO_NAME>,
    "GIT_HUB_BRANCH": "main",
    "WEBHOOK_SSM_NAME": "webhook_ip_list",
    "WEBHOOK_IP_ALLOWED_LIST": webhook_ip_allowed_list,
    "MESSAGE_NAME": "discord_notification",
    "MESSAGE_CONFIG": message_config,
    "namespace": namespace,
    "function_name": f"{namespace}-TradingBotLambda",
    "custom_auth_function_name": f"{namespace}-CustomAuth",
    "bucket_name": f"{namespace.lower()}-trading-bot-bucket",
    "docker_build_project_name": f"{namespace}-DockerBuild",
    "pipeline_name": f"{namespace}-Pipeline"
}

app = cdk.App()

base_ecr = AutoTradingBotEcrStack(app, f"{props["namespace"]}-BotEcr", props)
rest_api_execution = AutoTradingBotRestApiStack(app, f"{props["namespace"]}-RestApi", base_ecr.outputs)
rest_api_execution.add_dependency(base_ecr)
app.synth()