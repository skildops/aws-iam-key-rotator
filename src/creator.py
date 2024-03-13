"""
Generates new key pair, notifies user and schedules deletion of old key pair
"""

import os
import logging
import concurrent.futures
import pytz
import boto3

from datetime import datetime, date
from botocore.exceptions import ClientError

import shared_functions
import encryption

# Table name which holds existing access key pair details to be deleted
IAM_KEY_ROTATOR_TABLE = os.environ.get("IAM_KEY_ROTATOR_TABLE", None)

# Days after which a new access key pair should be generated
ROTATE_AFTER_DAYS = os.environ.get("ROTATE_AFTER_DAYS", 85)

# No. of days to wait for deleting existing key pair after a new key pair is generated
DELETE_AFTER_DAYS = os.environ.get("DELETE_AFTER_DAYS", 5)

# Whether to share encrypted version of key pair
ENCRYPT_KEY_PAIR = os.environ.get("ENCRYPT_KEY_PAIR", True)

# Mail client to use for sending new key creation or existing key deletion mail
MAIL_CLIENT = os.environ.get("MAIL_CLIENT", "ses")

# From address to be used while sending mail
MAIL_FROM = os.environ.get("MAIL_FROM", None)

# AWS_REGION environment variable is by default available within lambda environment
iam = boto3.client("iam", region_name=os.environ.get("AWS_REGION"))
dynamodb = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION"))

logger = logging.getLogger("creator")
logger.setLevel(logging.INFO)


def prepare_instruction(key_update_instructions):
    """
    Joins instructions in ascending order and returns a string
    """
    sorted_keys = sorted(key_update_instructions)
    prepared_instruction = [key_update_instructions[k] for k in sorted_keys]
    return " ".join(prepared_instruction)


def fetch_users_with_email(user):
    """
    Checks if email is present as a tag and returns username and other tags if present
    """
    logger.info("Fetching tags for %s", user)
    resp = iam.list_user_tags(UserName=user)

    user_attributes = {}
    key_update_instructions = {}
    for t in resp["Tags"]:
        if t["Key"].lower().startswith("ikr:instruction_"):
            key_update_instructions[int(t["Key"].split("_")[1])] = t["Value"]
        elif t["Key"].lower().startswith("ikr:"):
            user_attributes[t["Key"].split(":")[1].lower()] = t["Value"]

    if len(key_update_instructions) > 0:
        user_attributes["instruction"] = prepare_instruction(key_update_instructions)
    else:
        user_attributes["instruction"] = ""

    if "email" in user_attributes:
        return True, user, user_attributes

    return False, user, None


def fetch_user_keys(user):
    """
    Fetch existing access key and age of the key associated with an IAM user
    """
    logger.info("Fetching keys for %s", user)
    resp = iam.list_access_keys(UserName=user)

    user_keys = []
    for obj in resp["AccessKeyMetadata"]:
        user_keys.append(
            {
                "ak": obj["AccessKeyId"],
                "ak_age_days": (datetime.now(pytz.UTC) - obj["CreateDate"]).days,
            }
        )

    return user, user_keys


def fetch_user_details():
    """
    Fetch list of users whose keys needs to be rotated periodically
    """
    users = {}
    try:
        params = {}
        logger.info("Fetching all users")
        while True:
            resp = iam.list_users(**params)

            for u in resp["Users"]:
                users[u["UserName"]] = {}

            try:
                params["Marker"] = resp["Marker"]
            except Exception:
                break

        logging.info("User count: %s", len(users))

        logger.info("Fetching tags for users individually")
        with concurrent.futures.ThreadPoolExecutor(10) as executor:
            results = [executor.submit(fetch_users_with_email, user) for user in users]

        for f in concurrent.futures.as_completed(results):
            has_email, user_name, user_attributes = f.result()
            if not has_email:
                users.pop(user_name)
            else:
                users[user_name]["attributes"] = user_attributes
        logger.info("User(s) with email tag: %s", [user for user in users])

        logger.info("Fetching keys for users individually")
        with concurrent.futures.ThreadPoolExecutor(10) as executor:
            results = [executor.submit(fetch_user_keys, user) for user in users]

        for f in concurrent.futures.as_completed(results):
            user_name, keys = f.result()
            users[user_name]["keys"] = keys
    except ClientError as ce:
        logger.error(ce)

    return users


