from datetime import datetime
from typing import Any, Dict, List, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

MODEL_CFG = ConfigDict(extra="forbid", protected_namespaces=())


class MessagePayload(BaseModel):
    model_config = MODEL_CFG

    message_id: UUID
    user_id: str
    ts: datetime
    source_type: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageCreatedEvent(BaseModel):
    model_config = MODEL_CFG

    event_type: Literal["message.created"] = "message.created"
    event_version: int = 1
    event_id: UUID
    org_id: str
    message: MessagePayload


class MessageEmbeddedEvent(BaseModel):
    model_config = MODEL_CFG

    event_type: Literal["message.embedded"] = "message.embedded"
    event_version: int = 1
    event_id: UUID
    org_id: str
    message: MessagePayload
    model_version: str
    embedding_dim: int
    embedding: List[float]
    created_at: datetime


class MessageClusteredEvent(BaseModel):
    model_config = MODEL_CFG

    event_type: Literal["message.clustered"] = "message.clustered"
    event_version: int = 1
    event_id: UUID
    org_id: str

    message_id: UUID
    user_id: str
    ts: datetime

    model_version: str
    cluster_id: UUID
    confidence: float
    created_at: datetime
    
    
def to_json_bytes(model: BaseModel) -> bytes:
    return model.model_dump_json().encode("utf-8")


def parse_message_created(data: bytes) -> MessageCreatedEvent:
    return MessageCreatedEvent.model_validate_json(data)


def parse_message_embedded(data: bytes) -> MessageEmbeddedEvent:
    return MessageEmbeddedEvent.model_validate_json(data)


def parse_message_clustered(data: bytes) -> MessageClusteredEvent:
    return MessageClusteredEvent.model_validate_json(data)