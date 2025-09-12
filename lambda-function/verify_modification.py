import os
import logging
import boto3
import time
from datetime import datetime, timezone
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.getenv("REGION")
MAX_POLL = int(os.getenv("MAX_POLL_SECONDS", "300"))   # total seconds to wait
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))

ec2 = boto3.client("ec2", region_name=REGION) if REGION else boto3.client("ec2")
dynamodb = boto3.resource('dynamodb', region_name=REGION) if REGION else boto3.resource('dynamodb')
DDB_TABLE = os.environ.get('DDB_TABLE')
if not DDB_TABLE:
    raise RuntimeError("DDB_TABLE env var must be set")
table = dynamodb.Table(DDB_TABLE)

def check_mod_status(volume_id):
    try:
        resp = ec2.describe_volumes_modifications(VolumeIds=[volume_id])
        mods = resp.get('VolumesModifications', [])
        if not mods:
            return {'VolumeId': volume_id, 'ModificationState': None, 'StatusMessage': None}
        m = mods[0]
        return {
            'VolumeId': volume_id,
            'ModificationState': m.get('ModificationState'),
            'StatusMessage': m.get('StatusMessage'),
            'StartTime': m.get('StartTime').isoformat() if m.get('StartTime') else None,
            'Progress': m.get('Progress')
        }
    except ClientError as e:
        return {'VolumeId': volume_id, 'Error': str(e)}

def tag_volume(volume_id):
    try:
        ec2.create_tags(Resources=[volume_id], Tags=[
            {'Key': 'AutoConverted', 'Value': 'true'},
            {'Key': 'ConvertedBy', 'Value': 'IntelligentEBS'},
            {'Key': 'ConvertedAt', 'Value': datetime.now(timezone.utc).isoformat()}
        ])
        return True
    except ClientError as e:
        logger.exception("Failed to tag %s: %s", volume_id, e)
        return False

def update_ddb_status(volume_id, logged_at, success, status_message=None):
    try:
        update_expr = "SET ConversionStatus = :s, LastCheckedAt = :t"
        expr_vals = {':s': 'COMPLETED' if success else 'FAILED', ':t': datetime.now(timezone.utc).isoformat()}
        if status_message:
            update_expr += ", StatusMessage = :m"
            expr_vals[':m'] = status_message
        table.update_item(
            Key={'VolumeId': volume_id, 'LoggedAt': logged_at},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_vals
        )
        return True
    except ClientError as e:
        logger.exception("Failed to update DDB for %s: %s", volume_id, e)
        return False

def lambda_handler(event, context):
    """
    Input expects {'ModifyResults': [ {'VolumeId', ... , 'LoggedAt'}, ... ] }
    Polls modifications until success/failure or timeout.
    """
    modify_results = event.get('ModifyResults', [])
    pending = {r['VolumeId']: r.get('LoggedAt') for r in modify_results if 'VolumeId' in r}
    results = []
    start = time.time()
    deadline = start + MAX_POLL

    logger.info("Verifying %d volumes", len(pending))
    while pending and time.time() < deadline:
        for vol_id in list(pending.keys()):
            status = check_mod_status(vol_id)
            mod_state = (status.get('ModificationState') or '').lower() if status else ''
            logger.info("Volume %s status: %s", vol_id, mod_state)
            if mod_state in ('completed', 'optimizing'):
                # success
                tagged = tag_volume(vol_id)
                updated = update_ddb_status(vol_id, pending[vol_id], True, status.get('StatusMessage'))
                results.append({'VolumeId': vol_id, 'Success': True, 'State': status, 'Tagged': tagged})
                pending.pop(vol_id, None)
            elif mod_state in ('failed', 'failed-io', 'error'):
                updated = update_ddb_status(vol_id, pending[vol_id], False, status.get('StatusMessage'))
                results.append({'VolumeId': vol_id, 'Success': False, 'State': status})
                pending.pop(vol_id, None)
            # otherwise still pending
        if pending:
            time.sleep(POLL_INTERVAL)

    # timeout leftovers
    for vol_id, logged_at in pending.items():
        status = check_mod_status(vol_id)
        update_ddb_status(vol_id, logged_at, False, "Timed out waiting for modification")
        results.append({'VolumeId': vol_id, 'Success': False, 'TimedOut': True, 'State': status})

    return {'VerifyResults': results, 'CheckedAt': datetime.now(timezone.utc).isoformat()}
