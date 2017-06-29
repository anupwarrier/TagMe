from __future__ import print_function

import json
import urllib
import boto3
import gzip
import io
import logging


logger = logging.getLogger()
logger.setLevel(logging.INFO)

print('Loading function')

# General services

sns = boto3.client('sns')

# Values
SNS_TOPIC_ARN = 'arn:aws:sns:us-west-2:129801715103:tagme-topic'
TAGS = ['CostCenter','AssetProtectionLevel','Team','Application','Owner','Email']

def decompress(data):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
        return f.read()


def report(instance, user, region):
    report = "User " + user + " created an instance on region " +  region + " without proper tagging. \n"
    report += "Instance id: " + instance['instanceId'] + "\n"
    report += "Image Id: " + instance['imageId'] + "\n"
    report += "Instance type: " + instance['instanceType'] + "\n"
    report += "This instance has been destroyed."
    return report


def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))
    logger.info("Key" + key)
    try:
        list_keys = []
        s3 = boto3.client('s3')
        s3_object = s3.get_object(Bucket=bucket, Key=key)
        s3_object_content = s3_object['Body'].read()
        s3_object_unzipped_content = decompress(s3_object_content)
        json_object = json.loads(s3_object_unzipped_content)
        if json_object['Records'] != None:
            for record in json_object['Records']:
                if record['eventName'] == "RunInstances":
                    user = record['userIdentity']['principalId'].split(':')
                    region = record['awsRegion']
                    ec2 = boto3.resource('ec2', region_name=region)
                    for index, instance in enumerate(record['responseElements']['instancesSet']['items']):
                        instance_object = ec2.Instance(instance['instanceId'])
                        logger.info("Instance Id " + instance['instanceId'] )
                        tags = {}
                        should_terminate = 0
                        if instance_object.tags == None: 
                            should_terminate = 1
                        else :
                            for tag in instance_object.tags:
                                list_keys.append(tag['Key']) 
                            for key in TAGS:
                                if key not in list_keys:
                                    should_terminate = 1
                        if should_terminate == 1 :
                            instance_object.terminate()
                            sns.publish(TopicArn=SNS_TOPIC_ARN, Message=report(instance, user[1], region))
    except Exception as e:
        print(e)
        raise e