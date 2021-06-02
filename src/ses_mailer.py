import boto3
import os
import logging

ses = boto3.client('ses', region_name=os.environ.get('AWS_REGION'))

logger = logging.getLogger('ses-mailer')
logger.setLevel(logging.INFO)

def send_email(email, userName, mailFrom, mailBody):
    logger.info('Sending mail to {} ({}) via AWS SES'.format(userName, email))
    ses.send_email(
        Source='{}'.format(mailFrom),
        Destination={
            'ToAddresses': [
                email
            ]
        },
        Message={
            'Subject': {
                'Data': 'New Access Key Pair'
            },
            'Body': {
                'Html': {
                    'Data': mailBody,
                    'Charset': 'UTF-8'
                }
            }
        }
    )
    logger.info('Mail sent to {} ({}) via AWS SES'.format(userName, email))
