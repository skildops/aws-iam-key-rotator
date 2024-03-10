"""
Encrypt key pair shared with user
"""

import logging
import sys
import os
import boto3

from cryptography.fernet import Fernet
from botocore.exceptions import ClientError

ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION"))

logger = logging.getLogger("encryption")
logger.setLevel(logging.INFO)


def store_in_ssm(user_name, encryption_key):
    """
    Store encryption key in SSM
    """
    try:
        logger.info(
            "Creating SSM parameter to store encryption key for %s user", user_name
        )
        ssm.put_parameter(
            Name=f"/ikr/secret/iam/{user_name}",
            Description=f"Encryption key used to encrypt access key pair of {user_name} user",
            Value=encryption_key,
            Type="SecureString",
            Overwrite=True,
        )
        logger.info("SSM parameter created for %s user", user_name)
    except ClientError as ce:
        logger.error(
            "Failed to create SSM parameter to store encryption key for %s user. Reason: %s",
            user_name,
            ce,
        )
        return False

    return True


def encrypt(user_name, access_key, secret_access_key):
    """
    Encrypt access key pair
    """
    encryption_key = Fernet.generate_key().decode("utf-8")

    if not store_in_ssm(user_name, encryption_key):
        sys.exit(1)

    f = Fernet(encryption_key)
    encrypted_access_key = f.encrypt(access_key.encode("utf-8")).decode("utf-8")
    encrypted_secret_access_key = f.encrypt(secret_access_key.encode("utf-8")).decode(
        "utf-8"
    )

    return encrypted_access_key, encrypted_secret_access_key
