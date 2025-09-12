import os
import logging
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE = os.environ.get('DDB_TABLE')
REGION = os.getenv('REGION')
if not TABLE:
    raise RuntimeError("DDB_TABLE environment variable must be set")

dynamodb = boto3.resource('dynamodb', region_name=REGION) if REGION else boto3.resource('dynamodb')
table = dynamodb.Table(TABLE)

def lambda_handler(event, context):
    """
    Input: {'Volumes':[ ... ]}
    Writes a log row for each volume with ConversionStatus=PENDING and returns volumes with LoggedAt.
    """
    volumes = event.get('Volumes', [])
    out_volumes = []
    for v in volumes:
        vol_id = v['VolumeId']
        logged_at = datetime.now(timezone.utc).isoformat()
        item = {
            'VolumeId': vol_id,
            'LoggedAt': logged_at,
            'InstanceId': v.get('InstanceId'),
            'PrevVolumeType': v.get('VolumeType'),
            'Size': int(v.get('Size', 0)),
            'AvailabilityZone': v.get('AvailabilityZone'),
            'Region': REGION or boto3.session.Session().region_name,
            'Tags': v.get('Tags', {}),
            'ConversionStatus': 'PENDING'
        }
        try:
            table.put_item(Item=item)
            logger.info("Logged %s to DynamoDB at %s", vol_id, logged_at)
            v['LoggedAt'] = logged_at
            out_volumes.append(v)
        except ClientError as e:
            logger.exception("Failed to write log for %s: %s", vol_id, e)
            # still append volume so workflow can attempt modification if desired
            v['LoggedAt'] = logged_at
            v['LogError'] = str(e)
            out_volumes.append(v)

    return {'Volumes': out_volumes, 'LoggedCount': len(out_volumes)}
