import math
import os
from contextlib import asynccontextmanager
from typing import Optional

import libsql_client


def _client():
    return libsql_client.create_client(
        url=os.environ["TURSO_DATABASE_URL"],
        auth_token=os.environ.get("TURSO_AUTH_TOKEN", ""),
    )


@asynccontextmanager
async def get_client():
    client = _client()
    try:
        await client.execute("PRAGMA foreign_keys = ON")
        yield client
    finally:
        await client.close()


async def init_db() -> None:
    async with get_client() as client:
        await client.batch([
            """CREATE TABLE IF NOT EXISTS venues (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ssid       TEXT    NOT NULL,
                name       TEXT,
                lat        REAL,
                lng        REAL,
                created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )""",
            "CREATE INDEX IF NOT EXISTS idx_venues_ssid  ON venues(ssid)",
            "CREATE INDEX IF NOT EXISTS idx_venues_latng ON venues(lat, lng)",
            """CREATE TABLE IF NOT EXISTS speed_reports (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                venue_id      INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
                download_mbps REAL    NOT NULL,
                upload_mbps   REAL    NOT NULL,
                ping_ms       REAL,
                submitted_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                submitter_ip  TEXT    NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_reports_venue_id     ON speed_reports(venue_id)",
            "CREATE INDEX IF NOT EXISTS idx_reports_submitted_at ON speed_reports(submitted_at)",
            "CREATE INDEX IF NOT EXISTS idx_reports_ip_venue     ON speed_reports(submitter_ip, venue_id, submitted_at)",
        ])


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def find_matching_venue(
    client,
    ssid: str,
    lat: Optional[float],
    lng: Optional[float],
) -> Optional[int]:
    from src.config import VENUE_DEDUPE_RADIUS_M

    rs = await client.execute("SELECT id, lat, lng FROM venues WHERE ssid = ?", [ssid])
    for row in rs.rows:
        row_id, row_lat, row_lng = row[0], row[1], row[2]
        if lat is None and lng is None and row_lat is None and row_lng is None:
            return row_id
        if (
            lat is not None
            and lng is not None
            and row_lat is not None
            and row_lng is not None
            and haversine_m(lat, lng, row_lat, row_lng) <= VENUE_DEDUPE_RADIUS_M
        ):
            return row_id
    return None


async def rate_limit_count(
    client,
    ip: str,
    venue_id: int,
    hours: int = 1,
) -> int:
    rs = await client.execute(
        """SELECT COUNT(*) FROM speed_reports
           WHERE submitter_ip = ? AND venue_id = ?
             AND submitted_at > strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)""",
        [ip, venue_id, f"-{hours} hours"],
    )
    return rs.rows[0][0] if rs.rows else 0


def _median(values: list) -> Optional[float]:
    n = len(values)
    if n == 0:
        return None
    s = sorted(values)
    mid = n // 2
    return s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) / 2


async def venue_stats(client, venue_id: int) -> dict:
    rs = await client.execute(
        "SELECT download_mbps, upload_mbps, ping_ms, submitted_at "
        "FROM speed_reports WHERE venue_id = ? ORDER BY submitted_at DESC",
        [venue_id],
    )
    rows = rs.rows
    if not rows:
        return {
            "median_download_mbps": None,
            "median_upload_mbps": None,
            "median_ping_ms": None,
            "report_count": 0,
            "last_reported_at": None,
        }
    return {
        "median_download_mbps": _median([r[0] for r in rows]),
        "median_upload_mbps": _median([r[1] for r in rows]),
        "median_ping_ms": _median([r[2] for r in rows if r[2] is not None]),
        "report_count": len(rows),
        "last_reported_at": rows[0][3],
    }
