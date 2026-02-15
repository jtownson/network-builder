import asyncio
import hashlib
import os
import random
from datetime import datetime, timezone
from re import sub
from typing import List
from uuid import UUID, uuid4

import psycopg
from dotenv import load_dotenv
from nats import errors as nats_errors
from nats.aio.client import Client
from nats.js.client import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy, AckPolicy

from app.events import (
    MessageCreatedEvent,
    MessageEmbeddedEvent,
    parse_message_created,
    to_json_bytes,
)

load_dotenv()

# JetStream / NATS
STREAM_NAME = os.getenv("JETSTREAM_STREAM", "ingress_messages")
CONSUME_DURABLE = os.getenv("EMBEDDER_DURABLE", "embedder_v1")
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
DELIVER_SUBJECT_ENV = os.getenv("EMBEDDER_DELIVER_SUBJECT", "").strip()

# Embedding config
MODEL_VERSION = os.getenv("EMBED_MODEL_VERSION", "stub-768-v1")
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))

# Publish embedded events to embeddings.{org_id}
PUBLISH_SUBJECT_PREFIX = os.getenv("EMBEDDED_SUBJECT_PREFIX", "embeddings")

# Persist embeddings into Postgres as well
PERSIST_TO_DB = os.getenv("EMBED_PERSIST_TO_DB", "false").lower() in (
    "1",
    "true",
    "yes",
)


def db_conninfo() -> str:
    host = os.getenv("DB_HOST", "postgres")
    port = int(os.getenv("DB_PORT", "5432"))
    name = os.getenv("DB_NAME", "network_builder_db")
    user = os.getenv("DB_USER", "network_builder_client")
    pw = os.getenv("DB_PASSWORD", "network_builder_secret")
    return f"host={host} port={port} dbname={name} user={user} password={pw}"


def stable_seed(*parts: str) -> int:
    h = hashlib.sha256("::".join(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False)


def stub_embedding(text: str, org_id: str, message_id: str, dim: int) -> List[float]:
    seed = stable_seed(org_id, message_id, text[:128])
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dim)]


def to_pgvector_literal(vec: List[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def upsert_embedding(
    cur: psycopg.Cursor, org_id: str, message_id: UUID, embedding: List[float]
) -> bool:
    vec_lit = to_pgvector_literal(embedding)
    cur.execute(
        """
        INSERT INTO message_embeddings (org_id, message_id, model_version, embedding)
        VALUES (%s, %s::uuid, %s, %s::vector)
        ON CONFLICT (org_id, message_id, model_version) DO NOTHING
        RETURNING 1
        """,
        (org_id, str(message_id), MODEL_VERSION, vec_lit),
    )
    return cur.fetchone() is not None


async def msg_callback(js: JetStreamContext, msg):
    created: MessageCreatedEvent = parse_message_created(msg.data)

    org_id = created.org_id
    msg_payload = created.message
    message_id = msg_payload.message_id

    emb = stub_embedding(
        text=msg_payload.text,
        org_id=org_id,
        message_id=str(message_id),
        dim=EMBED_DIM,
    )

    embedded_evt = MessageEmbeddedEvent(
        event_id=uuid4(),
        org_id=org_id,
        message=msg_payload,  # <-- includes text + metadata + user_id + ts
        model_version=MODEL_VERSION,
        embedding_dim=EMBED_DIM,
        embedding=emb,
        created_at=datetime.now(timezone.utc),
    )

    publish_subject = f"{PUBLISH_SUBJECT_PREFIX}.{org_id}"
    await js.publish(publish_subject, to_json_bytes(embedded_evt))

    print(f"✅ embedded message_id={message_id} org={org_id} -> {publish_subject}")
    await msg.ack()


async def main() -> None:
    print("⏳ Starting embedder consumer...")

    nats_client: Client = Client()
    await nats_client.connect(servers=[NATS_URL])

    js: JetStreamContext = nats_client.jetstream()

    print("✅ Connected to NATS/JetStream")

    deliver_subject = DELIVER_SUBJECT_ENV or nats_client.new_inbox()

    consumer_config = ConsumerConfig(
        "embedder_consumer",
        durable_name=CONSUME_DURABLE,
        description="Embedder consumer",
        deliver_policy=DeliverPolicy.ALL,
        deliver_subject=deliver_subject,
        ack_policy=AckPolicy.EXPLICIT,
        ack_wait=30_000_000_000,
        max_deliver=5,
    )

    await js.subscribe(
        subject="messages.>",
        cb=lambda m: msg_callback(js, m),
        durable=CONSUME_DURABLE,
        stream=STREAM_NAME,
        config=consumer_config,
    )

    print(
        f"✅ Embedder running (consume=messages.>, publish={PUBLISH_SUBJECT_PREFIX}.<org>, "
        f"stream={STREAM_NAME}, durable={CONSUME_DURABLE}, model={MODEL_VERSION})"
    )

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
