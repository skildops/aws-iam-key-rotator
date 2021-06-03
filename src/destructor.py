import boto3
import os
import logging
import concurrent.futures

from botocore.exceptions import ClientError

# Table name which holds existing access key pair details to be deleted
IAM_KEY_ROTATOR_TABLE = os.environ.get('IAM_KEY_ROTATOR_TABLE', None)

# In case lambda fails to delete the key, how long should it wait before next try
RETRY_AFTER_MINS = os.environ.get('RETRY_AFTER_MINS', 5)

# Mail client to use for sending new key creation or existing key deletion mail
MAIL_CLIENT = os.environ.get('MAIL_CLIENT', 'ses')

# From address to be used while sending mail
MAIL_FROM = os.environ.get('MAIL_FROM', None)

# AWS_REGION is by default available within lambda environment
iam = boto3.client('iam', region_name=os.environ.get('AWS_REGION'))
ses = boto3.client('ses', region_name=os.environ.get('AWS_REGION'))
dynamodb = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION'))

logger = logging.getLogger('destructor')
logger.setLevel(logging.INFO)

def send_email(email, userName, existingAccessKey):
    mailBody = '<html><head><title>{}</title></head><body>Hey &#x1F44B; {},<br/><br/>An existing access key pair assocaited to your username has been deleted because it reached End-Of-Life. <br/><br/>Access Key: <strong>{}</strong><br/><br/>Thanks,<br/>Your Security Team</body></html>'.format('Old Access Key Pair Deleted', userName, existingAccessKey)
    try:
        logger.info('Using {} as mail client'.format(MAIL_CLIENT))
        if MAIL_CLIENT == 'ses':
            import ses_mailer
            ses_mailer.send_email(email, userName, MAIL_FROM, mailBody)
        elif MAIL_CLIENT == 'mailgun':
            import mailgun_mailer
            mailgun_mailer.send_email(email, userName, MAIL_FROM, mailBody)
        else:
            logger.error('{}: Invalid mail client. Supported mail clients: AWS SES and Mailgun'.format(MAIL_CLIENT))
    except (Exception, ClientError) as ce:
        logger.error('Failed to send mail to user {} ({}). Reason: {}'.format(userName, email, ce))

def destroy_user_key(rec):
    if rec['eventName'] == 'REMOVE':
        key = rec['dynamodb']['OldImage']
        userName = key['user']['S']
        userEmail = key['email']['S']
        accessKey = key['ak']['S']
        try:
            logger.info('Deleting access key {} assocaited with user {}'.format(accessKey, userName))
            iam.delete_access_key(
                UserName=userName,
                AccessKeyId=accessKey
            )
            logger.info('Access Key {} has been deleted'.format(accessKey))

            # Send mail to user about key deletion
            send_email(userEmail, userName, accessKey)
        except (Exception, ClientError) as ce:
            logger.error('Failed to delete access key {}. Reason: {}'.format(accessKey, ce))
            logger.info('Adding access key {} back to the database'.format(accessKey))
            dynamodb.put_item(
                TableName=IAM_KEY_ROTATOR_TABLE,
                Key={
                    'user': {
                        'S': userName
                    },
                    'ak': {
                        'S': accessKey
                    },
                    'email': {
                        'S': userEmail
                    },
                    'delete_on': {
                        'N': str(int(key['delete_on']['N']) + (RETRY_AFTER_MINS * 60))
                    }
                }
            )
            logger.info('Access key {} added back to the database'.format(accessKey))
    else:
        logger.info('Skipping as it is not a delete event')

def destroy_user_keys(records):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        [executor.submit(destroy_user_key(rec)) for rec in records]

def handler(event, context):
    if IAM_KEY_ROTATOR_TABLE is None:
        logger.error('IAM_KEY_ROTATOR_TABLE is required. Current value: {}'.format(IAM_KEY_ROTATOR_TABLE))
    elif MAIL_FROM is None:
        logger.error('MAIL_FROM is required. Current value: {}'.format(MAIL_FROM))
    else:
        destroy_user_keys(event['Records'])
