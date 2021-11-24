import os
import json
import logging
import requests

logger = logging.getLogger('slack')
logger.setLevel(logging.INFO)

def notify(url, userName, existingAccessKey, accessKey=None, secretKey=None):
    if accessKey is not None:
        # New key pair generated
        logger.info('Sending notification to {} about new access key generation via {}'.format(userName, url))
        msg = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":mega: NEW KEY PAIR GENERATED FOR *{}* :mega:".format(userName)
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": "*Access Key:*\n{}".format(accessKey)
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*Secret Key:*\n{}".format(secretKey)
                        }
                    ]
                },
                {
                  "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*NOTE:* Existing key pair *{}* will be deleted after {} days so please update the new key pair wherever required".format(existingAccessKey, os.environ.get('DAYS_FOR_DELETION'))
                    }
                },
            ]
        }
    else:
        # Old key pair is deleted
        logger.info('Sending notification to {} about deletion of old access key via {}'.format(userName, url))
        msg = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":mega: OLD KEY PAIR DELETED :mega:".format(userName)
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": "*User:*\n{}".format(userName)
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*Old Access Key:*\n{}".format(accessKey)
                        }
                    ]
                }
            ]
        }

    resp = requests.post(url=url, json=msg)
    if resp.status_code == 200:
        logger.info('Notification sent to {} about key deletion via {}'.format(userName, url))
    else:
        logger.error('Notificaiton failed with {} status code. Reason: {}'.format(resp.status_code, resp.text))
