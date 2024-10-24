import json
import boto3
from botocore.exceptions import ClientError
from dydx_v4_client.indexer.rest.indexer_client import IndexerClient
from dydx_v4_client.network import TESTNET

async def subaccount_info(test_address, subaccount_no):
    indexer = IndexerClient(TESTNET.rest_indexer)
    try:
        response = await indexer.account.get_subaccount(test_address, subaccount_no)
        subaccount = response["subaccount"]
    except Exception as e:
        print(f"Error: {e}")
    return subaccount

async def get_secret(secret_name, region):
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e
    secret = json.loads(get_secret_value_response['SecretString'])
    return secret

async def get_ssm_parameter(ssm_name, region):
    # Create a SSM client
    session = boto3.session.Session()
    client = session.client(
        service_name="ssm",
        region_name=region
    )
    try:
        get_ssm_params_response = client.get_parameter(Name=ssm_name)
    except ClientError as e:
        raise e
    ssm_params = json.loads(get_ssm_params_response["Parameter"]["Value"])
    return ssm_params