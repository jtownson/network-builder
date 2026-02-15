#!/bin/bash

curl -s -X POST "http://localhost:8000/v1/orgs/org-1/messages" \
  -H "Content-Type: application/json" \
  -d "{
    \"message_id\": \"$(uuidgen)\",
    \"user_id\": \"user-99\",
    \"ts\": \"2026-01-29T10:00:00Z\",
    \"text\": \"Hello from the API — test message with explicit message_id\",
    \"source_type\": \"api_demo\",
    \"metadata\": {
      \"via\": \"curl\",
      \"purpose\": \"api smoke test\"
    }
  }"
