import uuid
from datetime import datetime, timezone

import httpx
import pytest


def _vec(first: float, second: float) -> str:
    vals = [0.0] * 768
    vals[0] = first
    vals[1] = second
    return "[" + ",".join(f"{v:.6f}" for v in vals) + "]"


@pytest.mark.asyncio
async def test_api_user_centroids_ranked_by_distance(api_url, db):
    org_id = f"org-centroids-test-{uuid.uuid4()}"
    model_version = "stub-768-v1"
    target_user = "user-a"
    user_b = "user-b"
    user_c = "user-c"
    user_d = "user-d"

    cluster_1 = uuid.uuid4()
    cluster_2 = uuid.uuid4()

    m1 = uuid.uuid4()
    m2 = uuid.uuid4()
    m3 = uuid.uuid4()
    m4 = uuid.uuid4()
    m5 = uuid.uuid4()

    now = datetime.now(timezone.utc)

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO clusters (org_id, cluster_id, model_version, centroid_embedding, effective_count, is_active)
            VALUES
              (%s, %s::uuid, %s, %s::vector, 3, TRUE),
              (%s, %s::uuid, %s, %s::vector, 2, TRUE)
            """,
            (org_id, str(cluster_1), model_version, _vec(1.0, 0.0), org_id, str(cluster_2), model_version, _vec(0.0, 1.0)),
        )

        cur.execute(
            """
            INSERT INTO messages (org_id, message_id, user_id, ts, source_type, text, metadata)
            VALUES
              (%s, %s::uuid, %s, %s, 'test', 'm1', '{}'::jsonb),
              (%s, %s::uuid, %s, %s, 'test', 'm2', '{}'::jsonb),
              (%s, %s::uuid, %s, %s, 'test', 'm3', '{}'::jsonb),
              (%s, %s::uuid, %s, %s, 'test', 'm4', '{}'::jsonb),
              (%s, %s::uuid, %s, %s, 'test', 'm5', '{}'::jsonb)
            """,
            (
                org_id,
                str(m1),
                target_user,
                now,
                org_id,
                str(m2),
                user_b,
                now,
                org_id,
                str(m3),
                user_c,
                now,
                org_id,
                str(m4),
                target_user,
                now,
                org_id,
                str(m5),
                user_d,
                now,
            ),
        )

        cur.execute(
            """
            INSERT INTO message_embeddings (org_id, message_id, model_version, embedding)
            VALUES
              (%s, %s::uuid, %s, %s::vector),
              (%s, %s::uuid, %s, %s::vector),
              (%s, %s::uuid, %s, %s::vector),
              (%s, %s::uuid, %s, %s::vector),
              (%s, %s::uuid, %s, %s::vector)
            """,
            (
                org_id,
                str(m1),
                model_version,
                _vec(1.0, 0.0),
                org_id,
                str(m2),
                model_version,
                _vec(0.8, 0.6),
                org_id,
                str(m3),
                model_version,
                _vec(0.0, 1.0),
                org_id,
                str(m4),
                model_version,
                _vec(0.0, 1.0),
                org_id,
                str(m5),
                model_version,
                _vec(0.6, 0.8),
            ),
        )

        cur.execute(
            """
            INSERT INTO message_cluster (org_id, message_id, cluster_id, confidence)
            VALUES
              (%s, %s::uuid, %s::uuid, 1.0),
              (%s, %s::uuid, %s::uuid, 1.0),
              (%s, %s::uuid, %s::uuid, 1.0),
              (%s, %s::uuid, %s::uuid, 1.0),
              (%s, %s::uuid, %s::uuid, 1.0)
            """,
            (
                org_id,
                str(m1),
                str(cluster_1),
                org_id,
                str(m2),
                str(cluster_1),
                org_id,
                str(m3),
                str(cluster_1),
                org_id,
                str(m4),
                str(cluster_2),
                org_id,
                str(m5),
                str(cluster_2),
            ),
        )

        cur.execute(
            """
            INSERT INTO user_cluster (org_id, user_id, cluster_id, participation_score, message_count)
            VALUES
              (%s, %s, %s::uuid, 1.0, 1),
              (%s, %s, %s::uuid, 1.0, 1),
              (%s, %s, %s::uuid, 1.0, 1),
              (%s, %s, %s::uuid, 1.0, 1),
              (%s, %s, %s::uuid, 1.0, 1)
            """,
            (
                org_id,
                target_user,
                str(cluster_1),
                org_id,
                user_b,
                str(cluster_1),
                org_id,
                user_c,
                str(cluster_1),
                org_id,
                target_user,
                str(cluster_2),
                org_id,
                user_d,
                str(cluster_2),
            ),
        )
        db.commit()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{api_url}/v1/orgs/{org_id}/users/{target_user}/connections")

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["org_id"] == org_id
    assert body["user_id"] == target_user
    assert len(body["centroids"]) == 2

    by_cluster = {item["cluster_id"]: item["users"] for item in body["centroids"]}

    c1_users = by_cluster[str(cluster_1)]
    assert [u["user_id"] for u in c1_users] == [target_user, user_b, user_c]
    assert c1_users[0]["distance"] == pytest.approx(0.0, abs=1e-6)
    assert c1_users[1]["distance"] == pytest.approx(0.2, abs=1e-3)
    assert c1_users[2]["distance"] == pytest.approx(1.0, abs=1e-6)

    c2_users = by_cluster[str(cluster_2)]
    assert [u["user_id"] for u in c2_users] == [target_user, user_d]
    assert c2_users[0]["distance"] == pytest.approx(0.0, abs=1e-6)
    assert c2_users[1]["distance"] == pytest.approx(0.2, abs=1e-3)
