from collections.abc import Generator

import psycopg

from app.core.config import NATS_URL, JETSTREAM_STREAM, JETSTREAM_SUBJECTS
from app.core.db import db_conninfo
from app.core.nats_client import NatsJetStreamPublisher

_publisher: NatsJetStreamPublisher | None = None


def get_publisher() -> NatsJetStreamPublisher:
    assert _publisher is not None, "Publisher not initialized"
    return _publisher


async def init_publisher() -> None:
    global _publisher
    _publisher = NatsJetStreamPublisher(
        nats_url=NATS_URL,
        stream_name=JETSTREAM_STREAM,
        subjects=JETSTREAM_SUBJECTS,
    )
    await _publisher.connect()


async def close_publisher() -> None:
    global _publisher
    if _publisher is not None:
        await _publisher.close()
        _publisher = None


def get_db_conn() -> Generator[psycopg.Connection, None, None]:
    with psycopg.connect(db_conninfo()) as conn:
        yield conn
