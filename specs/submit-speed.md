# Feature: Submit Speed Report

## Status

Approved

## Overview

A contributor connects to a public wifi network, opens wifibuddy, and submits a speed test result. The app runs the speed test automatically in the browser (LibreSpeed), optionally detects the contributor's location to suggest nearby venues from OpenStreetMap, and stores the report in SQLite. A rate limit of one report per IP per venue per hour prevents spam without requiring an account.

## Goals

- Zero-friction submission: SSID + one button to run test + optional location confirm
- No account required — fully anonymous
- Rate limiting enforced server-side with testable hooks
- Graceful degradation: geolocation denied or OSM slow → falls back to manual venue name

## Non-Goals

- Browser auto-detection of connected SSID (not possible in web APIs — user types it)
- Email confirmation or user accounts
- CAPTCHA (rate limiting + honeypot field is sufficient for v1)
- Duplicate venue deduplication (handled by admin in v1)

## User Stories

- As a **contributor**, I want to submit my wifi speed so that others know what to expect at this location.
- As a **contributor**, I want the app to run the speed test for me so that I don't have to copy numbers from another tool.
- As the **system**, I want to rate-limit submissions so that a single IP cannot flood the database.

## Technical Design

### Submission flow

1. Contributor navigates to `/submit`.
2. Types the SSID (network name) into a text field. Label reads: *"Enter the wifi name shown on your device (e.g. 'CoffeeShop_Guest')"*.
3. Clicks **Run Speed Test**. LibreSpeed iframe/widget runs download + upload + ping test. Results populate hidden form fields automatically on completion.
4. App requests browser geolocation (`navigator.geolocation.getCurrentPosition`).
   - If granted: `GET /api/venues/nearby?lat=&lng=&radius=200` returns up to 5 venue names from OSM within 200 m. Contributor selects one or skips.
   - If denied or OSM returns nothing: contributor may type a venue name manually (optional).
5. Contributor clicks **Submit**.
6. `POST /reports` — server validates, checks rate limit, inserts venue (if new SSID+location combination) and report, returns `303 See Other` to `/venues/{id}`.

### LibreSpeed integration

Self-hosted LibreSpeed (`/static/librespeed/`). The test widget posts results to a JS callback; the callback populates `<input type="hidden">` fields `download_mbps`, `upload_mbps`, `ping_ms` before form submission.

### OSM nearby query

`GET /api/venues/nearby` queries the local `venues` table first (existing known venues), then falls back to the Nominatim/Overpass API if fewer than 3 local results exist. Result is cached in `sessionStorage` — no repeat queries on the same page load.

The OSM query uses the Overpass API with a bounding box derived from the contributor's coordinates ± ~200 m. It requests only: `name`, `amenity` (cafe, restaurant, library), `lat`, `lng`.

### POST /reports — server validation

| Field | Rule |
|---|---|
| `ssid` | Required, 1–64 chars, trimmed |
| `download_mbps` | Required, float, > 0, < 10000 |
| `upload_mbps` | Required, float, > 0, < 10000 |
| `ping_ms` | Optional, float, > 0, < 60000 |
| `lat` | Optional, float, −90 to 90 |
| `lng` | Optional, float, −180 to 180 |
| `name` | Optional, 1–128 chars, trimmed |
| `_honey` | Honeypot — must be empty; if set, return 200 silently (do not insert) |

Rate limit: if `submitter_ip` has ≥ 1 report for the same `venue_id` in the last hour, return `429 Too Many Requests` with a plain-text message: *"You've already submitted a report for this network recently. Try again in an hour."*

On success: insert into `venues` (if no matching venue exists) then `speed_reports`, redirect `303` to `/venues/{venue_id}`.

### Venue matching logic

A "matching venue" is an existing row in `venues` where:
- `ssid` matches exactly (case-sensitive, trimmed), AND
- `lat`/`lng` is within ~50 m of the submitted coordinates (using the Haversine approximation), OR
- both submitted and existing `lat`/`lng` are NULL.

If no match, insert a new venue row.

## Acceptance Criteria

- [ ] Submitting a valid report with SSID, download, upload inserts one `venues` row and one `speed_reports` row
- [ ] Submitting with `_honey` populated inserts nothing and returns 200
- [ ] Submitting the same IP + venue twice within one hour returns 429 on the second attempt
- [ ] Submitting with `download_mbps = 0` returns 422 with a validation error
- [ ] Submitting with no SSID returns 422 with a validation error
- [ ] Submitting without geolocation (lat/lng omitted) succeeds; venue row has NULL lat/lng
- [ ] A successful submission redirects to `/venues/{id}` for the correct venue
- [ ] Two submissions with the same SSID within 50 m of each other reuse the same venue row

## Open Questions

- None — all design decisions resolved above.
