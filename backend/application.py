"""
ByteSized Arcade — Corrected EC2 Backend (Flask & DynamoDB)
===========================================================
This file fixes the previous database disconnect by natively reading 
the leaderboard directly from DynamoDB using the EC2 Instance IAM Role.
"""

import json
import time
import logging
from flask import Flask, request, jsonify, send_from_directory
import boto3
from collections import defaultdict

app = Flask(__name__, static_folder='static')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ── Unified Configuration ─────────────────────────────────────────────────────
AWS_REGION    = "us-east-1"
DYNAMO_TABLE  = "arcade_scores"
SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/YOUR_ACCOUNT_ID/ByteSizedScoreQueue"

# ── AWS Clients (Using EC2 IAM Instance Profile) ──────────────────────────────
sqs      = boto3.client("sqs",      region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table    = dynamodb.Table(DYNAMO_TABLE)

@app.route("/health")
def health():
    """ALB Health Check Target."""
    return jsonify({"status": "ok"}), 200

@app.route("/api/score", methods=["POST"])
def post_score():
    """Receives score, runs a minor guard check, and enqueues to SQS."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    username  = str(data.get("username", "")).strip()[:12]
    score     = data.get("score")
    level     = data.get("level", 1)
    timestamp = data.get("timestamp", int(time.time() * 1000))

    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not isinstance(score, int) or score < 0:
        return jsonify({"error": "Score must be a non-negative integer"}), 400
    if score > 99_999:
        return jsonify({"error": "Score out of range"}), 400

    message = {
        "username":  username,
        "score":     score,
        "level":     int(level),
        "timestamp": int(timestamp // 1000) # Lambda expects Unix epoch seconds
    }

    try:
        resp = sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message),
        )
        log.info("Queued score | user=%s score=%d msgId=%s", username, score, resp["MessageId"])
        return jsonify({"status": "queued", "messageId": resp["MessageId"]}), 202
    except Exception as exc:
        log.error("SQS send failed: %s", exc)
        return jsonify({"error": "Failed to queue score, try again"}), 500

@app.route("/api/leaderboard")
def get_leaderboard():
    """
    Reads directly from the DynamoDB table via VPC Gateway Endpoint.
    Groups entries by unique username, extracts their max score, and returns the top 10.
    """
    try:
        # Scan the table (Perfect for capstone scale)
        response = table.scan()
        items = response.get('Items', [])
        
        # Group unique users and track their highest score
        user_high_scores = defaultdict(lambda: {"score": -1, "level": 1})
        for item in items:
            user = item['username']
            score = int(item['score'])
            level = int(item.get('level', 1))
            
            if score > user_high_scores[user]["score"]:
                user_high_scores[user] = {"score": score, "level": level}
        
        # Format and sort for the UI response
        sorted_rows = [
            {"username": user, "score": stats["score"], "level": stats["level"]}
            for user, stats in user_high_scores.items()
        ]
        sorted_rows.sort(key=lambda x: x["score"], reverse=True)
        
        # Return top 10
        top_10 = sorted_rows[:10]
        return jsonify({"rows": top_10, "count": len(top_10)}), 200

    except Exception as exc:
        log.error("Leaderboard scan failed: %s", exc)
        return jsonify({"error": "Could not fetch leaderboard"}), 500

@app.route("/")
def index():
    return send_from_directory("static", "bytesized_arcade.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
