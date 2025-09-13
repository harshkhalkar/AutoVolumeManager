import os
import logging
import boto3
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.getenv("REGION")
# Get the volume types from an environment variable, comma-separated. Default to ['gp2'] if not set
VOLUME_TYPES = os.getenv("VOLUME_TYPES", "gp2").split(',')

# Clean any whitespace around volume types
VOLUME_TYPES = [vt.strip() for vt in VOLUME_TYPES if vt.strip()]

ec2 = boto3.client("ec2", region_name=REGION) if REGION else boto3.client("ec2")

def lambda_handler(event, context):
    """
    Scans for EBS volumes of specified types and tag AutoConvert=true.
    Returns: {'Volumes': [ {VolumeId, Size, VolumeType, AvailabilityZone, InstanceId, Tags}, ... ], 'ScannedCount': N}
    """
    logger.info(f"Starting filter_volumes scan for volume types: {VOLUME_TYPES}")
    
    filters = [{'Name': 'volume-type', 'Values': VOLUME_TYPES}]
    paginator = ec2.get_paginator('describe_volumes')
    page_iterator = paginator.paginate(Filters=filters)

    candidates = []
    scanned = 0
    for page in page_iterator:
        for v in page.get('Volumes', []):
            scanned += 1
            tags_list = v.get('Tags') or []
            tags = {t['Key']: t['Value'] for t in tags_list}
            if tags.get('AutoConvert', '').lower() == 'true':
                attachment = v.get('Attachments')[0] if v.get('Attachments') else {}
                instance_id = attachment.get('InstanceId')
                candidates.append({
                    'VolumeId': v['VolumeId'],
                    'Size': v['Size'],
                    'VolumeType': v['VolumeType'],
                    'AvailabilityZone': v['AvailabilityZone'],
                    'InstanceId': instance_id,
                    'Tags': tags
                })

    logger.info("Scanned %d volumes. Found %d candidates", scanned, len(candidates))
    return {
        'Volumes': candidates,
        'ScannedCount': scanned,
        'Timestamp': datetime.now(timezone.utc).isoformat()
    }
