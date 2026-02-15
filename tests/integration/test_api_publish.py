import json
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from app.events import MessageCreatedEvent

@pytest.mark.asyncio
async def test_api_publishes_message_created(api_url, nats):
    org_id = "org-test"
    user_id = "user-test"
    message_id = str(uuid.uuid4())

    # Subscribe first to avoid races
    sub = await nats.subscribe(f"messages.{org_id}")
    try:
        payload = {
            "message_id": message_id,
            "user_id": user_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "text": "integration test message.created",
            "source_type": "test",
            "metadata": {"k": "v"},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{api_url}/v1/orgs/{org_id}/messages", json=payload)
            assert r.status_code == 202, r.text
            body = r.json()
            assert body["org_id"] == org_id
            assert body["message_id"] == message_id

            msg = await sub.next_msg(timeout=5.0)
            evt = MessageCreatedEvent.model_validate_json(msg.data)

            assert evt.event_type == "message.created"
            assert evt.org_id == org_id
            assert str(evt.message.message_id) == message_id
            assert evt.message.user_id == user_id
    finally:
        await sub.unsubscribe()