def send_email(
    email,
    user_name,
    access_key,
    secret_key,
    instruction,
    existing_access_key,
    existing_key_delete_age,
):
    """
    Send new key pair to the user
    """
    try:
        # fetch aws account info
        account_id = shared_functions.fetch_account_info()["id"]
        account_name = shared_functions.fetch_account_info()["name"]

        mail_subject = "New Access Key Pair"

        mail_body_plain = f"""Hey {user_name},\n\n
        A new access key pair has been generated for you. Please update the same wherever necessary.\n\n
        Account: {account_id} ({account_name})\n
        Access Key: {access_key}\n
        Secret Access Key: {secret_key}\n
        Instruction: {instruction}\n\n
        Note: Existing key pair {existing_access_key} will be deleted after {existing_key_delete_age} days so please update the key pair wherever required.\n\n
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
                <p>A new access key pair has been generated for you.
                    Please update the same wherever necessary.</p>
                <p>
                    Account: <b>%s (%s)</b>
                    <br/>
                    Access Key: <b>%s</b>
                    <br/>
                    Secret Access Key: <b>%s</b>
                    <br/>
                    Instruction: <b>%s</b>
                </p>
                <p><b>Note:</b> Existing key pair <b>%s</b> will be deleted after
                    <b>%s</b> days so please update the key pair wherever required.</p>
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
            access_key,
            secret_key,
            instruction,
            existing_access_key,
            existing_key_delete_age,
        )

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


def mark_key_for_destroy(user_name, ak, existing_key_delete_age, email):
    """
    Add key in DynamoDB to delete it after few days
    """
    try:
        today = date.today()
        dynamodb.put_item(
            TableName=IAM_KEY_ROTATOR_TABLE,
            Item={
                "user": {"S": user_name},
                "ak": {"S": ak},
                "email": {"S": email},
                "delete_on": {
                    "N": str(
                        round(
                            datetime(
                                today.year, today.month, today.day, tzinfo=pytz.utc
                            ).timestamp()
                        )
                        + (existing_key_delete_age * 24 * 60 * 60)
                    )
                },
                "delete_enc_key": {"S": "Y" if ENCRYPT_KEY_PAIR else "N"},
            },
        )
        logger.info("Key %s marked for deletion", ak)
    except (Exception, ClientError) as ce:
        logger.error("Failed to mark key %s for deletion. Reason: %s", ak, ce)


def create_user_key(user_name, user):
    """
    Generate new key pair for the IAM user if required
    """
    try:
        if len(user["keys"]) == 0:
            logger.info(
                "Skipping key creation for %s because no existing key found", user_name
            )
        elif len(user["keys"]) == 2:
            logger.warning(
                "Skipping key creation for %s because 2 keys already exist. Please delete anyone to create new key",
                user_name,
            )
        else:
            for k in user["keys"]:
                key_rotation_age = (
                    user["attributes"]["rotate_after_days"]
                    if "rotate_after_days" in user["attributes"]
                    else ROTATE_AFTER_DAYS
                )
                if k["ak_age_days"] <= int(key_rotation_age):
                    logger.info(
                        "Skipping key creation for %s because existing key is only %s day(s) old and the rotation is set for %s days",
                        user_name,
                        k["ak_age_days"],
                        key_rotation_age,
                    )
                else:
                    logger.info("Creating new access key for %s", user_name)
                    resp = iam.create_access_key(UserName=user_name)
                    logger.info("New key pair generated for user %s", user_name)

                    # Email keys to user
                    existing_key_delete_age = (
                        user["attributes"]["delete_after_days"]
                        if "delete_after_days" in user["attributes"]
                        else DELETE_AFTER_DAYS
                    )

                    if ENCRYPT_KEY_PAIR:
                        user_access_key, user_secret_access_key = encryption.encrypt(
                            user_name,
                            resp["AccessKey"]["AccessKeyId"],
                            resp["AccessKey"]["SecretAccessKey"],
                        )
                        user_instruction = (
                            "The above key pair is encrypted so you need to decrypt it using the encryption key stored in SSM parameter /ikr/secret/iam/%s before using the key pair. You can use the *decryption.py* file present in the *skildops/aws-iam-key-rotator* repo. %s",
                            user_name,
                            user["attributes"]["instruction"],
                        )
                    else:
                        user_access_key = resp["AccessKey"]["AccessKeyId"]
                        user_secret_access_key = resp["AccessKey"]["SecretAccessKey"]
                        user_instruction = user["attributes"]["instruction"]

                    send_email(
                        user["attributes"]["email"],
                        user_name,
                        user_access_key,
                        user_secret_access_key,
                        user_instruction,
                        user["keys"][0]["ak"],
                        int(existing_key_delete_age),
                    )

                    # Mark exisiting key to destory after X days
                    mark_key_for_destroy(
                        user_name,
                        user["keys"][0]["ak"],
                        int(existing_key_delete_age),
                        user["attributes"]["email"],
                    )
    except (Exception, ClientError) as ce:
        logger.error("Failed to create new key pair. Reason: %s", ce)


def create_user_keys(users):
    """
    Call create_user_key in parallel using threads
    """
    with concurrent.futures.ThreadPoolExecutor(10) as executor:
        [executor.submit(create_user_key, user, users[user]) for user in users]


def handler(event, context):
    """
    Entrypoint function for lambda
    """
    global ENCRYPT_KEY_PAIR
    ENCRYPT_KEY_PAIR = False if ENCRYPT_KEY_PAIR == "false" else True

    if IAM_KEY_ROTATOR_TABLE is None:
        logger.error(
            "IAM_KEY_ROTATOR_TABLE is required. Current value: %s",
            IAM_KEY_ROTATOR_TABLE,
        )
    elif MAIL_FROM is None:
        logger.error("MAIL_FROM is required. Current value: %s", MAIL_FROM)
    else:
        users = fetch_user_details()
        create_user_keys(users)
