import boto3
import os
import logging
import concurrent.futures
import pytz

from datetime import datetime, date
from botocore.exceptions import ClientError

# No. of days to wait before existing key pair is deleted once a new key pair is generated
DAYS_FOR_DELETION = os.environ.get('DAYS_FOR_DELETION', 5)

# Table name which holds existing access key pair details to be deleted
IAM_KEY_ROTATOR_TABLE = os.environ.get('IAM_KEY_ROTATOR_TABLE')

# Days after which a new access key pair should be generated
ACCESS_KEY_AGE = os.environ.get('ACCESS_KEY_AGE', 85)

# Mail client to use for sending new key creation or existing key deletion mail
MAIL_CLIENT = os.environ.get('MAIL_CLIENT', 'ses')

# From address to be used while sending mail
MAIL_FROM = os.environ.get('MAIL_FROM')

# AWS_REGION environment variable is by default available within lambda environment
iam = boto3.client('iam', region_name=os.environ.get('AWS_REGION'))
dynamodb = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION'))

logger = logging.getLogger('creator')
logger.setLevel(logging.INFO)

def fetch_users_with_email(user):
    logger.info('Fetching tags for {}'.format(user))
    resp = iam.list_user_tags(
        UserName=user
    )

    userAttributes = {}
    for t in resp['Tags']:
        if t['Key'].lower() == 'email':
            userAttributes['email'] = t['Value']

        if t['Key'].lower() == 'rotate_after_days':
            userAttributes['rotate_after'] = t['Value']

    if 'email' in userAttributes:
        return True, user, userAttributes

    return False, user, None

def fetch_user_keys(user):
    logger.info('Fetching keys for {}'.format(user))
    resp = iam.list_access_keys(
        UserName=user
    )

    userKeys = []
    for obj in resp['AccessKeyMetadata']:
        userKeys.append({
            'ak': obj['AccessKeyId'],
            'ak_age_days': (datetime.now(pytz.UTC) - obj['CreateDate']).days
        })

    return user, userKeys

def fetch_user_details():
    users = {}
    try:
        params = {}
        logger.info('Fetching all users')
        while True:
            resp = iam.list_users(**params)

            for u in resp['Users']:
                users[u['UserName']] = {}

            try:
                params['Marker'] = resp['Marker']
            except Exception:
                break

        logger.info('Fetching tags for users individually')
        with concurrent.futures.ThreadPoolExecutor(10) as executor:
            results = [executor.submit(fetch_users_with_email, user) for user in users]

        for f in concurrent.futures.as_completed(results):
            hasEmail, userName, userAttributes = f.result()
            if not hasEmail:
                users.pop(userName)
            else:
                users[userName]['attributes'] = userAttributes

        logger.info('Fetching keys for users individually')
        with concurrent.futures.ThreadPoolExecutor(10) as executor:
            results = [executor.submit(fetch_user_keys, user) for user in users]

        for f in concurrent.futures.as_completed(results):
            userName, keys = f.result()
            users[userName]['keys'] = keys
    except ClientError as ce:
        logger.error(ce)

    return users

def create_user_key(userName, user):
    if len(user['keys']) == 0:
        logger.info('Skipping key creation for {} because no existing key found'.format(userName))
    elif len(user['keys']) == 2:
        logger.warn('Skipping key creation {} because 2 keys already exist. Please delete anyone to create new key'.format(userName))
    else:
        for k in user['keys']:
            rotationAge = user['attributes']['rotate_after'] if 'rotate_after' in user['attributes'] else ACCESS_KEY_AGE
            if k['ak_age_days'] <= rotationAge:
                logger.info('Skipping key creation for {} because existing key is only {} day(s) old and the rotation is set for {} days'.format(userName, k['ak_age_days'], rotationAge))
            else:
                logger.info('Creating new access key for {}'.format(userName))
                resp = iam.create_access_key(
                    UserName=userName
                )

                # Email keys to user
                send_email(user['email'], userName, resp['AccessKey']['AccessKeyId'], resp['AccessKey']['SecretAccessKey'], user['keys'][0]['ak'])

                # Mark exisiting key to destory after X days
                mark_key_for_destroy(userName, user['keys'][0]['ak'], user['email'])

def create_user_keys(users):
    with concurrent.futures.ThreadPoolExecutor(10) as executor:
        [executor.submit(create_user_key, user, users[user]) for user in users]

def send_email(email, userName, accessKey, secretKey, existingAccessKey):
    mailBody = '<html><head><title>{}</title></head><body>Hey &#x1F44B; {},<br/><br/>A new access key pair has been generated for you. Please update the same wherever necessary.<br/><br/>Access Key: <strong>{}</strong><br/>Secret Access Key: <strong>{}</strong><br/><br/><strong>Note:</strong> Existing key pair <strong>{}</strong> will be deleted after {} days so please update the new key pair wherever required.<br/><br/>Thanks,<br/>Your Security Team</body></html>'.format('New Access Key Pair', userName, accessKey, secretKey, existingAccessKey, DAYS_FOR_DELETION)
    try:
        if MAIL_CLIENT == 'ses':
            import ses_mailer
            ses_mailer.send_email(email, userName, MAIL_FROM, mailBody)
        elif MAIL_CLIENT == 'mailgun':
            import mailgun_mailer
            mailgun_mailer.send_email(email, userName, MAIL_FROM, mailBody)
        else:
            logger.error('{}: Invalid mailer client. Supported mail clients: AWS SES and Mailgun'.format(MAIL_CLIENT))
    except (Exception, ClientError) as ce:
        logger.error('Failed to send mail to user {} ({}). Reason: {}'.format(userName, email, ce))

def mark_key_for_destroy(userName, ak, email):
    try:
        today = date.today()
        dynamodb.put_item(
            TableName=IAM_KEY_ROTATOR_TABLE,
            Item={
                'user': {
                    'S': userName
                },
                'ak': {
                    'S': ak
                },
                'email': {
                    'S': email
                },
                'delete_on': {
                    'N': str(round(datetime(today.year, today.month, today.day, tzinfo=pytz.utc).timestamp()) + (DAYS_FOR_DELETION * 24 * 60 * 60))
                }
            }
        )
        logger.info('Key {} marked for deletion'.format(ak))
    except (Exception, ClientError) as ce:
        logger.error('Failed to mark key {} for deletion. Reason: {}'.format(ak, ce))

def handler(event, context):
    users = fetch_user_details()
    create_user_keys(users)
