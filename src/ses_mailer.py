"""
Send email via AWS SES service
"""

import os
import logging
import boto3

ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION"))

logger = logging.getLogger("ses-mailer")
logger.setLevel(logging.INFO)


def send_email(
    mail_to, user_name, mail_subject, mail_from, mail_body_plain, mail_body_html
):
    """
    Use AWS SDK to send email via SES
    """
    logger.info("Sending mail to %s (%s) via AWS SES", user_name, mail_to)
    ses.send_email(
        Source=f"{mail_from}",
        Destination={"ToAddresses": [mail_to]},
        Message={
            "Subject": {"Data": mail_subject},
            "Body": {
                "Text": {"Data": mail_body_plain, "Charset": "UTF-8"},
                "Html": {"Data": mail_body_html, "Charset": "UTF-8"},
            },
        },
    )
    logger.info("Mail sent to %s (%s) via AWS SES", user_name, mail_to)
