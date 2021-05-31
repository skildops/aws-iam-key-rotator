import boto3
import os
import requests
import logging

ssm = boto3.client('ssm', region_name=os.environ.get('AWS_REGION'))

# Mailgun API URL for sending email
MAILGUN_API_URL = os.environ.get('MAILGUN_API_URL')

# Name of SSM Parameter which holds Mailgun API key
MAILGUN_API_KEY_NAME = os.environ.get('MAILGUN_API_KEY_NAME')

logger = logging.getLogger('mailgun-mailer')
logger.setLevel(logging.INFO)

def send_email(email, userName, mailFrom, mailBody):
    logger.info('Fetching API key for SSM')
    resp = ssm.get_parameter(
        Name=MAILGUN_API_KEY_NAME,
        WithDecryption=True
    )
    apiKey = resp['Parameter']['Value']

    logger.info('Sending mail to {} ({}) via Mailgun'.format(userName, email))
    resp = requests.post(MAILGUN_API_URL, auth=("api", apiKey),
        data={"from": mailFrom,
              "to": [email],
              "subject": "New Access Key Pair",
              "html": mailBody})
    respBody = resp.json()

    if 'message' in respBody and respBody['message'] == 'Queued. Thank you.':
        logger.info('Mail sent to {} ({}) via Mailgun'.format(userName, email))
    else:
        logger.error('Mailgun was unable to send mail to {} ({}). Reason: {}'.format(userName, email, respBody['message']))
