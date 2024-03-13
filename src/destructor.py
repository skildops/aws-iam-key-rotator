"""
The file will be triggered by a DynamoDB stream to delete an IAM key pair
"""

import os
import logging
import concurrent.futures
import boto3

from botocore.exceptions import ClientError

import shared_functions

# Table name which holds existing access key pair details to be deleted
IAM_KEY_ROTATOR_TABLE = os.environ.get("IAM_KEY_ROTATOR_TABLE", None)

# In case lambda fails to delete the old key, how long should it wait before the next try
RETRY_AFTER_MINS = int(os.environ.get("RETRY_AFTER_MINS", 5))

# Mail client to use for sending new key creation or existing key deletion mail
MAIL_CLIENT = os.environ.get("MAIL_CLIENT", "ses")

# From address to be used while sending mail
MAIL_FROM = os.environ.get("MAIL_FROM", None)

# AWS_REGION is by default available within lambda environment
iam = boto3.client("iam", region_name=os.environ.get("AWS_REGION"))
ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION"))
ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION"))
dynamodb = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION"))

logger = logging.getLogger("destructor")
logger.setLevel(logging.INFO)


def send_email(email, user_name, existing_access_key):
    """
    Send email about key pair deletion
    """
    # fetch aws account info
    account_id = shared_functions.fetch_account_info()["id"]
    account_name = shared_functions.fetch_account_info()["name"]

    mail_subject = "Old Access Key Pair Deleted"

    mail_body_plain = f"""
    Hey {user_name},\n
    An existing access key pair associated to your username
    has been deleted because it reached End-Of-Life.\n\n
    Account: {account_id} ({account_name})\n
    Access Key: {existing_access_key}\n\n
    Thanks,\n
    Your Security Team"""

    mail_body_html = (
        """
    <!DOCTYPE html>
    <html style="font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
                    box-sizing: border-box; font-size: 14px; margin: 0;">
        <head>
            <meta name="viewport" content="width=device-width" />
            <meta http-equiv="Content-Type" content="text/html charset=UTF-8" />
            <title>%s</title>
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
            <p>Hey &#x1F44B; %s,</p>
            <p>An existing access key pair associated to your
                username has been deleted because it reached End-Of-Life.<p/>
            <p>
                Account: <strong>%s (%s)</strong>
                <br/>
                Access Key: <strong>%s</strong>
            </p>
            <p>
                Thanks,<br/>
                Your Security Team
            </p>
        </body>
    </html>""",
        mail_subject,
        user_name,
        account_id,
        account_name,
        existing_access_key,
    )
    try:
        logger.info("Using %s as mail client", MAIL_CLIENT)
        if MAIL_CLIENT == "smtp":
            import smtp_mailer

            smtp_mailer.send_email(
                email,
                user_name,
                mail_subject,
                MAIL_FROM,
                mail_body_plain,
                mail_body_html,
            )
        elif MAIL_CLIENT == "ses":
            import ses_mailer

            ses_mailer.send_email(
                email,
                user_name,
                mail_subject,
                MAIL_FROM,
                mail_body_plain,
                mail_body_html,
            )
        elif MAIL_CLIENT == "mailgun":
            import mailgun_mailer

            mailgun_mailer.send_email(
                email,
                user_name,
                mail_subject,
                MAIL_FROM,
                mail_body_plain,
                mail_body_html,
            )
        else:
            logger.error(
                "%s: Invalid mail client. Supported mail clients: AWS SES and Mailgun",
                MAIL_CLIENT,
            )
    except (Exception, ClientError) as ce:
        logger.error(
            "Failed to send mail to user %s (%s). Reason: %s", user_name, email, ce
        )


def delete_encryption_key(user_name):
    """
    Delete encryption key stored in SSM parameter store
    """
    try:
        logger.info("Deleting encryption key for %s user", user_name)
        ssm.delete_parameter(Name=f"/ikr/secret/iam/{user_name}")
        logger.info("Encryption key deleted for %s user", user_name)
    except ClientError as ce:
        logger.error(
            "Unable to delete encryption key for %s user. Reason: %s", user_name, ce
        )
        return False

    return True


def destroy_user_key(rec):
    """
    Delete IAM key pair if DynamoDB event type is remove
    """
    if rec["eventName"] == "REMOVE":
        key = rec["dynamodb"]["OldImage"]
        user_name = key["user"]["S"]
        user_email = key["email"]["S"]
        access_key = key["ak"]["S"]
        del_enc_key = key["delete_enc_key"]["S"]
        enc_key_deleted = False
        try:
            logger.info(
                "Deleting access key %s assocaited with user %s", access_key, user_name
            )
            iam.delete_access_key(UserName=user_name, AccessKeyId=access_key)
            logger.info("Access Key %s has been deleted", access_key)

            # Delete user encryption key stored in ssm
            if del_enc_key == "Y":
                enc_key_deleted = delete_encryption_key(user_name)

            # Send mail to user about key deletion
            send_email(user_email, user_name, access_key)
        except (Exception, ClientError) as ce:
            logger.error("Failed to delete access key %s. Reason: %s", access_key, ce)
            logger.info("Adding access key %s back to the database", access_key)

            dynamodb.put_item(
                TableName=IAM_KEY_ROTATOR_TABLE,
                Item={
                    "user": {"S": user_name},
                    "ak": {"S": access_key},
                    "email": {"S": user_email},
                    "delete_on": {
                        "N": str(int(key["delete_on"]["N"]) + (RETRY_AFTER_MINS * 60))
                    },
                    "delete_enc_key": {
                        "S": "N"
                        if del_enc_key == "Y" and enc_key_deleted
                        else del_enc_key
                    },
                },
            )
            logger.info("Access key %s added back to the database", access_key)
    else:
        logger.info("Skipping as it is not a delete event")


def destroy_user_keys(records):
    """
    Delete key pairs in parallel
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        [executor.submit(destroy_user_key(rec)) for rec in records]


def handler(event, context):
    """
    Lambda entrypoint function
    """
    if IAM_KEY_ROTATOR_TABLE is None:
        logger.error(
            "IAM_KEY_ROTATOR_TABLE is required. Current value: %s",
            IAM_KEY_ROTATOR_TABLE,
        )
    elif MAIL_FROM is None:
        logger.error("MAIL_FROM is required. Current value: %s", MAIL_FROM)
    else:
        destroy_user_keys(event["Records"])
