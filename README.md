# Intelligent EBS Auto Converter

## Overview

The Intelligent EBS Auto Converter is a serverless automation framework designed to streamline the management of Amazon EBS volumes across AWS environments. It allows teams to define rule-based workflows—such as volume type conversions, tagging policies, or compliance actions—and execute them automatically on a scheduled basis.

This solution is tag-driven, fully auditable, and integrates tightly with AWS-native services.

---

## Key Features

- **Automated Volume Management**: Automatically identify and process EBS volumes based on defined tags or conditions.
- **Flexible Architecture**: Built with modular AWS Lambda functions and AWS Step Functions for easy extension or customization.
- **Audit Logging**: All actions are logged in DynamoDB for traceability.
- **Notifications**: Summary reports are sent via Amazon SNS to stakeholders.
- **Safe Execution**: Optional dry-run mode, timeouts, and status verification reduce operational risk.
- **Tag-Based Control**: Only volumes with specific tags (e.g., `AutoConvert=true`) are included in processing.

---

## Architecture Diagram

![Architecture Overview](./architecture-overview/AutoVolumeManager.png)

---

## AWS Services Used

| Service        | Role in Framework                             |
|----------------|-----------------------------------------------|
| **Lambda**     | Executes logic: filter, modify, log, notify   |
| **Step Functions** | Orchestrates the multi-step process     |
| **DynamoDB**   | Stores logs and state of each volume operation |
| **SNS**        | Sends summary notifications via email         |
| **EventBridge**| Triggers the workflow on a schedule    |
| **IAM**        | Manages secure access across services         |

---

## IAM Roles & Permissions

### Lambda Execution Role

Allows Lambda functions to:
- Describe, modify, and tag EBS volumes
- Log to DynamoDB
- Publish messages to SNS
- Write logs to CloudWatch

### Step Functions Role

Allows Step Functions to:
- Invoke all Lambda functions involved in the workflow

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeLambdas",
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction",
        "lambda:InvokeAsync"
      ],
      "Resource": "<paste-arn-here>"
    }
  ]
}
```

### EventBridge Role

Allows EventBridge to:
- Start Step Functions state machine execution on a scheduled basis

```json
{
  "Version":"2012-10-17",
  "Statement":[
    {
      "Effect":"Allow",
      "Action":"states:StartExecution",
      "Resource":"<paste-arn-here>"
    }
  ]
}
```

---

## DynamoDB: `EBSVolumeConversionLog`

| Field           | Description                                 |
|------------------|---------------------------------------------|
| VolumeId         | EBS volume identifier                       |
| LoggedAt         | Timestamp when action was logged            |
| ConversionStatus | PENDING / COMPLETED / FAILED                |
| Tags             | Volume tags at time of processing           |
| Region           | AWS region of the volume                    |
| StatusMessage    | Message related to the result or failure    |

---

## Workflow

1. **Filter Volumes**  
   Lambda function scans all EBS volumes, filtering by volume type, tags.

2. **Log to DynamoDB**  
   Each selected volume is logged with metadata and marked for processing.

3. **Modify Volume (Action)**  
   Apply changes — such as converting volume type.

4. **Verify Result**  
   Poll the status and verify the outcome of the modification.

5. **Send Notification**  
   Summarize all results and notify sub's via SNS email.

---

## Environment Configuration

Each Lambda function supports environment variables to customize behavior:

- `DDB_TABLE` = Name of DynamoDB table
- `VOLUME_TYPES` = Volume type (filter volume)
- `SNS_TOPIC_ARN` = ARN of the SNS topic
- `TARGET_VOLUME_TYPE` = Target type (optional/customizable)
- `REGION` = AWS region override (optional)
- `DRY_RUN` = `true`/`false` for simulation mode

---

## Testing & Observability

- Manually trigger Step Functions execution to validate logic
- Monitor CloudWatch logs per Lambda for troubleshooting
- Use DynamoDB logs for traceability and audit

---

# Real-World Challenges Simulated & How They're Handled

---

## 1. Identifying Eligible EBS Volumes

### Challenge:

In large AWS environments, you might have hundreds or thousands of EBS volumes across multiple regions and accounts. How do you reliably and automatically find only those that qualify for conversion (e.g., gp2 → gp3)?

### Solution:

- `filter_volumes` Lambda filters by `volume-type=gp2` (volume-type according to need) and `tag:AutoConvert=true`.
- Uses paginated `describe_volumes` to scale across hundreds/thousands of volumes.

---

## 2. Audit Logging for Compliance

### Challenge:

Changes to cloud resources need to be traceable for compliance, rollback, or audit reviews.

### Solution:

- `log_to_dynamo` Lambda logs each volume change attempt to DynamoDB.
- Stores metadata like volume type, instance ID, timestamp, and conversion status.

---

## 3. Handling Failures & Timeouts

### Challenge:

EBS conversions can fail, be delayed, or stuck in “optimizing”.

### Solution:

- `verify_modification` Lambda polls status up to 5 minutes.
- Logs `COMPLETED`, `FAILED`, or `TIMED OUT` in DynamoDB.
- Adds tags on success, like `AutoConverted=true`.

---

## 4. Automated Notifications

### Challenge:

Teams don’t want to manually check logs or dashboards.

### Solution:

- `notify_sns` sends a detailed summary email after each run.
- Includes volume IDs, statuses, errors, and notes if no volumes needed action.

---

## 5. Scalability & Scheduling

### Challenge:

Manual scripts don’t scale well or run reliably on a schedule.

### Solution:

- Uses EventBridge to schedule daily runs.
- Step Functions orchestrate the workflow.
- Fully serverless: Lambdas scale automatically, no EC2 needed.

---

## 6. Safe Testing with Dry Run Mode

### Challenge:

How to safely test in production-like conditions?

### Solution:

- `modify_volume` supports `DRY_RUN=true` to simulate changes.
- No real modifications happen; useful for test/staging.

---

## 7. IAM & Least Privilege

### Challenge:

Over-permissioned roles are a security risk.

### Solution:

- IAM roles have tightly scoped actions (e.g., only `ModifyVolume`, `Publish`, `PutItem`).

---

## 8. Error Visibility & Debugging

### Challenge:

Hard to debug silent failures.

### Solution:

- All Lambdas log to CloudWatch Logs.
- Step Functions provide a visual workflow to pinpoint failure steps.

---

## 9. Avoiding Accidental Modifications

### Challenge:

Accidental conversion of critical volumes can be disruptive.

### Solution:

- Uses opt-in tagging (`AutoConvert=true`) to prevent unintended changes.
- Ensures only explicitly marked volumes are affected.

---
