import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest


SCENARIO_PATH = (
    Path(__file__).parent
    / "data"
    / "topic_scenarios"
    / "basic_subjects"
    / "scenario.json"
)


def _load_scenario():
    with SCENARIO_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _expected_peers_by_user(scenario):
    expected = {}
    for subject in scenario["subjects"]:
        users = list(subject["users"])
        for user in users:
            expected[user] = sorted(u for u in users if u != user)
    return expected


def _build_messages(scenario):
    messages = []
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for subject in scenario["subjects"]:
        for user in subject["users"]:
            for text in subject["texts"]:
                messages.append(
                    {
                        "subject": subject["label"],
                        "user_id": user,
                        "text": text,
                        "ts": ts.isoformat(),
                    }
                )
                ts += timedelta(seconds=1)
    return messages


async def _wait_for_pipeline_completion(db, org_id: str, expected_messages: int, timeout_s: float = 120.0):
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages WHERE org_id = %s", (org_id,))
            count = int(cur.fetchone()[0])

        if count >= expected_messages:
            return

        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(
                f"Timed out waiting for messages to be written (expected={expected_messages}, got={count})"
            )

        await asyncio.sleep(2.0)


async def _connected_peers(client: httpx.AsyncClient, api_url: str, org_id: str, user_id: str):
    resp = await client.get(f"{api_url}/v1/orgs/{org_id}/users/{user_id}/connections")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    peers = set()
    for centroid in body.get("centroids", []):
        for ranked in centroid.get("users", []):
            ranked_user = ranked.get("user_id")
            if ranked_user and ranked_user != user_id:
                peers.add(ranked_user)

    return sorted(peers), body


@pytest.mark.asyncio
async def test_topic_scenario_connections_match_expected_peers(api_url, db):
    scenario = _load_scenario()
    expected = _expected_peers_by_user(scenario)
    messages = _build_messages(scenario)

    org_id = f"org-topic-scenario-{uuid.uuid4()}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        for idx, m in enumerate(messages):
            payload = {
                "message_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{org_id}|{idx}|{m['user_id']}|{m['text']}")),
                "user_id": m["user_id"],
                "ts": m["ts"],
                "text": m["text"],
                "source_type": "topic-scenario",
                "metadata": {"subject_label": m["subject"]},
            }
            resp = await client.post(f"{api_url}/v1/orgs/{org_id}/messages", json=payload)
            assert resp.status_code == 202, resp.text

        await _wait_for_pipeline_completion(db=db, org_id=org_id, expected_messages=len(messages))

        mismatches = {}
        for user_id, peers in expected.items():
            got, body = await _connected_peers(client, api_url, org_id, user_id)
            if got != peers:
                mismatches[user_id] = {
                    "expected": peers,
                    "got": got,
                    "response": body,
                }

        assert not mismatches, json.dumps(mismatches, default=str)
