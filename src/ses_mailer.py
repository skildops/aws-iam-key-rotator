import boto3
import os
import logging

ses = boto3.client('ses', region_name=os.environ.get('AWS_REGION'))

logger = logging.getLogger('ses-mailer')
logger.setLevel(logging.INFO)

def send_email(mailTo, userName, mailSubject, mailFrom, mailBodyPlain, mailBodyHtml):
    logger.info('Sending mail to {} ({}) via AWS SES'.format(userName, mailTo))
    ses.send_email(
        Source='{}'.format(mailFrom),
        Destination={
            'ToAddresses': [
                mailTo
            ]
        },
        Message={
            'Subject': {
                'Data': mailSubject
            },
            'Body': {
                'Text': {
                    'Data': mailBodyPlain,
                    'Charset': 'UTF-8'
                },
                'Html': {
                    'Data': mailBodyHtml,
                    'Charset': 'UTF-8'
                }
            }
        }
    )
    logger.info('Mail sent to {} ({}) via AWS SES'.format(userName, mailTo))
