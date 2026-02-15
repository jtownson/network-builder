import asyncio
import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

import psycopg
from dotenv import load_dotenv
from nats import errors as nats_errors
from nats.aio.client import Client as NATS

from app.events import (
    MessageEmbeddedEvent,
    MessageClusteredEvent,
    parse_message_embedded,
    to_json_bytes,
)

load_dotenv()

# -------------------------
# NATS / JetStream
# -------------------------
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
STREAM_NAME = os.getenv("JETSTREAM_STREAM", "ingress_messages")
CONSUME_DURABLE = os.getenv("CLUSTERER_DURABLE", "clusterer_v1")

CONSUME_SUBJECT = os.getenv("CLUSTERER_CONSUME_SUBJECT", "embeddings.>")
PUBLISH_PREFIX = os.getenv("CLUSTERED_SUBJECT_PREFIX", "clusters")  # clusters.{org_id}

# -------------------------
# Clustering parameters
# -------------------------
# We use cosine distance in pgvector: distance = 1 - cosine_similarity
ASSIGN_SIM_THRESHOLD = float(os.getenv("CLUSTER_ASSIGN_SIM_THRESHOLD", "0.78"))
ASSIGN_DIST_THRESHOLD = 1.0 - ASSIGN_SIM_THRESHOLD

# centroid update: capped mean
COUNT_CAP = int(os.getenv("CLUSTER_COUNT_CAP", "1000"))


def db_conninfo() -> str:
    host = os.getenv("DB_HOST", "postgres")
    port = int(os.getenv("DB_PORT", "5432"))
    name = os.getenv("DB_NAME", "network_builder_db")
    user = os.getenv("DB_USER", "network_builder_client")
    pw = os.getenv("DB_PASSWORD", "network_builder_secret")
    return f"host={host} port={port} dbname={name} user={user} password={pw}"


def l2_normalize(vec: List[float]) -> List[float]:
    # defensive normalization
    s = 0.0
    for x in vec:
        s += x * x
    if s <= 0.0:
        return vec
    norm = s ** 0.5
    return [x / norm for x in vec]


def to_pgvector_literal(vec: List[float]) -> str:
    # pgvector accepts: '[0.1,0.2,...]'
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def cosine_similarity_from_distance(d: float) -> float:
    # for normalized vectors: cosine_distance = 1 - cosine_similarity
    return max(-1.0, min(1.0, 1.0 - d))


def updated_centroid(old: List[float], new: List[float], effective_count: int, cap: int) -> List[float]:
    """
    Capped-mean update:
      n_eff = min(effective_count, cap)
      c' = normalize((c*n_eff + x)/(n_eff+1))
    """
    n_eff = min(int(effective_count), int(cap))
    out = []
    for i in range(len(old)):
        out.append((old[i] * n_eff + new[i]) / (n_eff + 1.0))
    return l2_normalize(out)


def parse_vector_text(vec_txt: str) -> List[float]:
    # centroid_embedding::text returns '[0.1,0.2,...]'
    body = vec_txt.strip()
    if body.startswith("[") and body.endswith("]"):
        body = body[1:-1]
    if not body:
        return []
    return [float(x) for x in body.split(",")]


def fetch_best_cluster(
    cur: psycopg.Cursor,
    org_id: str,
    model_version: str,
    embedding: List[float],
) -> Optional[Tuple[UUID, float, List[float], int]]:
    """
    Returns best candidate: (cluster_id, cosine_distance, centroid_vector, effective_count)
    or None if there are no active clusters.
    """
    vec_lit = to_pgvector_literal(embedding)

    # `<=>` is cosine distance for pgvector
    cur.execute(
        """
        SELECT cluster_id,
               (centroid_embedding <=> %s::vector) AS dist,
               centroid_embedding::text,
               effective_count
        FROM clusters
        WHERE org_id = %s
          AND model_version = %s
          AND is_active = TRUE
        ORDER BY centroid_embedding <=> %s::vector
        LIMIT 1
        """,
        (vec_lit, org_id, model_version, vec_lit),
    )
    rows = cur.fetchall()
    if not rows:
        return None

    cluster_id, dist, centroid_txt, eff = rows[0]
    return (UUID(str(cluster_id)), float(dist), parse_vector_text(centroid_txt), int(eff))


def create_cluster(
    cur: psycopg.Cursor,
    org_id: str,
    model_version: str,
    embedding: List[float],
) -> UUID:
    vec_lit = to_pgvector_literal(embedding)
    cur.execute(
        """
        INSERT INTO clusters (
          org_id, model_version, centroid_embedding, label,
          effective_count, last_activity_at, is_active,
          created_at, updated_at
        )
        VALUES (
          %s, %s, %s::vector, NULL,
          1, now(), TRUE,
          now(), now()
        )
        RETURNING cluster_id
        """,
        (org_id, model_version, vec_lit),
    )
    return UUID(str(cur.fetchone()[0]))


def update_cluster(
    cur: psycopg.Cursor,
    org_id: str,
    cluster_id: UUID,
    new_centroid: List[float],
    new_effective_count: int,
) -> None:
    vec_lit = to_pgvector_literal(new_centroid)
    cur.execute(
        """
        UPDATE clusters
        SET centroid_embedding = %s::vector,
            effective_count = %s,
            last_activity_at = now(),
            updated_at = now()
        WHERE org_id = %s AND cluster_id = %s::uuid
        """,
        (vec_lit, int(new_effective_count), org_id, str(cluster_id)),
    )


