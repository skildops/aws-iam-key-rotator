import json
import boto3
import os
import concurrent.futures

from botocore.exceptions import ClientError

# AWS Profile to use for API calls
IKR_AWS_PROFILE = os.environ.get('IKR_AWS_PROFILE', None)

# AWS Access Key to use for API calls
IKR_AWS_ACCESS_KEY_ID = os.environ.get('IKR_AWS_ACCESS_KEY_ID', None)

# AWS Secret Access Key to use for API calls
IKR_AWS_SECRET_ACCESS_KEY = os.environ.get('IKR_AWS_SECRET_ACCESS_KEY', None)

# AWS Session Token to use for API calls
IKR_AWS_SESSION_TOKEN = os.environ.get('IKR_AWS_SESSION_TOKEN', None)

# AWS region to use
IKR_AWS_REGION = os.environ.get('IKR_AWS_REGION', 'us-east-1')

session = boto3.Session(aws_access_key_id=IKR_AWS_ACCESS_KEY_ID, aws_secret_access_key=IKR_AWS_SECRET_ACCESS_KEY, aws_session_token=IKR_AWS_SESSION_TOKEN, region_name=IKR_AWS_REGION, profile_name=IKR_AWS_PROFILE)
iam = session.client('iam')

iamUsers = json.load(open('iam-user-tags.json'))

def tag_user(userName, tags):
    print('Tagging user {}'.format(userName))
    try:
        userTags = []
        for t in tags:
            userTags.append({
                'Key': t,
                'Value': tags[t]
            })

        iam.tag_user(
            UserName=userName,
            Tags=userTags
        )
        print('Tag(s) added to user {}'.format(userName))
    except (Exception, ClientError) as ce:
        print('Failed to tag user {}. Reason: {}'.format(userName, ce))

    return userName

if len(iamUsers) == 0:
    print('No IAM users present in user-tagging.json file')
else:
    # Tagging each user using a separate thread
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = [executor.submit(tag_user, u, iamUsers[u]) for u in iamUsers]
