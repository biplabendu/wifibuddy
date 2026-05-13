from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import src.config as config
import src.db as db

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")

_CORS = {"Access-Control-Allow-Origin": "*"}


def speed_class(mbps: Optional[float]) -> str:
    if mbps is None:
        return "unknown"
    if mbps < config.SPEED_SLOW_MBPS:
        return "slow"
    if mbps <= config.SPEED_FAST_MBPS:
        return "ok"
    return "fast"


def time_ago(iso: Optional[str]) -> str:
    if not iso:
        return "never"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        s = int((datetime.now(timezone.utc) - dt).total_seconds())
        if s < 60:
            return f"{s}s ago"
        if s < 3600:
            return f"{s // 60}m ago"
        if s < 86400:
            return f"{s // 3600}h ago"
        return f"{s // 86400}d ago"
    except Exception:
        return iso


def _enrich_venue(conn, row: dict) -> dict:
    stats = db.venue_stats(conn, row["id"])
    md = stats["median_download_mbps"]
    return {
        **row,
        **stats,
        "speed_class": speed_class(md),
        "last_reported_ago": time_ago(stats["last_reported_at"]),
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, page: int = 1):
    conn = db.get_conn()
    try:
        rows = conn.execute("SELECT id, ssid, name, lat, lng FROM venues").fetchall()
        venues = [_enrich_venue(conn, dict(r)) for r in rows]
    finally:
        conn.close()

    venues.sort(key=lambda v: v["median_download_mbps"] or 0, reverse=True)

    offset = (page - 1) * config.PAGE_SIZE
    page_venues = venues[offset : offset + config.PAGE_SIZE]
    has_next = len(venues) > offset + config.PAGE_SIZE

    return templates.TemplateResponse(
        request,
        "index.html",
        {"venues": page_venues, "page": page, "has_next": has_next, "nav_active": "browse"},
    )


@router.get("/venues/{venue_id}", response_class=HTMLResponse)
async def venue_detail(request: Request, venue_id: int, page: int = 1):
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()
        if not row:
            return templates.TemplateResponse(
                request, "404.html", {}, status_code=404
            )
        venue = dict(row)
        stats = db.venue_stats(conn, venue_id)

        offset = (page - 1) * 20
        reports_raw = conn.execute(
            "SELECT id, download_mbps, upload_mbps, ping_ms, submitted_at "
            "FROM speed_reports WHERE venue_id = ? ORDER BY submitted_at DESC "
            "LIMIT 21 OFFSET ?",
            (venue_id, offset),
        ).fetchall()
        has_next = len(reports_raw) > 20
        reports = [dict(r) for r in reports_raw[:20]]
        for r in reports:
            r["submitted_ago"] = time_ago(r["submitted_at"])
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "venue.html",
        {
            "venue": venue,
            "stats": stats,
            "speed_class": speed_class(stats["median_download_mbps"]),
            "reports": reports,
            "page": page,
            "has_next": has_next,
        },
    )


# --- JSON API ---

@router.get("/api/venues")
async def api_venues(request: Request, page: int = 1, bbox: Optional[str] = None):
    conn = db.get_conn()
    try:
        if bbox:
            try:
                west, south, east, north = map(float, bbox.split(","))
            except (ValueError, TypeError):
                return JSONResponse({"error": "Invalid bbox"}, status_code=400, headers=_CORS)
            rows = conn.execute(
                "SELECT id, ssid, name, lat, lng FROM venues "
                "WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?",
                (south, north, west, east),
            ).fetchall()
        else:
            offset = (page - 1) * config.PAGE_SIZE
            rows = conn.execute(
                "SELECT id, ssid, name, lat, lng FROM venues "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (config.PAGE_SIZE, offset),
            ).fetchall()
        venues = [_enrich_venue(conn, dict(r)) for r in rows]
    finally:
        conn.close()

    # Remove non-serialisable helpers before sending
    for v in venues:
        v.pop("last_reported_ago", None)
        v.pop("speed_class", None)

    return JSONResponse({"venues": venues, "page": page}, headers=_CORS)


