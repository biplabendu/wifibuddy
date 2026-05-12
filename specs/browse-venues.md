# Feature: Browse Venues

## Status

Approved

## Overview

The primary visitor experience. A visitor opens wifibuddy to find a good place to work. On desktop they see a list of venues sorted by median download speed and distance. On mobile they see a map centered on their location with speed-annotated markers. Both views are server-rendered HTML with minimal JavaScript (Leaflet for the map, htmx for partial updates).

## Goals

- Useful without an account or any interaction — data is visible immediately on page load
- Desktop: scannable list ranked by speed so the best option is at the top
- Mobile: spatial map so visitors can find what is close to them
- Fast first load — no JavaScript bundle, server-rendered HTML, static assets only

## Non-Goals

- Text search or filter by city name in v1 (map pan/zoom is sufficient)
- User-saved favorites or history
- Real-time updates (page reload or htmx swap on submit is enough)
- Filtering by date range, device type, or ISP

## User Stories

- As a **visitor on desktop**, I want to see a list of nearby venues ranked by speed so I can pick the fastest one.
- As a **visitor on mobile**, I want a map showing nearby wifi spots so I can find one that is close to me.
- As a **visitor**, I want to see how recently a speed was reported so I know if the data is stale.

## Technical Design

### Routes

| Route | Description |
|---|---|
| `GET /` | Main page — detects viewport via UA and renders list (desktop) or map (mobile) |
| `GET /venues/{id}` | Venue detail page |
| `GET /api/venues` | JSON: paginated venue list with median speeds |
| `GET /api/venues/nearby` | JSON: venues within radius of lat/lng (used by submit flow) |
| `GET /api/venues/{id}` | JSON: single venue with full report history |

### Desktop list view (`GET /`)

Server renders an HTML table sorted by `median_download DESC`, then `distance_km ASC` (distance from the requesting IP's approximate location via MaxMind GeoLite2 free DB — or omit distance sort entirely if geolocation is not available).

Each row shows:
- SSID (linked to `/venues/{id}`)
- Venue name (if set)
- Median download speed (Mbps), styled with a colour band: red < 10, amber 10–50, green > 50
- Number of reports
- Time since last report (e.g. "2 h ago")

Pagination: 25 rows per page, `?page=N` query param. htmx `hx-get` on "Load more" button appends the next page without a full reload.

### Mobile map view (`GET /`)

User-agent check: if the UA suggests a mobile browser, render the map template instead of the list template.

Leaflet map centred on the visitor's browser geolocation (with permission) or `[0, 0]` with zoom 2 (world view) as fallback.

Venue markers loaded via `GET /api/venues?bbox=<west>,<south>,<east>,<north>` as the map moves (Leaflet `moveend` event + htmx or fetch). Markers are colour-coded by median download speed (same red/amber/green thresholds as desktop). Clicking a marker shows a popup with SSID, venue name, median speed, and a link to the detail page.

### Venue detail page (`GET /venues/{id}`)

Sections (top to bottom):

1. **Summary card** — SSID, venue name, address (from OSM `name` if available), median download, median upload, median ping, number of reports, time since last report.
2. **Speed history table** — all `speed_reports` for this venue, newest first: date/time, download, upload, ping. Paginated at 20 rows.
3. **Submit a report** — inline link to `/submit?ssid=<ssid>&venue_id=<id>` pre-populates the submit form.

### Speed colour thresholds

| Download (Mbps) | Colour | Label |
|---|---|---|
| < 10 | Red | Slow |
| 10 – 50 | Amber | OK |
| > 50 | Green | Fast |

These thresholds are defined as constants in `src/config.py` so they can be changed without touching templates.

### Performance

- All venue list queries use the indexes defined in `data-model.md`.
- The map bbox query uses the `idx_venues_latng` index.
- Static assets (Pico CSS, Leaflet, htmx) are served from `/static/` with a long `Cache-Control` header (`max-age=31536000, immutable`).
- No per-request database connection — a single SQLite connection is reused via a connection pool (FastAPI lifespan context).

## Acceptance Criteria

- [ ] `GET /` returns 200 with an HTML page containing at least one venue row (given seeded data)
- [ ] The venue list is ordered by median download descending
- [ ] Each row shows SSID, median download, report count, and time since last report
- [ ] Venues with median download > 50 Mbps render with a green indicator
- [ ] Venues with median download < 10 Mbps render with a red indicator
- [ ] `GET /venues/{id}` for a valid ID returns 200 with the summary card and history table
- [ ] `GET /venues/{id}` for an invalid ID returns 404
- [ ] `GET /api/venues` returns valid JSON with a `venues` array and pagination metadata
- [ ] `GET /api/venues?bbox=...` returns only venues within the bounding box
- [ ] On a simulated mobile UA, `GET /` renders the map template, not the list template

## Open Questions

- MaxMind GeoLite2 requires a free account to download — decide whether to include distance sorting at launch or ship without it and add later.
