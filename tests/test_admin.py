"""Tests for specs/admin-api.md acceptance criteria."""
from tests.conftest import seed_venue

_AUTH = ("admin", "changeme")
_BAD_AUTH = ("admin", "wrong")


def test_delete_report_returns_204(client, conn):
    seed_venue(conn)
    report_id = conn.execute("SELECT id FROM speed_reports LIMIT 1").fetchone()["id"]
    response = client.delete(f"/admin/reports/{report_id}", auth=_AUTH)
    assert response.status_code == 204
    assert conn.execute("SELECT COUNT(*) FROM speed_reports WHERE id=?", (report_id,)).fetchone()[0] == 0


def test_delete_report_wrong_credentials_returns_401(client, conn):
    seed_venue(conn)
    report_id = conn.execute("SELECT id FROM speed_reports LIMIT 1").fetchone()["id"]
    response = client.delete(f"/admin/reports/{report_id}", auth=_BAD_AUTH)
    assert response.status_code == 401


def test_delete_report_nonexistent_returns_404(client):
    response = client.delete("/admin/reports/99999", auth=_AUTH)
    assert response.status_code == 404


def test_delete_venue_cascades_reports(client, conn):
    venue_id = seed_venue(conn)
    assert conn.execute("SELECT COUNT(*) FROM speed_reports WHERE venue_id=?", (venue_id,)).fetchone()[0] == 1
    response = client.delete(f"/admin/venues/{venue_id}", auth=_AUTH)
    assert response.status_code == 204
    assert conn.execute("SELECT COUNT(*) FROM venues WHERE id=?", (venue_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM speed_reports WHERE venue_id=?", (venue_id,)).fetchone()[0] == 0


def test_admin_reports_excludes_submitter_ip(client, conn):
    seed_venue(conn)
    response = client.get("/admin/reports", auth=_AUTH)
    assert response.status_code == 200
    data = response.json()
    for report in data["reports"]:
        assert "submitter_ip" not in report


def test_api_venues_json_shape(client, conn):
    seed_venue(conn, ssid="ShapeNet", download=60.0, upload=15.0)
    response = client.get("/api/venues")
    assert response.status_code == 200
    data = response.json()
    v = data["venues"][0]
    for key in ("id", "ssid", "median_download_mbps", "report_count", "last_reported_at"):
        assert key in v, f"Missing key: {key}"


def test_api_venue_detail_404(client):
    response = client.get("/api/venues/99999")
    assert response.status_code == 404
    assert "error" in response.json()


def test_api_venues_no_submitter_ip(client, conn):
    seed_venue(conn)
    response = client.get("/api/venues")
    data = response.json()
    for v in data["venues"]:
        assert "submitter_ip" not in v
        for r in v.get("reports", []):
            assert "submitter_ip" not in r


def test_api_venues_cors_header(client, conn):
    seed_venue(conn)
    response = client.get("/api/venues")
    assert response.headers.get("access-control-allow-origin") == "*"
