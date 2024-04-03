"""
Send email via Mailgun service
"""

import os
import logging
import requests
import boto3


ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION"))

# Mailgun API URL for sending email
MAILGUN_API_URL = os.environ.get("MAILGUN_API_URL", None)

# Name of SSM Parameter which holds Mailgun API key
MAILGUN_API_KEY_NAME = os.environ.get("MAILGUN_API_KEY_NAME", None)

logger = logging.getLogger("mailgun-mailer")
logger.setLevel(logging.INFO)


def send_email(
    mail_to, user_name, mail_subject, mail_from, mail_body_plain, mail_body_html
):
    """
    Trigger Mailgun API via REST to send email
    """
    if MAILGUN_API_URL is None or MAILGUN_API_KEY_NAME is None:
        logger.error(
            "Both MAILGUN_API_URL and MAILGUN_API_KEY_NAME is required for sending mail via Mailgun. Current values: MAILGUN_API_URL = %s and MAILGUN_API_KEY_NAME = %s",
            MAILGUN_API_URL,
            MAILGUN_API_KEY_NAME,
        )
        return False

    logger.info("Fetching Mailgun API key from SSM")
    resp = ssm.get_parameter(Name=MAILGUN_API_KEY_NAME, WithDecryption=True)
    api_key = resp["Parameter"]["Value"]

    logger.info("Sending mail to %s (%s) via Mailgun", user_name, mail_to)
    resp = requests.post(
        MAILGUN_API_URL,
        auth=("api", api_key),
        timeout=3,
        data={
            "from": mail_from,
            "to": [mail_to],
            "subject": mail_subject,
            "text": mail_body_plain,
            "html": mail_body_html,
        },
    )
    resp_body = resp.json()

    if "message" in resp_body and resp_body["message"] == "Queued. Thank you.":
        logger.info("Mail sent to %s (%s) via Mailgun", user_name, mail_to)
    else:
        logger.error(
            "Mailgun was unable to send mail to %s (%s). Reason: %s",
            user_name,
            mail_to,
            resp_body["message"],
        )