@router.get("/api/venues/nearby")
async def api_venues_nearby(lat: float, lng: float, radius: int = config.NEARBY_RADIUS_DEFAULT_M):
    radius = max(config.NEARBY_RADIUS_MIN_M, min(radius, config.NEARBY_RADIUS_MAX_M))
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT id, ssid, name, lat, lng FROM venues "
            "WHERE lat IS NOT NULL AND lng IS NOT NULL"
        ).fetchall()
        nearby = []
        for v in rows:
            dist = db.haversine_m(lat, lng, v["lat"], v["lng"])
            if dist <= radius:
                stats = db.venue_stats(conn, v["id"])
                nearby.append(
                    {
                        "id": v["id"],
                        "ssid": v["ssid"],
                        "name": v["name"],
                        "lat": v["lat"],
                        "lng": v["lng"],
                        "distance_m": round(dist),
                        "median_download_mbps": stats["median_download_mbps"],
                    }
                )
        nearby.sort(key=lambda x: x["distance_m"])
    finally:
        conn.close()

    # Start with names from local wifibuddy venues
    suggestions = [
        {"name": v["name"], "distance_m": v["distance_m"]}
        for v in nearby
        if v["name"]
    ]

    # Include all named OSM places within the radius regardless of category
    osm = await _osm_nearby(lat, lng, radius)
    seen = {s["name"] for s in suggestions}
    for place in osm:
        if place["name"] not in seen:
            suggestions.append({"name": place["name"], "distance_m": place.get("distance_m")})

    # Build pins list for map display
    pins = []
    pins_names = set()
    for v in nearby:
        pin_name = v["name"] or v["ssid"]
        pins.append({
            "name": pin_name,
            "lat": v["lat"],
            "lng": v["lng"],
            "source": "wifibuddy",
            "median_download_mbps": v["median_download_mbps"],
        })
        pins_names.add(pin_name)
    for place in osm:
        if place["lat"] is not None and place["lng"] is not None and place["name"] not in pins_names:
            pins.append({
                "name": place["name"],
                "lat": place["lat"],
                "lng": place["lng"],
                "source": "osm",
                "median_download_mbps": None,
            })

    return JSONResponse(
        {"venues": nearby, "suggestions": suggestions, "pins": pins},
        headers=_CORS,
    )


async def _osm_nearby(lat: float, lng: float, radius: int) -> list[dict]:
    # Query both nodes and ways — most cafes/shops in OSM are ways (polygons), not nodes.
    # `out center` returns a center lat/lon for ways so we can compute distance.
    query = (
        f'[out:json][timeout:8];'
        f'(node["name"](around:{radius},{lat},{lng});'
        f'way["name"](around:{radius},{lat},{lng}););'
        f'out center;'
    )
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                timeout=8.0,
            )
        if resp.status_code != 200:
            return []
        results = []
        for el in resp.json().get("elements", []):
            name = el.get("tags", {}).get("name")
            if not name:
                continue
            # nodes expose lat/lon directly; ways expose them under "center"
            el_lat = el.get("lat") or (el.get("center") or {}).get("lat")
            el_lon = el.get("lon") or (el.get("center") or {}).get("lon")
            results.append({
                "name": name,
                "lat": el_lat,
                "lng": el_lon,
                "distance_m": round(db.haversine_m(lat, lng, el_lat, el_lon))
                if el_lat and el_lon
                else None,
            })
        return results
    except Exception:
        return []


@router.get("/api/venues/{venue_id}")
async def api_venue_detail(venue_id: int):
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()
        if not row:
            return JSONResponse(
                {"error": "Not found"}, status_code=404, headers=_CORS
            )
        stats = db.venue_stats(conn, venue_id)
        reports = conn.execute(
            "SELECT id, download_mbps, upload_mbps, ping_ms, submitted_at "
            "FROM speed_reports WHERE venue_id = ? ORDER BY submitted_at DESC LIMIT 20",
            (venue_id,),
        ).fetchall()
        result = {
            **dict(row),
            **stats,
            "reports": [dict(r) for r in reports],
        }
    finally:
        conn.close()
    return JSONResponse(result, headers=_CORS)
