import json
import boto3
import os
import concurrent.futures

from botocore.exceptions import ClientError

# AWS Profile to use for API calls
AWS_PROFILE = os.environ.get('AWS_PROFILE', None)

# AWS Access Key to use for API calls
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', None)

# AWS Secret Access Key to use for API calls
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', None)

# AWS Session Token to use for API calls
AWS_SESSION_TOKEN = os.environ.get('AWS_SESSION_TOKEN', None)

# AWS region to use
AWS_REGION = 'us-east-1'

session = boto3.Session(aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY, aws_session_token=AWS_SESSION_TOKEN, region_name=AWS_REGION, profile_name=AWS_PROFILE)
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
