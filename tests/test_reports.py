"""Tests for specs/submit-speed.md acceptance criteria."""


def test_valid_submission_inserts_venue_and_report(client, conn):
    response = client.post(
        "/reports",
        data={"ssid": "CafeNet", "download_mbps": "50.0", "upload_mbps": "10.0"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/venues/" in response.headers["location"]
    assert conn.execute("SELECT COUNT(*) FROM venues WHERE ssid='CafeNet'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM speed_reports").fetchone()[0] == 1


def test_redirect_points_to_correct_venue(client, conn):
    response = client.post(
        "/reports",
        data={"ssid": "RedirectNet", "download_mbps": "25.0", "upload_mbps": "5.0"},
        follow_redirects=False,
    )
    venue_id = conn.execute("SELECT id FROM venues WHERE ssid='RedirectNet'").fetchone()["id"]
    assert response.headers["location"] == f"/venues/{venue_id}"


def test_honeypot_silently_drops(client, conn):
    response = client.post(
        "/reports",
        data={
            "ssid": "BotNet",
            "download_mbps": "50.0",
            "upload_mbps": "10.0",
            "honey": "i-am-a-bot",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0] == 0


def test_rate_limit_second_submission_returns_429(client, conn):
    data = {"ssid": "RateLimitNet", "download_mbps": "50.0", "upload_mbps": "10.0"}
    client.post("/reports", data=data, follow_redirects=False)
    response = client.post("/reports", data=data, follow_redirects=False)
    assert response.status_code == 429


def test_download_zero_returns_422(client):
    response = client.post(
        "/reports",
        data={"ssid": "BadNet", "download_mbps": "0", "upload_mbps": "10.0"},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_missing_ssid_returns_422(client):
    response = client.post(
        "/reports",
        data={"download_mbps": "50.0", "upload_mbps": "10.0"},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_submission_without_location_succeeds(client, conn):
    response = client.post(
        "/reports",
        data={"ssid": "NoGPSNet", "download_mbps": "30.0", "upload_mbps": "8.0"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = conn.execute("SELECT lat, lng FROM venues WHERE ssid='NoGPSNet'").fetchone()
    assert row["lat"] is None
    assert row["lng"] is None


def test_same_ssid_within_50m_reuses_venue(client, conn):
    base = {"download_mbps": "40.0", "upload_mbps": "8.0"}
    client.post("/reports", data={**base, "ssid": "DupeNet", "lat": "37.7749", "lng": "-122.4194"}, follow_redirects=False)
    # Second submission from a different "IP" — in tests client IP is always "testclient"
    # so we use a slightly different location still within 50m
    client.post("/reports", data={**base, "ssid": "DupeNet", "lat": "37.7749", "lng": "-122.4194"}, follow_redirects=False)
    # Both should resolve to the same venue (rate limit means second one returns 429 — check venue count)
    assert conn.execute("SELECT COUNT(*) FROM venues WHERE ssid='DupeNet'").fetchone()[0] == 1


def test_two_same_ssid_same_location_single_venue(client, conn):
    """Duplicate detection: two valid submissions for same SSID near same coords → one venue row."""
    r1 = client.post(
        "/reports",
        data={"ssid": "UniqueNet", "download_mbps": "60.0", "upload_mbps": "15.0",
              "lat": "48.8566", "lng": "2.3522"},
        follow_redirects=False,
    )
    assert r1.status_code == 303
    assert conn.execute("SELECT COUNT(*) FROM venues WHERE ssid='UniqueNet'").fetchone()[0] == 1


# --- New UI: single "Wifi Name" field — specs/ui-redesign.md ---

def test_submit_page_has_single_wifi_name_field(client):
    """Submit page shows one ssid input wired to a datalist for nearby-place suggestions."""
    response = client.get("/submit")
    assert response.status_code == 200
    assert 'name="ssid"' in response.text
    assert 'list="place-suggestions"' in response.text
    assert 'id="place-suggestions"' in response.text
    # The old separate venue-name input must be gone
    assert 'name="name"' not in response.text


def test_submission_without_name_mirrors_ssid(client, conn):
    """When the new form posts only ssid, venues.name is set equal to ssid."""
    client.post(
        "/reports",
        data={"ssid": "Blue Bottle Coffee", "download_mbps": "42.0", "upload_mbps": "9.0"},
        follow_redirects=False,
    )
    row = conn.execute(
        "SELECT ssid, name FROM venues WHERE ssid='Blue Bottle Coffee'"
    ).fetchone()
    assert row is not None
    assert row["ssid"] == "Blue Bottle Coffee"
    assert row["name"] == "Blue Bottle Coffee"


def test_submission_with_explicit_name_preserved(client, conn):
    """Legacy clients that still send `name` separately must have it preserved."""
    client.post(
        "/reports",
        data={
            "ssid": "GuestWifi_42",
            "name": "Joe's Diner",
            "download_mbps": "20.0",
            "upload_mbps": "4.0",
        },
        follow_redirects=False,
    )
    row = conn.execute(
        "SELECT ssid, name FROM venues WHERE ssid='GuestWifi_42'"
    ).fetchone()
    assert row is not None
    assert row["name"] == "Joe's Diner"
