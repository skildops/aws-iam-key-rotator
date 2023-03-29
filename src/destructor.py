import boto3
import os
import logging
import concurrent.futures

from botocore.exceptions import ClientError

import shared_functions

# Table name which holds existing access key pair details to be deleted
IAM_KEY_ROTATOR_TABLE = os.environ.get('IAM_KEY_ROTATOR_TABLE', None)

# In case lambda fails to delete the old key, how long should it wait before the next try
RETRY_AFTER_MINS = os.environ.get('RETRY_AFTER_MINS', 5)

# Mail client to use for sending new key creation or existing key deletion mail
MAIL_CLIENT = os.environ.get('MAIL_CLIENT', 'ses')

# From address to be used while sending mail
MAIL_FROM = os.environ.get('MAIL_FROM', None)

# AWS_REGION is by default available within lambda environment
iam = boto3.client('iam', region_name=os.environ.get('AWS_REGION'))
ses = boto3.client('ses', region_name=os.environ.get('AWS_REGION'))
ssm = boto3.client('ssm', region_name=os.environ.get('AWS_REGION'))
dynamodb = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION'))

logger = logging.getLogger('destructor')
logger.setLevel(logging.INFO)

def send_email(email, userName, existingAccessKey):
    mailSubject = 'Old Access Key Pair Deleted'
    mailBodyPlain = 'Hey {},\nAn existing access key pair associated to your username has been deleted because it reached End-Of-Life.\n\nAccount: {} ({})\nAccess Key: {}\n\nThanks,\nYour Security Team'.format(userName, shared_functions.fetch_account_info()['id'], shared_functions.fetch_account_info()['name'], existingAccessKey)
    mailBodyHtml = '''
    <!DOCTYPE html>
    <html style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;">
        <head>
            <meta name="viewport" content="width=device-width" />
            <meta http-equiv="Content-Type" content="text/html charset=UTF-8" />
            <title>{}</title>
            <style type="text/css">
                body {{
                    -webkit-font-smoothing: antialiased;
                    -webkit-text-size-adjust: none;
                    width: 100% !important;
                    height: 100%;
                    line-height: 1.6em;
                }}
            </style>
        </head>
        <body>
            <p>Hey &#x1F44B; {},</p>
            <p>An existing access key pair associated to your username has been deleted because it reached End-Of-Life.<p/>
            <p>
                Account: <strong>{} ({})</strong>
                <br/>
                Access Key: <strong>{}</strong>
            </p>
            <p>
                Thanks,<br/>
                Your Security Team
            </p>
        </body>
    </html>'''.format(mailSubject, userName, shared_functions.fetch_account_info()['id'], shared_functions.fetch_account_info()['name'], existingAccessKey)
    try:
        logger.info('Using {} as mail client'.format(MAIL_CLIENT))
        if MAIL_CLIENT == 'smtp':
            import smtp_mailer
            smtp_mailer.send_email(email, userName, mailSubject, MAIL_FROM, mailBodyPlain, mailBodyHtml)
        elif MAIL_CLIENT == 'ses':
            import ses_mailer
            ses_mailer.send_email(email, userName, mailSubject, MAIL_FROM, mailBodyPlain, mailBodyHtml)
        elif MAIL_CLIENT == 'mailgun':
            import mailgun_mailer
            mailgun_mailer.send_email(email, userName, mailSubject, MAIL_FROM, mailBodyPlain, mailBodyHtml)
        else:
            logger.error('{}: Invalid mail client. Supported mail clients: AWS SES and Mailgun'.format(MAIL_CLIENT))
    except (Exception, ClientError) as ce:
        logger.error('Failed to send mail to user {} ({}). Reason: {}'.format(userName, email, ce))

def delete_encryption_key(userName):
    try:
        logger.info('Deleting encryption key for {} user'.format(userName))
        ssm.delete_parameter(
            Name='/ikr/secret/iam/{}'.format(userName)
        )
        logger.info('Encryption key deleted for {} user'.format(userName))
    except ClientError as ce:
        logger.error('Unable to delete encryption key for {} user. Reason: {}'.format(userName, ce))

def destroy_user_key(rec):
    if rec['eventName'] == 'REMOVE':
        key = rec['dynamodb']['OldImage']
        userName = key['user']['S']
        userEmail = key['email']['S']
        accessKey = key['ak']['S']
        isEncrypted = key['is_encrypted']['S']
        try:
            logger.info('Deleting access key {} assocaited with user {}'.format(accessKey, userName))
            iam.delete_access_key(
                UserName=userName,
                AccessKeyId=accessKey
            )
            logger.info('Access Key {} has been deleted'.format(accessKey))

            # Delete user encryption key stored in ssm
            delete_encryption_key(userName)

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
                    },
                    'is_encrypted': {
                        'S': isEncrypted
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
