import os
from dotenv import load_dotenv

load_dotenv()

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
JETSTREAM_STREAM = os.getenv("JETSTREAM_STREAM", "ingress_messages")
JETSTREAM_SUBJECTS = os.getenv("JETSTREAM_SUBJECTS", "messages.>").split(",")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "network_builder_db")
DB_USER = os.getenv("DB_USER", "network_builder_client")
DB_PASSWORD = os.getenv("DB_PASSWORD", "network_builder_secret")
