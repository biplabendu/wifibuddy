# Feature: Admin Endpoints and JSON API

## Status

Approved

## Overview

Two separate concerns handled in one spec because they share the same route design. (1) A minimal password-protected admin API for deleting spam reports and duplicate venues — no UI, intended for use with curl or any HTTP client. (2) JSON responses on all existing routes so that a future mobile app or third-party client can consume the same data without a separate service.

## Goals

- Admin can delete any report or venue with a single curl command
- All data routes return JSON when requested (content negotiation or `/api/` prefix)
- No admin UI to build or secure beyond HTTP Basic Auth

## Non-Goals

- Admin create/edit endpoints (inserts happen through the normal submit flow)
- Role-based access control or multi-admin accounts
- Audit log of admin actions (v1 — SQLite history is sufficient)
- Public write API (submissions go through the HTML form flow only in v1)

## User Stories

- As the **admin**, I want to delete a spam report via curl so that bad data does not affect speed averages.
- As the **admin**, I want to delete a duplicate venue via curl so that reports are not split across two records.
- As a **third-party developer**, I want JSON endpoints so that I can build a mobile client against the same data.

## Technical Design

### Authentication

HTTP Basic Auth. Credentials are read from environment variables:

```
ADMIN_USERNAME=<set in .env>
ADMIN_PASSWORD=<set in .env>
```

A FastAPI dependency (`require_admin`) checks the `Authorization` header on every admin route. Returns `401 Unauthorized` with `WWW-Authenticate: Basic` if missing or wrong. No sessions, no tokens.

### Admin endpoints

All admin routes are prefixed `/admin/`.

#### DELETE /admin/reports/{id}

Deletes a single speed report by ID.

- `204 No Content` on success
- `404 Not Found` if the ID does not exist
- `401` if not authenticated

Example:
```bash
curl -u admin:password -X DELETE https://example.com/admin/reports/42
```

#### DELETE /admin/venues/{id}

Deletes a venue and all its reports (cascade, per data model).

- `204 No Content` on success
- `404 Not Found` if the ID does not exist
- `401` if not authenticated

Example:
```bash
curl -u admin:password -X DELETE https://example.com/admin/venues/7
```

#### GET /admin/reports?limit=50&offset=0

Returns the 50 most recent reports (newest first) for review. Useful for spotting spam before deleting.

- `200 OK` with JSON array of `{id, venue_id, ssid, download_mbps, upload_mbps, ping_ms, submitted_at}` — `submitter_ip` is **excluded** from the response body even for admins (unnecessary exposure).
- `401` if not authenticated

### JSON API

Content negotiation: any route that returns HTML also returns JSON if the request includes `Accept: application/json`. Additionally, all routes are mirrored under `/api/` that always return JSON regardless of `Accept` header.

| HTML route | JSON equivalent | Notes |
|---|---|---|
| `GET /` | `GET /api/venues` | Paginated venue list with median speeds |
| `GET /venues/{id}` | `GET /api/venues/{id}` | Venue detail + report history |
| `GET /` (map bbox) | `GET /api/venues?bbox=w,s,e,n` | Venues within bounding box |
| `GET /api/venues/nearby` | same | Already JSON-only |

JSON response shape for a venue:
```json
{
  "id": 1,
  "ssid": "CoffeeShop_Guest",
  "name": "Blue Bottle Coffee on Main St",
  "lat": 37.7749,
  "lng": -122.4194,
  "median_download_mbps": 47.3,
  "median_upload_mbps": 12.1,
  "median_ping_ms": 14.0,
  "report_count": 8,
  "last_reported_at": "2026-05-12T10:23:00Z"
}
```

JSON response shape for a report (within venue detail):
```json
{
  "id": 42,
  "download_mbps": 51.2,
  "upload_mbps": 13.4,
  "ping_ms": 11.0,
  "submitted_at": "2026-05-12T10:23:00Z"
}
```

`submitter_ip` is never included in any public JSON response.

### CORS

The `/api/` routes include `Access-Control-Allow-Origin: *` so that a future mobile app or browser-based client on a different origin can fetch them without a proxy.

## Acceptance Criteria

- [ ] `DELETE /admin/reports/{id}` with correct credentials returns `204` and the row is gone from SQLite
- [ ] `DELETE /admin/reports/{id}` with wrong credentials returns `401`
- [ ] `DELETE /admin/reports/{id}` for a non-existent ID returns `404`
- [ ] `DELETE /admin/venues/{id}` deletes the venue and all its reports (cascade)
- [ ] `GET /admin/reports` returns JSON and does not include `submitter_ip`
- [ ] `GET /api/venues` returns valid JSON matching the specified shape
- [ ] `GET /api/venues/{id}` returns `404` JSON for a non-existent venue
- [ ] `GET /api/venues` response does not include `submitter_ip` in any report object
- [ ] `GET /api/venues` includes `Access-Control-Allow-Origin: *` header

## Open Questions

- None — design fully resolved above.
