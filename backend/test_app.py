from unittest.mock import patch, MagicMock
import json
import sys
sys.path.insert(0, '.')

# Mock boto3 before importing app so it doesn't try to connect to AWS
with patch('boto3.client') as mock_sqs, patch('boto3.resource') as mock_dynamo:
    mock_sqs_client = MagicMock()
    mock_sqs.return_value = mock_sqs_client
    mock_sqs_client.send_message.return_value = {"MessageId": "mock-id-123"}
    
    from application import app
    app.config['TESTING'] = True
    client = app.test_client()

    # Test 1 — valid score
    res = client.post('/api/score',
        data=json.dumps({"username": "Alice", "score": 250, "level": 1, "timestamp": 1700000000000}),
        content_type='application/json'
    )
    print("Valid score:", res.status_code, res.get_json())

    # Test 2 — missing username
    res = client.post('/api/score',
        data=json.dumps({"username": "", "score": 250, "level": 1}),
        content_type='application/json'
    )
    print("Missing username:", res.status_code, res.get_json())

    # Test 3 — score out of range
    res = client.post('/api/score',
        data=json.dumps({"username": "Hacker", "score": 999999, "level": 1}),
        content_type='application/json'
    )
    print("Out of range:", res.status_code, res.get_json())

    # Test 4 — health check
    res = client.get('/health')
    print("Health check:", res.status_code, res.get_json())