import os
import pytest
import psycopg
from nats.aio.client import Client as NATS

API_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
NATS_URL = os.getenv("TEST_NATS_URL", "nats://localhost:4222")

DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
DB_PORT = int(os.getenv("TEST_DB_PORT", "5432"))
DB_NAME = os.getenv("TEST_DB_NAME", "network_builder_db")
DB_USER = os.getenv("TEST_DB_USER", "network_builder_client")
DB_PASSWORD = os.getenv("TEST_DB_PASSWORD", "network_builder_secret")


@pytest.fixture(scope="session")
def api_url() -> str:
    return API_URL


@pytest.fixture(scope="session")
def db_conninfo() -> str:
    return f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"


@pytest.fixture
def db(db_conninfo: str):
    # fresh connection per test; simple and reliable
    with psycopg.connect(db_conninfo) as conn:
        yield conn


@pytest.fixture
async def nats():
    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    try:
        yield nc
    finally:
        await nc.drain()
