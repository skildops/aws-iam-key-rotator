import boto3
import os
import logging

from botocore.exceptions import ClientError

MAIL_FROM = os.environ.get('MAIL_FROM')

ses = boto3.client('ses', region_name=os.environ.get('AWS_REGION'))

logger = logging.getLogger('ses-mailer')
logger.setLevel(logging.INFO)

def send_email(email, userName, accessKey, secretKey, existingAccessKey):
    logger.info('Sending mail to {} ({})'.format(userName, email))
    try:
        ses.send_email(
            Source='{}'.format(MAIL_FROM),
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
                        'Data': '<html><head><title>{}</title></head><body>Hey &#x1F44B; {},<br/><br/>A new access key pair has been generated for you. Please update the same wherever necessary.<br/><br/>Access Key: <strong>{}</strong><br/>Secret Access Key: <strong>{}</strong><br/><br/><strong>Note:</strong> Existing key pair <strong>{}</strong> will be deleted after {} days so please update the new key pair wherever required.<br/><br/>Thanks,<br/>Your Security Team</body></html>'.format('New Access Key Pair', userName, accessKey, secretKey, existingAccessKey, DAYS_FOR_DELETION),
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        logger.info('Mail sent to {} ({}) via AWS SES'.format(userName, email))
    except (Exception, ClientError) as ce:
        logger.error('Failed to send mail to user {} ({}). Reason: {}'.format(userName, email, ce))
