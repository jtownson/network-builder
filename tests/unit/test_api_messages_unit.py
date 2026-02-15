from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api.routes.messages import IngestMessageRequest, ingest_message
from app.events import MessageCreatedEvent


class _Ack:
    def __init__(self, stream: str, seq: int):
        self.stream = stream
        self.seq = seq


class _FakePublisher:
    def __init__(self):
        self.stream_name = "ingress_messages"
        self.published = []

    async def publish(self, subject: str, payload: bytes):
        self.published.append((subject, payload))
        return _Ack(stream="ingress_messages", seq=123)


class _FailingPublisher:
    stream_name = "ingress_messages"

    async def publish(self, subject: str, payload: bytes):
        raise RuntimeError("publish failed")


@pytest.mark.asyncio
async def test_ingest_message_publishes_event_and_returns_ack_fields():
    fake = _FakePublisher()
    body = IngestMessageRequest(
        user_id="unit-user",
        ts=datetime.now(timezone.utc),
        text="unit test message",
        source_type="unit-test",
        metadata={"k": "v"},
    )
    resp = await ingest_message(org_id="org-unit", body=body, pub=fake)

    assert resp.status == "accepted"
    assert resp.org_id == "org-unit"
    assert resp.subject == "messages.org-unit"
    assert resp.stream == "ingress_messages"
    assert resp.seq == 123
    assert UUID(str(resp.event_id))
    assert UUID(str(resp.message_id))

    assert len(fake.published) == 1
    subject, raw_payload = fake.published[0]
    assert subject == "messages.org-unit"

    evt = MessageCreatedEvent.model_validate_json(raw_payload)
    assert evt.event_type == "message.created"
    assert evt.org_id == "org-unit"
    assert evt.message.user_id == "unit-user"
    assert evt.message.text == "unit test message"
    assert evt.message.source_type == "unit-test"
    assert evt.message.metadata == {"k": "v"}


@pytest.mark.asyncio
async def test_ingest_message_returns_503_when_publish_fails():
    body = IngestMessageRequest(
        user_id="unit-user",
        ts=datetime.now(timezone.utc),
        text="unit test message",
        source_type="unit-test",
        metadata={},
    )

    with pytest.raises(HTTPException) as exc:
        await ingest_message(org_id="org-unit", body=body, pub=_FailingPublisher())

    assert exc.value.status_code == 503
    assert "JetStream publish failed" in str(exc.value.detail)
