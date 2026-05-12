"""Tests for specs/data-model.md acceptance criteria."""
import pytest
from tests.conftest import seed_venue


def test_init_creates_tables(conn):
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "venues" in tables
    assert "speed_reports" in tables


def test_init_creates_indexes(conn):
    indexes = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert "idx_venues_ssid" in indexes
    assert "idx_venues_latng" in indexes
    assert "idx_reports_venue_id" in indexes
    assert "idx_reports_submitted_at" in indexes
    assert "idx_reports_ip_venue" in indexes


def test_venue_nullable_lat_lng(conn):
    conn.execute("INSERT INTO venues (ssid) VALUES ('NoGPS')")
    conn.commit()
    row = conn.execute("SELECT lat, lng FROM venues WHERE ssid='NoGPS'").fetchone()
    assert row["lat"] is None
    assert row["lng"] is None


def test_venue_nullable_name(conn):
    conn.execute("INSERT INTO venues (ssid) VALUES ('NoName')")
    conn.commit()
    row = conn.execute("SELECT name FROM venues WHERE ssid='NoName'").fetchone()
    assert row["name"] is None


def test_delete_venue_cascades_reports(conn):
    venue_id = seed_venue(conn)
    assert conn.execute("SELECT COUNT(*) FROM speed_reports WHERE venue_id=?", (venue_id,)).fetchone()[0] == 1
    conn.execute("DELETE FROM venues WHERE id=?", (venue_id,))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM venues WHERE id=?", (venue_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM speed_reports WHERE venue_id=?", (venue_id,)).fetchone()[0] == 0


def test_rate_limit_zero_for_new_pair(conn):
    from src.db import rate_limit_count
    seed_venue(conn, ssid="NewNet")
    venue_id = conn.execute("SELECT id FROM venues WHERE ssid='NewNet'").fetchone()["id"]
    assert rate_limit_count(conn, "9.9.9.9", venue_id) == 0


def test_rate_limit_nonzero_after_report(conn):
    from src.db import rate_limit_count
    venue_id = seed_venue(conn, ssid="RatNet", ip="5.5.5.5")
    assert rate_limit_count(conn, "5.5.5.5", venue_id) >= 1


def test_median_odd_count(conn):
    from src.db import venue_stats
    venue_id = seed_venue(conn, ssid="OddNet", download=10.0)
    conn.execute(
        "INSERT INTO speed_reports (venue_id, download_mbps, upload_mbps, submitter_ip) VALUES (?,30.0,5.0,'x')",
        (venue_id,),
    )
    conn.execute(
        "INSERT INTO speed_reports (venue_id, download_mbps, upload_mbps, submitter_ip) VALUES (?,20.0,5.0,'y')",
        (venue_id,),
    )
    conn.commit()
    stats = venue_stats(conn, venue_id)
    assert stats["median_download_mbps"] == pytest.approx(20.0)


def test_median_even_count(conn):
    from src.db import venue_stats
    venue_id = seed_venue(conn, ssid="EvenNet", download=10.0)
    conn.execute(
        "INSERT INTO speed_reports (venue_id, download_mbps, upload_mbps, submitter_ip) VALUES (?,30.0,5.0,'x')",
        (venue_id,),
    )
    conn.commit()
    stats = venue_stats(conn, venue_id)
    assert stats["median_download_mbps"] == pytest.approx(20.0)
