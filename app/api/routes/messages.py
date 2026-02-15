
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.events import MessageCreatedEvent, MessagePayload, to_json_bytes
from app.api.dependencies import get_publisher

router = APIRouter(prefix="/v1/orgs", tags=["messages"])


class IngestMessageRequest(BaseModel):
    message_id: Optional[UUID] = Field(default=None, description="Optional client-supplied id for idempotency.")
    user_id: str
    ts: datetime
    text: str
    source_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestMessageResponse(BaseModel):
    status: str = "accepted"
    event_id: UUID
    org_id: str
    message_id: UUID
    subject: str
    stream: str
    seq: int


@router.post("/{org_id}/messages", status_code=202, response_model=IngestMessageResponse)
async def ingest_message(
    org_id: str,
    body: IngestMessageRequest,
    pub=Depends(get_publisher),
) -> IngestMessageResponse:
    event_id = uuid4()
    message_id = body.message_id or uuid4()

    evt = MessageCreatedEvent(
        event_id=event_id,
        org_id=org_id,
        message=MessagePayload(
            message_id=message_id,
            user_id=body.user_id,
            ts=body.ts,
            source_type=body.source_type,
            text=body.text,
            metadata=body.metadata,
        ),
    )

    subject = f"messages.{org_id}"  # per your rename
    try:
        ack = await pub.publish(subject, to_json_bytes(evt))
        print(f"Published message.created event to {subject} with ack {ack}")
        
        return IngestMessageResponse(
            event_id=event_id,
            org_id=org_id,
            message_id=message_id,
            subject=subject,
            stream=getattr(ack, "stream", pub.stream_name),
            seq=int(getattr(ack, "seq", 0)),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"JetStream publish failed: {e}")

