import boto3
import os
import logging
import concurrent.futures
import pytz

from datetime import datetime, date
from botocore.exceptions import ClientError

# Table name which holds existing access key pair details to be deleted
IAM_KEY_ROTATOR_TABLE = os.environ.get('IAM_KEY_ROTATOR_TABLE', None)

# Days after which a new access key pair should be generated
ROTATE_AFTER_DAYS = os.environ.get('ROTATE_AFTER_DAYS', 85)

# No. of days to wait for deleting existing key pair after a new key pair is generated
DELETE_AFTER_DAYS = os.environ.get('DELETE_AFTER_DAYS', 5)

# Mail client to use for sending new key creation or existing key deletion mail
MAIL_CLIENT = os.environ.get('MAIL_CLIENT', 'ses')

# From address to be used while sending mail
MAIL_FROM = os.environ.get('MAIL_FROM', None)

# AWS_REGION environment variable is by default available within lambda environment
iam = boto3.client('iam', region_name=os.environ.get('AWS_REGION'))
dynamodb = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION'))

logger = logging.getLogger('creator')
logger.setLevel(logging.INFO)

def prepare_instruction(keyUpdateInstructions):
    sortedKeys = sorted(keyUpdateInstructions)
    preparedInstruction = [keyUpdateInstructions[k] for k in sortedKeys]
    return ' '.join(preparedInstruction)

def fetch_users_with_email(user):
    logger.info('Fetching tags for {}'.format(user))
    resp = iam.list_user_tags(
        UserName=user
    )

    userAttributes = {}
    keyUpdateInstructions = {}
    for t in resp['Tags']:
        if t['Key'].lower() == 'ikr:email':
            userAttributes['email'] = t['Value']

        if t['Key'].lower() == 'ikr:rotate_after_days':
            userAttributes['rotate_after'] = t['Value']

        if t['Key'].lower() == 'ikr:delete_after_days':
            userAttributes['delete_after'] = t['Value']

        if t['Key'].lower().startswith('ikr:instruction_'):
            keyUpdateInstructions[int(t['Key'].split('_')[1])] = t['Value']

    if len(keyUpdateInstructions) > 0:
        userAttributes['instruction'] = prepare_instruction(keyUpdateInstructions)
    else:
        userAttributes['instruction'] = ''

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
        logging.info('User count: {}'.format(len(users)))

        logger.info('Fetching tags for users individually')
        with concurrent.futures.ThreadPoolExecutor(10) as executor:
            results = [executor.submit(fetch_users_with_email, user) for user in users]

        for f in concurrent.futures.as_completed(results):
            hasEmail, userName, userAttributes = f.result()
            if not hasEmail:
                users.pop(userName)
            else:
                users[userName]['attributes'] = userAttributes
        logger.info('User(s) with email tag: {}'.format([user for user in users]))

        logger.info('Fetching keys for users individually')
        with concurrent.futures.ThreadPoolExecutor(10) as executor:
            results = [executor.submit(fetch_user_keys, user) for user in users]

        for f in concurrent.futures.as_completed(results):
            userName, keys = f.result()
            users[userName]['keys'] = keys
    except ClientError as ce:
        logger.error(ce)

    return users

def send_email(email, userName, accessKey, secretKey, instruction, existingAccessKey, existingKeyDeleteAge):
    try:
        mailSubject = 'New Access Key Pair'
        mailBodyPlain = 'Hey {},\n\nA new access key pair has been generated for you. Please update the same wherever necessary.\n\nAccess Key: {}\nSecret Access Key: {}\nInstruction: {}\n\nNote: Existing key pair {} will be deleted after {} days so please update the key pair wherever required.\n\nThanks,\nYour Security Team'.format(mailSubject, userName, accessKey, secretKey, instruction, existingAccessKey, existingKeyDeleteAge)
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
                <p>A new access key pair has been generated for you. Please update the same wherever necessary.</p>
                <p>
                    Access Key: <b>{}</b>
                    <br/>
                    Secret Access Key: <b>{}</b>
                    <br/>
                    Instruction: <b>{}</b>
                </p>
                <p><b>Note:</b> Existing key pair <b>{}</b> will be deleted after <b>{}</b> days so please update the key pair wherever required.</p>
                <p>Thanks,<br/>
                Your Security Team</p>
            </body>
        </html>'''.format(mailSubject, userName, accessKey, secretKey, instruction, existingAccessKey, existingKeyDeleteAge)

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

def mark_key_for_destroy(userName, ak, existingKeyDeleteAge, email):
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
                    'N': str(round(datetime(today.year, today.month, today.day, tzinfo=pytz.utc).timestamp()) + (existingKeyDeleteAge * 24 * 60 * 60))
                }
            }
        )
        logger.info('Key {} marked for deletion'.format(ak))
    except (Exception, ClientError) as ce:
        logger.error('Failed to mark key {} for deletion. Reason: {}'.format(ak, ce))

def create_user_key(userName, user):
    try:
        if len(user['keys']) == 0:
            logger.info('Skipping key creation for {} because no existing key found'.format(userName))
        elif len(user['keys']) == 2:
            logger.warn('Skipping key creation for {} because 2 keys already exist. Please delete anyone to create new key'.format(userName))
        else:
            for k in user['keys']:
                keyRotationAge = user['attributes']['rotate_after'] if 'rotate_after' in user['attributes'] else ROTATE_AFTER_DAYS
                if k['ak_age_days'] <= int(keyRotationAge):
                    logger.info('Skipping key creation for {} because existing key is only {} day(s) old and the rotation is set for {} days'.format(userName, k['ak_age_days'], keyRotationAge))
                else:
                    logger.info('Creating new access key for {}'.format(userName))
                    resp = iam.create_access_key(
                        UserName=userName
                    )
                    logger.info('New key pair generated for user {}'.format(userName))

                    # Email keys to user
                    existingKeyDeleteAge = user['attributes']['delete_after'] if 'delete_after' in user['attributes'] else DELETE_AFTER_DAYS
                    send_email(user['attributes']['email'], userName, resp['AccessKey']['AccessKeyId'], resp['AccessKey']['SecretAccessKey'], user['attributes']['instruction'], user['keys'][0]['ak'], int(existingKeyDeleteAge))

                    # Mark exisiting key to destory after X days
                    mark_key_for_destroy(userName, user['keys'][0]['ak'], int(existingKeyDeleteAge), user['attributes']['email'])
    except (Exception, ClientError) as ce:
        logger.error('Failed to create new key pair. Reason: {}'.format(ce))

def create_user_keys(users):
    with concurrent.futures.ThreadPoolExecutor(10) as executor:
        [executor.submit(create_user_key, user, users[user]) for user in users]

def handler(event, context):
    if IAM_KEY_ROTATOR_TABLE is None:
        logger.error('IAM_KEY_ROTATOR_TABLE is required. Current value: {}'.format(IAM_KEY_ROTATOR_TABLE))
    elif MAIL_FROM is None:
        logger.error('MAIL_FROM is required. Current value: {}'.format(MAIL_FROM))
    else:
        users = fetch_user_details()
        create_user_keys(users)
