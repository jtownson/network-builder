import os
import pytest

STREAM = os.getenv("TEST_JETSTREAM_STREAM", "ingress_messages")

@pytest.mark.asyncio
async def test_stream_has_both_subjects(nats):
    js = nats.jetstream()
    info = await js.stream_info(STREAM)
    subjects = set(info.config.subjects or [])
    assert "messages.>" in subjects, f"missing messages.> in {subjects}"
    assert "embeddings.>" in subjects, f"missing embeddings.> in {subjects}"
    assert "clusters.>" in subjects, f"missing clusters.> in {subjects}"
