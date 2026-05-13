# Feature: Unified List + Map Browse View

## Status

Done

## Overview

The home page currently shows a list view and a map view as two separate
sub-tabs switched via `#map` URL fragment. This change merges them into a
single **Browse** view where both panels are visible at once and stay in sync:
list rows and map markers react to each other so a visitor can scan venues
without flipping back and forth. On desktop the two panels sit side-by-side
(list left, map right); on mobile they stack with the map on top. A
"Locate me" button on the map re-centers it on the visitor's current
position.

## Goals

- Replace the home page's two sub-tabs with a single combined view.
- On viewports ≥ 900px wide, list and map are shown side-by-side.
- On viewports < 900px wide, map is shown above the list (stacked).
- Hovering a list row on desktop highlights the corresponding map marker.
- Tapping a list row on mobile selects it (visual highlight + pan the map to it).
- A locate-me button on the map re-centers the map on the user's current
  geolocation when clicked.
- Header nav simplifies to two tabs: **Report** and **Browse**.

## Non-Goals

- Changing the venue detail page.
- Changing the Report (`/submit`) flow.
- Adding clustering, filtering, or search to the map/list.
- Persisting the selected row across page loads.
- Changing the `/api/venues` or `/api/venues/nearby` JSON shape.
- Updating the data model.

## User Stories

- As a **visitor on a laptop**, I want to scan a list of venues and see each
  one's location appear on the map as I hover, so I can pick the most
  convenient one without clicking back and forth.
- As a **visitor on a phone**, I want to tap a venue row and have the map jump
  to its location, so I can confirm it's near me before walking over.
- As a **visitor anywhere**, I want a "locate me" button so I can re-center
  the map on myself after panning around.

## Technical Design

Pure template + client-side change. No backend or data model changes.

### Layout

`index.html` renders one container with two children: `#tab-list` and
`#tab-map`. CSS (in the template's `head` block) uses a media query at
`min-width: 900px` to switch from a vertical stack (map first) to a
two-column grid (list left, map right). Existing `.tab-panel` / `.active`
CSS in this template is removed; the panels are always visible.

The map height becomes `min(70vh, 600px)` so it stays usable on tall
desktop monitors. On mobile, the map is the first child in DOM order so the
stacked layout naturally puts it on top.

### Reactive coupling

- Each list `<tr>` gets `data-venue-id="{{ v.id }}"` plus a `data-has-coords`
  flag and stores `data-lat` / `data-lng`.
- Each map marker is stored in a `markersById` map keyed by venue id.
- On `mouseenter` of a row, the marker is "highlighted" (stroke weight
  bumped, marker brought to the front).
- On `mouseleave`, the highlight is reverted.
- On `click` (which also fires on tap), the map pans to the marker's
  coordinates at a reasonable zoom (existing zoom preserved if already
  zoomed in), and the marker's popup opens. The row gets a `.selected`
  class for visual feedback.
- Rows without coordinates have `data-has-coords="false"` and the JS
  no-ops the hover/click handlers for them (they still link to the venue
  detail page via the name link).

### Locate-me button

A small button is positioned over the top-right of the map (Leaflet
control). Clicking it calls `navigator.geolocation.getCurrentPosition`;
on success the map flies to those coords at zoom 14; on error it shows
a transient inline message ("Couldn't get your location"). A user-position
marker (a small filled circle) is dropped at the located point and replaced
on subsequent clicks. The initial auto-locate-on-load behavior is preserved.

### Header nav

`base.html` header nav drops the Map tab. Two tabs remain: **Report**
(`/submit`) and **Browse** (`/`). `nav_active` values become `'report'`
and `'browse'`. The inline hash-sync script that toggled the Map tab is
removed (no longer needed — no Map tab and no `#map` panel switching).

### Routes

`routes/venues.py`: `index` handler changes `nav_active="list"` to
`nav_active="browse"`. `routes/reports.py`: no change (still
`nav_active="report"`).

### IDs preserved

The container `<div id="tab-list">` and `<div id="tab-map">` IDs are kept
so the existing test asserting their presence in the homepage HTML still
passes (these are now just layout containers, no longer tabs).

## Acceptance Criteria

- [ ] `GET /` returns HTML containing both `id="tab-list"` and `id="tab-map"`
      with no `display: none` CSS — both are visible together.
- [ ] The header on every page contains exactly two `<a … data-tab="…">`
      links with `data-tab` values `report` and `browse` (no `map` tab).
- [ ] On `GET /`, the Browse tab has the `active` class.
- [ ] On `GET /submit`, the Report tab has the `active` class.
- [ ] Each list `<tr>` for a venue with coordinates has `data-venue-id`,
      `data-lat`, and `data-lng` attributes.
- [ ] The map container exposes a `Locate me` button (button or Leaflet
      control with discoverable text/`aria-label`).
- [ ] CSS includes a `@media (min-width: 900px)` rule that arranges
      `#tab-list` and `#tab-map` in a two-column layout (e.g. via
      `grid-template-columns` or flex with explicit columns).
- [ ] All existing tests pass after updating those that asserted the
      old three-tab header.

## Open Questions

- Should hovering a map marker also highlight the matching list row?
  **Proposed:** yes — it's symmetric and cheap (one extra `mouseover`
  handler on each marker). Scrolling the list to bring the row into view
  is *not* in scope.
- What's the desktop breakpoint? **Proposed:** 900px — wide enough that
  a usable list + map both fit without crowding; below that, stacked.
