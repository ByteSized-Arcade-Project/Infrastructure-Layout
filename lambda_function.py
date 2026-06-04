"""
ByteSized Arcade — AWS Lambda Function
========================================
Revised for $15 AWS credit budget.

Key changes from original:
  - RDS + pymysql removed entirely
  - Writes to DynamoDB (always free, no VPC NAT Gateway needed)
  - DynamoDB accessed via VPC Gateway Endpoint (free) from private subnet

Trigger:  SQS (BatchSize=10, FunctionResponseTypes=['ReportBatchItemFailures'])
Runtime:  Python 3.12
Memory:   128 MB (minimum — keeps GB-second costs near zero)

IAM Role permissions required:
  sqs:DeleteMessage, sqs:GetQueueAttributes   → score queue ARN
  dynamodb:PutItem                            → scores table ARN only
  logs:CreateLogGroup, logs:PutLogEvents      → /aws/lambda/ByteSizedValidator

VPC:   Same VPC as EC2 — Private subnet, no internet access needed.
       DynamoDB reached via VPC Gateway Endpoint (free, configured in VPC settings).
"""

import json
import time
import logging
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

log = logging.getLogger()
log.setLevel(logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────
AWS_REGION   = "us-east-1"
DYNAMO_TABLE = "arcade_scores"

# Game physics ceiling — used by the cheat validator
MAX_SCORE_PER_SECOND = 50    # max points possible per second at level 1
MAX_SESSION_SECONDS  = 3600  # 1 hour max session

# ── DynamoDB client (Lambda execution role — no hardcoded keys) ───────────────
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table    = dynamodb.Table(DYNAMO_TABLE)


# ── Validation ────────────────────────────────────────────────────────────────
def validate(msg: dict) -> tuple[bool, str]:
    """
    Deep physics-based validation. Runs only inside the private subnet —
    the client can never reach this directly.

    Returns (True, "ok") or (False, "reason string").
    """
    username  = msg.get("username", "").strip()
    score     = msg.get("score", 0)
    level     = msg.get("level", 1)
    timestamp = msg.get("timestamp", 0)

    if not username or len(username) > 12:
        return False, "Invalid username"

    if not isinstance(score, int) or score < 0:
        return False, "Non-integer or negative score"

    # Physics ceiling: even a perfect player cannot exceed this
    ceiling = MAX_SCORE_PER_SECOND * MAX_SESSION_SECONDS * int(level)
    if score > ceiling:
        return False, f"Score {score} exceeds physics ceiling {ceiling} at level {level}"

    # Timestamp freshness: reject stale or future submissions
    now = int(time.time())
    if abs(now - timestamp) > 7200:
        return False, f"Stale timestamp: {timestamp} vs now {now}"

    return True, "ok"


# ── DynamoDB write ────────────────────────────────────────────────────────────
def save_score(msg: dict):
    """
    Write a validated score to DynamoDB.
    Primary key: username (partition) + timestamp (sort).
    This lets one player have multiple entries; the leaderboard
    query on the EC2 side groups by username and keeps only the max score.
    """
    table.put_item(
        Item={
            "username":  msg["username"],
            "timestamp": msg["timestamp"],
            "score":     msg["score"],
            "level":     msg["level"],
        }
    )
    log.info("Saved: %s → %d pts (level %d)", msg["username"], msg["score"], msg["level"])


# ── Handler ───────────────────────────────────────────────────────────────────
def handler(event, context):
    """
    SQS event. Each record body is a JSON string from EC2's enqueue call.
    Returns batchItemFailures so SQS only retries transient errors,
    not validation rejections (which would loop forever).
    """
    failures = []

    for record in event.get("Records", []):
        msg_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            log.info("Processing msgId=%s user=%s score=%s",
                     msg_id, body.get("username"), body.get("score"))

            valid, reason = validate(body)
            if not valid:
                # Validation failure — log it and drop. Do NOT retry.
                log.warning("REJECTED msgId=%s | %s", msg_id, reason)
                continue

            save_score(body)

        except json.JSONDecodeError as exc:
            log.error("Bad JSON in msgId=%s: %s", msg_id, exc)
            # Malformed message — drop, don't retry

        except ClientError as exc:
            log.error("DynamoDB error for msgId=%s: %s", msg_id, exc)
            # Transient AWS error — return to SQS for retry
            failures.append({"itemIdentifier": msg_id})

        except Exception as exc:
            log.error("Unexpected error for msgId=%s: %s", msg_id, exc)
            failures.append({"itemIdentifier": msg_id})

    return {"batchItemFailures": failures}
