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
        {"venues": page_venues, "page": page, "has_next": has_next, "nav_active": "list"},
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
async def api_venues_nearby(lat: float, lng: float, radius: int = 200):
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
                nearby.append(
                    {
                        "id": v["id"],
                        "ssid": v["ssid"],
                        "name": v["name"],
                        "lat": v["lat"],
                        "lng": v["lng"],
                        "distance_m": round(dist),
                    }
                )
        nearby.sort(key=lambda x: x["distance_m"])
        nearby = nearby[:5]
    finally:
        conn.close()

    # Start with names from local wifibuddy venues
    suggestions = [
        {"name": v["name"], "distance_m": v["distance_m"]}
        for v in nearby
        if v["name"]
    ]

    # Supplement with OSM places when local results are sparse
    if len(suggestions) < 3:
        osm = await _osm_nearby(lat, lng, radius)
        seen = {s["name"] for s in suggestions}
        for place in osm:
            if place["name"] not in seen:
                suggestions.append({"name": place["name"], "distance_m": place.get("distance_m")})

    return JSONResponse(
        {"venues": nearby, "suggestions": suggestions[:8]},
        headers=_CORS,
    )


async def _osm_nearby(lat: float, lng: float, radius: int) -> list[dict]:
    query = (
        f"[out:json][timeout:8];"
        f'node["amenity"~"cafe|restaurant|library|coworking"](around:{radius},{lat},{lng});'
        f"out 8;"
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
        return [
            {
                "name": el["tags"]["name"],
                "lat": el.get("lat"),
                "lng": el.get("lon"),
                "distance_m": round(db.haversine_m(lat, lng, el["lat"], el["lon"]))
                if el.get("lat") and el.get("lon")
                else None,
            }
            for el in resp.json().get("elements", [])
            if el.get("tags", {}).get("name")
        ]
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
