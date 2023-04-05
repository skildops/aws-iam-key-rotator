import boto3
import logging
import sys
import os

from cryptography.fernet import Fernet
from botocore.exceptions import ClientError

ssm = boto3.client('ssm', region_name=os.environ.get('AWS_REGION'))

logger = logging.getLogger('encryption')
logger.setLevel(logging.INFO)

def store_in_ssm(userName, encryptionKey):
    try:
        logger.info('Creating SSM parameter to store encryption key for {} user'.format(userName))
        ssm.put_parameter(
            Name='/ikr/secret/iam/{}'.format(userName),
            Description='Encryption key used to encrypt access key pair of {} user'.format(userName),
            Value=encryptionKey,
            Type='SecureString',
            Overwrite=True
        )
        logger.info('SSM parameter created for {} user'.format(userName))
    except ClientError as ce:
        logger.error('Failed to create SSM parameter to store encryption key for {} user. Reason: {}'.format(userName, ce))
        return False

    return True

def encrypt(userName, accessKey, secretAccessKey):
    encryptionKey = Fernet.generate_key().decode('utf-8')

    if not store_in_ssm(userName, encryptionKey):
        sys.exit(1)

    f = Fernet(encryptionKey)
    encryptedAccessKey = f.encrypt(accessKey.encode('utf-8')).decode('utf-8')
    encryptedSecretAccessKey = f.encrypt(secretAccessKey.encode('utf-8')).decode('utf-8')

    return encryptedAccessKey, encryptedSecretAccessKey
