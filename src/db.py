import math
import os
import sqlite3
from typing import Optional


def _db_path() -> str:
    return os.environ.get("DATABASE_PATH", "wifibuddy.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS venues (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ssid       TEXT    NOT NULL,
                name       TEXT,
                lat        REAL,
                lng        REAL,
                created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            );

            CREATE INDEX IF NOT EXISTS idx_venues_ssid  ON venues(ssid);
            CREATE INDEX IF NOT EXISTS idx_venues_latng ON venues(lat, lng);

            CREATE TABLE IF NOT EXISTS speed_reports (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                venue_id      INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
                download_mbps REAL    NOT NULL,
                upload_mbps   REAL    NOT NULL,
                ping_ms       REAL,
                submitted_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                submitter_ip  TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_reports_venue_id     ON speed_reports(venue_id);
            CREATE INDEX IF NOT EXISTS idx_reports_submitted_at ON speed_reports(submitted_at);
            CREATE INDEX IF NOT EXISTS idx_reports_ip_venue     ON speed_reports(submitter_ip, venue_id, submitted_at);
        """)
        conn.commit()
    finally:
        conn.close()


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_matching_venue(
    conn: sqlite3.Connection,
    ssid: str,
    lat: Optional[float],
    lng: Optional[float],
) -> Optional[int]:
    from src.config import VENUE_DEDUPE_RADIUS_M

    rows = conn.execute(
        "SELECT id, lat, lng FROM venues WHERE ssid = ?", (ssid,)
    ).fetchall()
    for row in rows:
        if lat is None and lng is None and row["lat"] is None and row["lng"] is None:
            return row["id"]
        if (
            lat is not None
            and lng is not None
            and row["lat"] is not None
            and row["lng"] is not None
            and haversine_m(lat, lng, row["lat"], row["lng"]) <= VENUE_DEDUPE_RADIUS_M
        ):
            return row["id"]
    return None


def rate_limit_count(
    conn: sqlite3.Connection,
    ip: str,
    venue_id: int,
    hours: int = 1,
) -> int:
    row = conn.execute(
        """SELECT COUNT(*) FROM speed_reports
           WHERE submitter_ip = ? AND venue_id = ?
             AND submitted_at > strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)""",
        (ip, venue_id, f"-{hours} hours"),
    ).fetchone()
    return row[0]


def _median(values: list) -> Optional[float]:
    n = len(values)
    if n == 0:
        return None
    s = sorted(values)
    mid = n // 2
    return s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) / 2


def venue_stats(conn: sqlite3.Connection, venue_id: int) -> dict:
    rows = conn.execute(
        "SELECT download_mbps, upload_mbps, ping_ms, submitted_at "
        "FROM speed_reports WHERE venue_id = ? ORDER BY submitted_at DESC",
        (venue_id,),
    ).fetchall()
    if not rows:
        return {
            "median_download_mbps": None,
            "median_upload_mbps": None,
            "median_ping_ms": None,
            "report_count": 0,
            "last_reported_at": None,
        }
    return {
        "median_download_mbps": _median([r["download_mbps"] for r in rows]),
        "median_upload_mbps": _median([r["upload_mbps"] for r in rows]),
        "median_ping_ms": _median(
            [r["ping_ms"] for r in rows if r["ping_ms"] is not None]
        ),
        "report_count": len(rows),
        "last_reported_at": rows[0]["submitted_at"],
    }
