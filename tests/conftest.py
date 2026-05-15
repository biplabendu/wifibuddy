import asyncio
import sqlite3

import libsql_client
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_db_path(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("TURSO_DATABASE_URL", f"file:{db_file}")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "")
    return str(db_file)


@pytest.fixture
def initialized_db(test_db_path):
    from src.db import init_db
    asyncio.run(init_db())
    return test_db_path


@pytest.fixture
def conn(initialized_db):
    c = sqlite3.connect(initialized_db)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


@pytest.fixture
def client(test_db_path):
    from src.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def run_db_async(test_db_path: str, coro_fn, *args):
    """Run an async db.py function against the test database file."""
    async def _run():
        async with libsql_client.create_client(url=f"file:{test_db_path}") as client:
            await client.execute("PRAGMA foreign_keys = ON")
            return await coro_fn(client, *args)
    return asyncio.run(_run())


def seed_venue(conn, ssid="TestNet", name="Test Cafe",
               lat=37.77, lng=-122.41,
               download=50.0, upload=10.0, ping=15.0,
               ip="1.2.3.4"):
    cur = conn.execute(
        "INSERT INTO venues (ssid, name, lat, lng) VALUES (?, ?, ?, ?)",
        (ssid, name, lat, lng),
    )
    venue_id = cur.lastrowid
    conn.execute(
        "INSERT INTO speed_reports "
        "(venue_id, download_mbps, upload_mbps, ping_ms, submitter_ip) "
        "VALUES (?, ?, ?, ?, ?)",
        (venue_id, download, upload, ping, ip),
    )
    conn.commit()
    return venue_id
