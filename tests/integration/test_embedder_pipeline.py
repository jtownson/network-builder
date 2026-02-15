import os
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from app.events import MessageEmbeddedEvent


@pytest.mark.asyncio
async def test_embedder_publishes_embedded_event(api_url, nats):
    expected_dim = int(os.getenv("TEST_EMBED_DIM", "768"))
    org_id = "org-embed-test"
    message_id = str(uuid.uuid4())

    # Listen for embedded events
    sub = await nats.subscribe(f"embeddings.{org_id}")
    try:
        payload = {
            "message_id": message_id,
            "user_id": "user-embed-test",
            "ts": datetime.now(timezone.utc).isoformat(),
            "text": "integration test message.embedded",
            "source_type": "test",
            "metadata": {},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{api_url}/v1/orgs/{org_id}/messages", json=payload)
            assert r.status_code == 202, r.text

            msg = await sub.next_msg(timeout=60.0)
            evt = MessageEmbeddedEvent.model_validate_json(msg.data)

            assert evt.event_type == "message.embedded"
            assert evt.org_id == org_id
            assert str(evt.message.message_id) == message_id
            assert evt.message.user_id == "user-embed-test"
            assert evt.message.text == "integration test message.embedded"
            assert evt.embedding_dim == expected_dim
            assert len(evt.embedding) == expected_dim
    finally:
        await sub.unsubscribe()
