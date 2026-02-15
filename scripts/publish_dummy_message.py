import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from nats.aio.client import Client as NATS
from nats.aio.msg import Msg
from nats.js import JetStreamContext

load_dotenv()

async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = NATS()
    await nc.connect(servers=[nats_url])
    js: JetStreamContext = nc.jetstream()

    org_id = os.getenv("ORG_ID", "org-1")
    user_id = os.getenv("USER_ID", "user-1")

    event = {
        "event_type": "message.created",
        "event_version": 1,
        "event_id": str(uuid.uuid4()),
        "org_id": org_id,
        "message": {
            "message_id": str(uuid.uuid4()),
            "user_id": user_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "source_type": "demo",
            "text": "Hello from publisher — first vertical slice ✅",
            "metadata": {"demo": True},
        },
    }

    subject = f"messages.{org_id}"
    ack = await js.publish(subject, json.dumps(event).encode("utf-8"))
    print(f"✅ Published to {subject}: stream={ack.stream} seq={ack.seq}")
    await nc.drain()

if __name__ == "__main__":
    asyncio.run(main())
