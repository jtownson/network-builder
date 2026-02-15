import uuid
from datetime import datetime, timezone

import httpx
import pytest

from app.events import MessageClusteredEvent


@pytest.mark.asyncio
async def test_clusterer_publishes_event_and_writes_assignment(api_url, nats, db):
    org_id = "org-cluster-test"
    message_id = str(uuid.uuid4())
    user_id = "user-cluster-test"

    sub = await nats.subscribe(f"clusters.{org_id}")
    try:
        payload = {
            "message_id": message_id,
            "user_id": user_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "text": "integration test message.clustered",
            "source_type": "test",
            "metadata": {},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{api_url}/v1/orgs/{org_id}/messages", json=payload)
            assert r.status_code == 202, r.text

        clustered_msg = await sub.next_msg(timeout=15.0)
        evt = MessageClusteredEvent.model_validate_json(clustered_msg.data)

        assert evt.event_type == "message.clustered"
        assert evt.org_id == org_id
        assert str(evt.message_id) == message_id
        assert evt.user_id == user_id
        assert 0.0 <= evt.confidence <= 1.0

        with db.cursor() as cur:
            cur.execute(
                """
                SELECT cluster_id, confidence
                FROM message_cluster
                WHERE org_id = %s
                  AND message_id = %s::uuid
                """,
                (org_id, message_id),
            )
            row = cur.fetchone()

        print(f"Queried cluster row: {row}")
        assert row is not None
        assert str(row[0]) == str(evt.cluster_id)
        assert 0.0 <= float(row[1]) <= 1.0
    finally:
        await sub.unsubscribe()
