import boto3
import os
import smtplib
import ssl
import logging

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

ssm = boto3.client('ssm', region_name=os.environ.get('AWS_REGION'))

logger = logging.getLogger('smtp-mailer')
logger.setLevel(logging.INFO)

# Whether to use SSL or TLS for sending mail
SMTP_PROTOCOL = os.environ.get('SMTP_PROTOCOL', 'ssl')

# Port number to use for connecting to SMTP server
SMTP_PORT = os.environ.get('SMTP_PORT', 465)

# Host name of server to connect
SMTP_SERVER = os.environ.get('SMTP_SERVER', None)

# SSM Parameter name which holds SMTP server password
SMTP_PASSWORD_PARAMETER = os.environ.get('SMTP_PASSWORD_PARAMETER')

def send_via_ssl(mailFrom, smtpPassword, mailTo, mailBody):
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(mailFrom, smtpPassword)
            server.sendmail(mailFrom, mailTo, mailBody)
    except Exception as e:
        logger.error('Unable to send mail via SSL to {}. Reason: {}'.format(mailTo, e))

def send_via_tls(mailFrom, smtpPassword, mailTo, mailBody):
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(mailFrom, smtpPassword)
            server.sendmail(mailFrom, mailTo, mailBody)
    except Exception as e:
        logger.error('Unable to send mail via TLS to {}. Reason: {}'.format(mailTo, e))

def send_email(mailTo, userName, mailSubject, mailFrom, mailBodyPlain, mailBodyHtml):
    if SMTP_SERVER is None:
        logger.error('SMTP_SERVER value cannot be blank')
        return False

    logger.info('Fetching SMTP password from SSM')
    resp = ssm.get_parameter(
        Name=SMTP_PASSWORD_PARAMETER,
        WithDecryption=True
    )
    smtpPassword = resp['Parameter']['Value']

    message = MIMEMultipart("alternative")
    message["Subject"] = mailSubject
    message["From"] = mailFrom
    message["To"] = mailTo

    mailBodyPlain = MIMEText(mailBodyPlain, 'plain')
    mailBodyHtml = MIMEText(mailBodyHtml, 'html')

    message.attach(mailBodyPlain)
    message.attach(mailBodyHtml)

    if SMTP_PROTOCOL.lower() == 'ssl':
        logger.info('Using SSL for sending mail to {}'.format(userName))
        send_via_ssl(mailFrom, smtpPassword, mailTo, message.as_string())
    elif SMTP_PROTOCOL.lower() == 'tls':
        logger.info('Using TLS for sending mail to {}'.format(userName))
        send_via_ssl(mailFrom, smtpPassword, mailTo, message.as_string())
    else:
        logger.error('{} is not a supported SMTP protocol'.format(SMTP_PROTOCOL))
