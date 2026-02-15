from typing import Optional, Sequence

from nats.aio.client import Client as NATS
from nats.js.api import StreamConfig, RetentionPolicy, StorageType


class NatsJetStreamPublisher:
    def __init__(self, nats_url: str, stream_name: str, subjects: Sequence[str]) -> None:
        self._nats_url = nats_url
        self._stream_name = stream_name
        self._subjects = list(subjects)
        self._nc: Optional[NATS] = None
        self._js = None

    @property
    def stream_name(self) -> str:
        return self._stream_name

    async def connect(self) -> None:
        nc = NATS()
        await nc.connect(servers=[self._nats_url])
        self._nc = nc
        self._js = nc.jetstream()

    async def ensure_stream(self) -> None:
        # Create or update stream config (dev-friendly)
        cfg = StreamConfig(
            name=self._stream_name,
            subjects=self._subjects,
            retention=RetentionPolicy.LIMITS,
            storage=StorageType.FILE,
            max_msgs=-1,
            max_bytes=-1,
            max_age=0,
            num_replicas=1,
        )
        try:
            await self._js.add_stream(cfg)
        except Exception as e:
            msg = str(e).lower()
            if "already" in msg and "stream" in msg:
                await self._js.update_stream(cfg)
            else:
                raise

    async def publish(self, subject: str, payload: bytes):
        # Returns PubAck (stream + seq)
        return await self._js.publish(subject, payload)

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.drain()
            self._nc = None
            self._js = None
