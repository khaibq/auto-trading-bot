import os
import boto3
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    print(event)

    # Retrieve request parameters from the Lambda function input:
    headers = event['headers']

    # Parse the input for the parameter values
    tmp = event['methodArn'].split(':')
    apiGatewayArnTmp = tmp[5].split('/')
    resource = '/'

    if (apiGatewayArnTmp[3]):
        resource += apiGatewayArnTmp[3]
    ssm_name = os.environ['WEBHOOK_SSM_NAME']
    region_name = os.environ['REGION_NAME']
    approved_ip_list = get_ssm_parameter_list(ssm_name, region_name)
    print(approved_ip_list)

    # Perform authorization to return the Allow policy for correct parameters
    # and the 'Unauthorized' error, otherwise.
    if headers['X-Forwarded-For'] in approved_ip_list:
        response = generateAllow('XForwardForAuthorized', event['methodArn'])
        print('authorized')
        return response
    else:
        print('unauthorized')
        raise Exception('Unauthorized') # Return a 401 Unauthorized response

# Get Parameter List for approved IP list
def get_ssm_parameter_list(ssm_name, region):
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
    ssm_params_list = get_ssm_params_response["Parameter"]["Value"].split(",")
    return ssm_params_list

# Help function to generate IAM policy
def generatePolicy(principalId, effect, resource):
    authResponse = {}
    authResponse['principalId'] = principalId
    if (effect and resource):
        policyDocument = {}
        policyDocument['Version'] = '2012-10-17'
        policyDocument['Statement'] = []
        statementOne = {}
        statementOne['Action'] = 'execute-api:Invoke'
        statementOne['Effect'] = effect
        statementOne['Resource'] = resource
        policyDocument['Statement'] = [statementOne]
        authResponse['policyDocument'] = policyDocument
    return authResponse

def generateAllow(principalId, resource):
    return generatePolicy(principalId, 'Allow', resource)

def generateDeny(principalId, resource):
    return generatePolicy(principalId, 'Deny', resource)