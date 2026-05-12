import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_db_path(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    return str(db_file)


@pytest.fixture
def initialized_db(test_db_path):
    from src.db import init_db
    init_db()
    return test_db_path


@pytest.fixture
def conn(initialized_db):
    from src.db import get_conn
    c = get_conn()
    yield c
    c.close()


@pytest.fixture
def client(test_db_path):
    from src.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


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
