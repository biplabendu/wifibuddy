# Feature: UI Redesign — Global Tabs and One-Click Report

## Status

Done

## Overview

Two coupled UI changes:

1. **Global tab navigation.** Three tabs — **Report**, **List**, **Map** — appear in the site header on every page and remain visible at all times. The active tab is highlighted based on the current path. Replaces the current header link to "Submit Speed" and the per-page tab bar on the home page.

2. **One-click Report page.** The Report page (`/submit`) is reduced to a single visible field at the top — **Wifi Name** — plus one primary button: **Run Test**. Clicking Run Test (a) prompts for geolocation, (b) loads nearby OSM place names as suggestions for the Wifi Name field, and (c) runs the speed test, filling download/upload/ping internally. The user picks or confirms the Wifi Name, then submits.

The submit form no longer distinguishes between SSID and venue name. A single "Wifi Name" value is stored in both the `ssid` and `name` columns of the `venues` row on insert. Existing rows are untouched.

## Goals

- Report, List, and Map tabs always visible in the site header.
- The Report page shows exactly one input field above the fold: Wifi Name.
- One button (Run Test) triggers geolocation, nearby-place fetch, and speed test in sequence.
- Nearby OSM place names appear as datalist suggestions on the Wifi Name input once location is known.
- A submitted report stores the same value in `venues.ssid` and `venues.name`.

## Non-Goals

- Backfilling or migrating existing rows where `ssid != name`.
- Google Places integration (decided against — OSM Nominatim/Overpass only).
- Changing the data model schema (still `ssid TEXT NOT NULL`, `name TEXT`).
- Changing the List or Map tabs' content or layout.
- Removing the venue detail page or its existing layout.
- Account/login.

## User Stories

- As a visitor on any page, I want to see Report / List / Map tabs in the header so I can switch context with one click.
- As a contributor on the Report page, I want one button that captures my location and runs a speed test so I don't have to fill out a form.
- As a contributor whose location is detected, I want to pick my venue's name from nearby store suggestions so I don't have to type it from scratch.

## Technical Design

### Tab navigation

- Move the tab bar from `index.html` into `base.html` so it renders on every page.
- Three links, styled as tabs:
  - **Report** → `/submit`
  - **List** → `/`
  - **Map** → `/#map`
- Active tab is determined server-side via the request path passed into the template context (a `nav_active` variable: `"report" | "list" | "map"`). The Map tab is "active" only when the URL has `#map`, which the server can't see — so we fall back to a small inline script that re-applies the active class based on `location.hash` on page load.
- Remove the existing duplicate per-page tab bar in `index.html`. The list/map panels remain, switched by `location.hash` and the existing `switchTab` JS, but the tab buttons themselves now live in the header.

### Report page

- Template (`submit.html`) is rewritten:
  - Above the fold: one text input — Wifi Name — and one primary button **Run Test**.
  - Below: a collapsed/hidden status area that becomes visible once Run Test is clicked, showing speed test progress and results in read-only form.
  - Hidden inputs: `download_mbps`, `upload_mbps`, `ping_ms`, `lat`, `lng`. Populated by JS during the test.
  - A final **Submit** button appears once both the Wifi Name is filled and the speed test has completed successfully.
- "Run Test" handler:
  1. Calls `navigator.geolocation.getCurrentPosition` (the browser shows its own permission prompt).
  2. On success, fires `/api/venues/nearby?lat=…&lng=…` and populates the Wifi Name `<datalist>` suggestions.
  3. Starts the existing NDT7 speed test pipeline; updates hidden fields on completion.
  4. If geolocation is denied or unavailable, skips the suggestions step but still runs the speed test.
- On submit, the form POSTs to `/reports` as today, but `name` is sent equal to `ssid` (both come from the single Wifi Name input).

### Backend changes

- `routes/reports.py`:
  - Accept the form as today; if `name` is missing or empty but `ssid` is present, set `name = ssid` on insert.
  - No other backend logic changes.
- All other routes unchanged.

### Template wiring

- `base.html` accepts an optional `nav_active` context variable (default `None`).
- `main.py` / route handlers pass `nav_active` in the context for `/` (`"list"`) and `/submit` (`"report"`). Map is handled by client-side hash detection.

## Acceptance Criteria

- [ ] Every server-rendered page contains `<a … data-tab="report">`, `<a … data-tab="list">`, `<a … data-tab="map">` in the header.
- [ ] On `GET /`, the List tab has the active class.
- [ ] On `GET /submit`, the Report tab has the active class.
- [ ] The Report page (`GET /submit`) contains exactly one visible `<input>` of type `text` with `name="ssid"` (Wifi Name) before the "Run Test" button in DOM order.
- [ ] The Report page contains a `<datalist id="venue-datalist">` element wired to the Wifi Name input via `list="venue-datalist"`.
- [ ] The Report page no longer contains a separate `<input name="name">` for venue name.
- [ ] `POST /reports` with only `ssid` set (no `name` in form) stores the same value in both `venues.ssid` and `venues.name`.
- [ ] `POST /reports` with `name` explicitly set (legacy clients) continues to use the provided `name`.
- [ ] All 38 existing tests still pass, except those asserting the old two-field form layout (which are updated to match the new spec).

## Open Questions

- Should the "Run Test" button retry geolocation if the user initially denies it? **Proposed:** no — fall back to speed test only and show "Location skipped — type the Wifi Name."
- Should we keep the `/submit` URL or move to `/report`? **Proposed:** keep `/submit` to avoid breaking inbound links; the visible tab label is "Report."
