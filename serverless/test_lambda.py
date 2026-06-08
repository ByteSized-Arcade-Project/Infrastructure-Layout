import json
import sys
sys.path.insert(0, '.')
from lambda_function import handler
import time

# Simulate what SQS sends to Lambda
def make_record(payload):
    return {"messageId": "test-001", "body": json.dumps(payload)}

fake_event = {
    "Records": [
        # Should PASS
        make_record({"username": "Alice", "score": 250, "level": 1, "timestamp": int(time.time())}),
        
        # Should REJECT — negative score
        make_record({"username": "Bob", "score": -5, "level": 1, "timestamp": 1700000000}),
        
        # Should REJECT — impossible score
        make_record({"username": "Hacker", "score": 99999999, "level": 1, "timestamp": 1700000000}),
        
        # Should REJECT — empty username
        make_record({"username": "", "score": 100, "level": 1, "timestamp": 1700000000}),
        
        # Should REJECT — stale timestamp
        make_record({"username": "OldPlayer", "score": 100, "level": 1, "timestamp": 1000}),
    ]
}

result = handler(fake_event, None)
print("\nBatch failures:", result)