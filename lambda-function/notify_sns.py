import os
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SNS_TOPIC = os.environ.get('SNS_TOPIC_ARN')
REGION = os.getenv('REGION')
if not SNS_TOPIC:
    raise RuntimeError("SNS_TOPIC_ARN must be set")

sns = boto3.client('sns', region_name=REGION) if REGION else boto3.client('sns')

def make_message(verify_results):
    if not verify_results:
        return "No conversions required during this run."
    lines = []
    for r in verify_results:
        vid = r.get('VolumeId')
        succ = r.get('Success', False)
        state = r.get('State', {})
        msg = f"Volume: {vid} | Success: {succ} | State: {state.get('ModificationState') or state.get('StatusMessage')}"
        if r.get('TimedOut'):
            msg += " | TIMED OUT"
        lines.append(msg)
    return "EBS Volume Conversion Report\n\n" + "\n".join(lines)

def lambda_handler(event, context):
    verify_results = event.get('VerifyResults') or event.get('VerifyResults', [])
    message = make_message(verify_results)
    subject = "EBS Volume Conversion Report"
    try:
        resp = sns.publish(TopicArn=SNS_TOPIC, Subject=subject, Message=message)
        logger.info("SNS published MessageId=%s", resp.get('MessageId'))
        return {'Published': True, 'MessageId': resp.get('MessageId')}
    except Exception as e:
        logger.exception("SNS publish failed: %s", e)
        return {'Published': False, 'Error': str(e)}
