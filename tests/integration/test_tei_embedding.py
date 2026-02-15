import math
import os

import httpx
import pytest


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def test_tei_embed_endpoint_basic_shape():
    tei_url = os.getenv("TEST_TEI_URL", "http://localhost:8080").rstrip("/")
    expected_dim = int(os.getenv("TEST_EMBED_DIM", "768"))

    payload = {"inputs": "hello from tei integration test"}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{tei_url}/embed", json=payload)
    except httpx.HTTPError as exc:
        pytest.fail(f"TEI endpoint not reachable at {tei_url}/embed: {exc}")

    assert resp.status_code == 200, resp.text

    body = resp.json()

    # TEI may return either one vector (`[float, ...]`) or a batch (`[[float, ...]]`).
    if isinstance(body, list) and body and isinstance(body[0], list):
        vector = body[0]
    else:
        vector = body

    assert isinstance(vector, list)
    assert len(vector) == expected_dim
    assert all(_is_number(x) for x in vector)
    assert any(abs(float(x)) > 0.0 for x in vector)
