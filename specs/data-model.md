# Feature: Data Model

## Status

Approved

## Overview

Defines the SQLite schema that underpins all wifibuddy features. Every other spec references this one. Two tables: `venues` (a named place that has wifi) and `speed_reports` (a single speed test result submitted by a contributor at a venue).

## Goals

- Single SQLite file, no migration framework, no ORM
- Schema supports all queries needed by browse-venues, submit-speed, and admin-api specs
- Indexes keep bounding-box and per-venue queries sub-millisecond at community scale

## Non-Goals

- Multi-tenant or multi-database support
- Full-text search (SSID lookup uses `LIKE` for v1)
- Soft-delete or audit log (hard delete only in v1)

## User Stories

- As the application, I need to persist venue and report data so that speed history survives server restarts.

## Technical Design

### venues table

```sql
CREATE TABLE IF NOT EXISTS venues (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ssid        TEXT    NOT NULL,
    name        TEXT,                        -- human-readable place name (optional)
    lat         REAL,
    lng         REAL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_venues_ssid ON venues(ssid);
CREATE INDEX IF NOT EXISTS idx_venues_latng ON venues(lat, lng);
```

- `ssid` is the wifi network name as entered by the contributor (case-sensitive, trimmed).
- `name` is an optional human-readable label (e.g. "Blue Bottle Coffee on Main St") sourced from OSM or typed manually.
- `lat`/`lng` are nullable — a venue exists even if no location was provided.
- There is no uniqueness constraint on `ssid` because the same SSID at different physical locations is a different venue.

### speed_reports table

```sql
CREATE TABLE IF NOT EXISTS speed_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id        INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    download_mbps   REAL    NOT NULL,
    upload_mbps     REAL    NOT NULL,
    ping_ms         REAL,
    submitted_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    submitter_ip    TEXT    NOT NULL          -- stored for rate limiting; never exposed in API
);

CREATE INDEX IF NOT EXISTS idx_reports_venue_id ON speed_reports(venue_id);
CREATE INDEX IF NOT EXISTS idx_reports_submitted_at ON speed_reports(submitted_at);
CREATE INDEX IF NOT EXISTS idx_reports_ip_venue ON speed_reports(submitter_ip, venue_id, submitted_at);
```

- `submitter_ip` is stored only for rate-limit enforcement (1 submission per IP per venue per hour). It is never returned by any API endpoint.
- `ping_ms` is nullable — LibreSpeed may not always return a reliable ping.

### Derived queries (used by other specs)

**Median download per venue** (used by browse-venues):
```sql
SELECT venue_id, AVG(download_mbps) AS median_download
FROM (
    SELECT venue_id, download_mbps,
           ROW_NUMBER() OVER (PARTITION BY venue_id ORDER BY download_mbps) AS rn,
           COUNT(*) OVER (PARTITION BY venue_id) AS cnt
    FROM speed_reports
)
WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)
GROUP BY venue_id;
```
SQLite has no `MEDIAN()` function; this window-function approach is the standard substitute.

**Rate-limit check** (used by submit-speed):
```sql
SELECT COUNT(*) FROM speed_reports
WHERE submitter_ip = ? AND venue_id = ?
  AND submitted_at > strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-1 hour');
```

## Acceptance Criteria

- [ ] Running `db.py` on a fresh file creates both tables and all indexes with no errors
- [ ] Inserting a venue without `lat`/`lng` succeeds (nullable)
- [ ] Inserting a venue without `name` succeeds (nullable)
- [ ] Deleting a venue cascades to delete all its `speed_reports`
- [ ] The rate-limit query returns 0 for a new IP+venue pair and > 0 after a report is inserted
- [ ] The median query returns the correct median for an odd-count and even-count set of reports

## Open Questions

- None — schema is fully defined.