def upsert_message_cluster(
    cur: psycopg.Cursor,
    org_id: str,
    message_id: UUID,
    cluster_id: UUID,
    confidence: float,
) -> None:
    cur.execute(
        """
        INSERT INTO message_cluster (org_id, message_id, cluster_id, confidence)
        VALUES (%s, %s::uuid, %s::uuid, %s)
        ON CONFLICT (org_id, message_id, cluster_id) DO NOTHING
        """,
        (org_id, str(message_id), str(cluster_id), float(confidence)),
    )


def upsert_user_cluster(
    cur: psycopg.Cursor,
    org_id: str,
    user_id: str,
    cluster_id: UUID,
    confidence: float,
) -> None:
    cur.execute(
        """
        INSERT INTO user_cluster (
          org_id, user_id, cluster_id,
          participation_score, message_count,
          last_activity_at, updated_at
        )
        VALUES (%s, %s, %s::uuid, %s, 1, now(), now())
        ON CONFLICT (org_id, user_id, cluster_id)
        DO UPDATE SET
          participation_score = user_cluster.participation_score + EXCLUDED.participation_score,
          message_count = user_cluster.message_count + 1,
          last_activity_at = now(),
          updated_at = now()
        """,
        (org_id, user_id, str(cluster_id), float(confidence)),
    )


def get_existing_message_assignment(
    cur: psycopg.Cursor,
    org_id: str,
    message_id: UUID,
) -> Optional[Tuple[UUID, float]]:
    cur.execute(
        """
        SELECT cluster_id, confidence
        FROM message_cluster
        WHERE org_id = %s
          AND message_id = %s::uuid
        ORDER BY assigned_at DESC
        LIMIT 1
        """,
        (org_id, str(message_id)),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return UUID(str(row[0])), float(row[1])


async def main() -> None:
    # Connect to NATS
    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    js = nc.jetstream()

    # Consume message.embedded events
    sub = await js.pull_subscribe(CONSUME_SUBJECT, durable=CONSUME_DURABLE, stream=STREAM_NAME)
    print(
        f"✅ Clusterer running (consume={CONSUME_SUBJECT}, publish={PUBLISH_PREFIX}.<org>, "
        f"stream={STREAM_NAME}, durable={CONSUME_DURABLE}, assign_sim>={ASSIGN_SIM_THRESHOLD})"
    )

    conn = psycopg.connect(db_conninfo())
    conn.autocommit = False

    try:
        while True:
            try:
                msgs = await sub.fetch(batch=25, timeout=1.0)
            except nats_errors.TimeoutError:
                await asyncio.sleep(0.2)
                continue

            for m in msgs:
                try:
                    embedded: MessageEmbeddedEvent = parse_message_embedded(m.data)

                    org_id = embedded.org_id
                    model_version = embedded.model_version

                    msg_payload = embedded.message
                    message_id = msg_payload.message_id
                    user_id = msg_payload.user_id
                    ts = msg_payload.ts

                    embedding = l2_normalize(list(embedded.embedding))

                    with conn.cursor() as cur:
                        existing = get_existing_message_assignment(cur, org_id, message_id)
                        if existing is not None:
                            cluster_id, confidence = existing
                        else:
                            best = fetch_best_cluster(cur, org_id, model_version, embedding)

                            if best is None:
                                cluster_id = create_cluster(cur, org_id, model_version, embedding)
                                confidence = 1.0
                            else:
                                best_cluster_id, best_dist, centroid_vec, eff_count = best

                                if best_dist <= ASSIGN_DIST_THRESHOLD:
                                    cluster_id = best_cluster_id
                                    confidence = cosine_similarity_from_distance(best_dist)

                                    new_cent = updated_centroid(centroid_vec, embedding, eff_count, COUNT_CAP)
                                    update_cluster(cur, org_id, cluster_id, new_cent, eff_count + 1)
                                else:
                                    cluster_id = create_cluster(cur, org_id, model_version, embedding)
                                    confidence = 1.0

                            upsert_message_cluster(cur, org_id, message_id, cluster_id, confidence)
                            upsert_user_cluster(cur, org_id, user_id, cluster_id, confidence)

                        conn.commit()

                    # Publish message.clustered event
                    clustered_evt = MessageClusteredEvent(
                        event_id=uuid4(),
                        org_id=org_id,
                        message_id=message_id,
                        user_id=user_id,
                        ts=ts,
                        model_version=model_version,
                        cluster_id=cluster_id,
                        confidence=float(confidence),
                        created_at=datetime.now(timezone.utc),
                    )

                    publish_subject = f"{PUBLISH_PREFIX}.{org_id}"
                    await js.publish(publish_subject, to_json_bytes(clustered_evt))

                    await m.ack()
                    print(
                        f"🧩 clustered message_id={message_id} org={org_id} user={user_id} "
                        f"-> cluster={cluster_id} conf={confidence:.3f}"
                    )

                except Exception as e:
                    if conn is not None:
                        conn.rollback()
                    # Don't ack; message will redeliver
                    print(f"❌ clusterer failed: {e}")

    finally:
        if conn is not None:
            conn.close()
        await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
