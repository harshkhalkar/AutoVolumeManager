import os
import logging
import boto3
import json
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.getenv("REGION")
TARGET = os.getenv("TARGET_VOLUME_TYPE", "gp3")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

ec2 = boto3.client("ec2", region_name=REGION) if REGION else boto3.client("ec2")

def lambda_handler(event, context):
    """
    Input: {'Volumes': [ {VolumeId, LoggedAt, ...}, ... ]}
    For each volume, call ec2.modify_volume to convert to TARGET
    Returns ModifyResults with VolumeId and response/error
    """
    volumes = event.get('Volumes', [])
    results = []
    for v in volumes:
        vol_id = v['VolumeId']
        try:
            if DRY_RUN:
                logger.info("DRY_RUN: would modify %s -> %s", vol_id, TARGET)
                resp = {'DryRun': True}
            else:
                raw_resp = ec2.modify_volume(VolumeId=vol_id, VolumeType=TARGET)
                logger.info("modify_volume response for %s: %s", vol_id, raw_resp)
                # Convert boto3 response to JSON-safe format
                resp = json.loads(json.dumps(raw_resp, default=str))
            results.append({
                'VolumeId': vol_id,
                'ModifyResponse': resp,
                'LoggedAt': v.get('LoggedAt')
            })
        except ClientError as e:
            logger.exception("Failed to modify %s: %s", vol_id, e)
            results.append({
                'VolumeId': vol_id,
                'Error': str(e),
                'LoggedAt': v.get('LoggedAt')
            })

    return {
        'ModifyResults': results,
        'Volumes': volumes
    }
