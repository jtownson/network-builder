import asyncio
import os

from dotenv import load_dotenv
from nats.aio.client import Client as NATS
from nats.js.api import ConsumerConfig, DeliverPolicy, AckPolicy

from app.core.nats_client import NatsJetStreamPublisher

load_dotenv()

STREAM = os.getenv("JETSTREAM_STREAM", "ingress_messages")
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")

subjects = ["messages.>","embeddings.>","clusters.>"]
consumers = [
    # (durable_name, filter_subject, deliver_subject)
    ("api_messages_v1", "messages.>", None),
    ("embedder_v1", "messages.>", f"deliver.embedder.embedder_v1"),
    ("clusterer_v1", "embeddings.>", None),
]

async def main():
    publisher = NatsJetStreamPublisher(
        nats_url=NATS_URL,
        stream_name=STREAM,
        subjects=subjects,
    )
    await publisher.connect()
    await publisher.ensure_stream()
    await publisher.close()

    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    js = nc.jetstream()

    # Ensure consumers
    for durable, filt, deliver_subject in consumers:
        ccfg = ConsumerConfig(
            durable_name=durable,
            deliver_policy=DeliverPolicy.ALL,
            ack_policy=AckPolicy.EXPLICIT,
            ack_wait=30,
            max_ack_pending=10_000,
            filter_subject=filt,
            deliver_subject=deliver_subject,
        )
        try:
            await js.add_consumer(STREAM, ccfg)
            print(f"✅ created consumer {durable} filter={filt}")
        except Exception as e:
            msg = str(e).lower()
            if "already" in msg and "consumer" in msg:
                print(f"ℹ️ consumer exists {durable}")
            else:
                raise

    await nc.drain()

if __name__ == "__main__":
    asyncio.run(main())
