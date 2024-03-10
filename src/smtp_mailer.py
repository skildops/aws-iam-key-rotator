"""
Send email through SMTP server
"""

import os
import smtplib
import ssl
import logging
import boto3

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION"))

logger = logging.getLogger("smtp-mailer")
logger.setLevel(logging.INFO)

# Whether to use SSL or TLS for sending mail
SMTP_PROTOCOL = os.environ.get("SMTP_PROTOCOL", "ssl")

# Port number to use for connecting to SMTP server
SMTP_PORT = os.environ.get("SMTP_PORT", 465)

# Host name of server to connect
SMTP_SERVER = os.environ.get("SMTP_SERVER", None)

# SSM Parameter name which holds SMTP server password
SMTP_PASSWORD_PARAMETER = os.environ.get("SMTP_PASSWORD_PARAMETER")


def send_via_ssl(user_name, mail_from, smtp_password, mail_to, mail_body):
    """
    Send email via SMTP over SSL
    """
    try:
        logger.info("Sending mail to %f (%f) via SMTP over SSL", user_name, mail_to)
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(mail_from, smtp_password)
            server.sendmail(mail_from, mail_to, mail_body)
        logger.info("Mail sent to %s (%s) via SMTP over SSL", user_name, mail_to)
    except Exception as ex:
        logger.error("Unable to send mail via SSL to %s. Reason: %s", mail_to, ex)


def send_via_tls(user_name, mail_from, smtp_password, mail_to, mail_body):
    """
    Send email via SMTP over TLS
    """
    try:
        logger.info("Sending mail to %s (%s) via SMTP over TLS", user_name, mail_to)
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(mail_from, smtp_password)
            server.sendmail(mail_from, mail_to, mail_body)
        logger.info("Mail sent to %s (%s) via SMTP over TLS", user_name, mail_to)
    except Exception as ex:
        logger.error("Unable to send mail via TLS to %s. Reason: %s", mail_to, ex)


def send_email(
    mail_to, user_name, mail_subject, mail_from, mail_body_plain, mail_body_html
):
    """
    Prepares message and decides if email will be sent over SSL or TLS
    """
    if SMTP_SERVER is None:
        logger.error("SMTP_SERVER value cannot be blank")
        return False

    logger.info("Fetching SMTP password from SSM")
    resp = ssm.get_parameter(Name=SMTP_PASSWORD_PARAMETER, WithDecryption=True)
    smtp_password = resp["Parameter"]["Value"]

    message = MIMEMultipart("alternative")
    message["Subject"] = mail_subject
    message["From"] = mail_from
    message["To"] = mail_to

    mail_body_plain = MIMEText(mail_body_plain, "plain")
    mail_body_html = MIMEText(mail_body_html, "html")

    message.attach(mail_body_plain)
    message.attach(mail_body_html)

    if SMTP_PROTOCOL.lower() == "ssl":
        send_via_ssl(user_name, mail_from, smtp_password, mail_to, message.as_string())
    elif SMTP_PROTOCOL.lower() == "tls":
        send_via_tls(user_name, mail_from, smtp_password, mail_to, message.as_string())
    else:
        logger.error("%s is not a supported SMTP protocol", SMTP_PROTOCOL)
