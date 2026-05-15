from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

import src.config as config
import src.db as db

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/submit", response_class=HTMLResponse)
async def submit_form(
    request: Request,
    ssid: str = "",
    venue_id: Optional[int] = None,
):
    return templates.TemplateResponse(
        request,
        "submit.html",
        {
            "ssid": ssid,
            "venue_id": venue_id,
            "errors": [],
            "nav_active": "report",
            "radius_default": config.NEARBY_RADIUS_DEFAULT_M,
            "radius_min":     config.NEARBY_RADIUS_MIN_M,
            "radius_max":     config.NEARBY_RADIUS_MAX_M,
            "radius_step":    config.NEARBY_RADIUS_STEP_M,
        },
    )


@router.post("/reports")
async def submit_report(request: Request):
    form = await request.form()

    if form.get("honey", ""):
        return Response(status_code=200)

    _radius_ctx = {
        "radius_default": config.NEARBY_RADIUS_DEFAULT_M,
        "radius_min":     config.NEARBY_RADIUS_MIN_M,
        "radius_max":     config.NEARBY_RADIUS_MAX_M,
        "radius_step":    config.NEARBY_RADIUS_STEP_M,
    }

    ssid = (form.get("ssid") or "").strip()
    raw_download = form.get("download_mbps", "")
    raw_upload = form.get("upload_mbps", "")
    raw_ping = form.get("ping_ms", "")
    raw_lat = form.get("lat", "")
    raw_lng = form.get("lng", "")
    name = (form.get("name") or "").strip() or None
    if name is None and ssid:
        name = ssid

    errors = []

    if not ssid or len(ssid) > 64:
        errors.append("Network name (SSID) is required and must be 64 characters or fewer.")

    download_mbps: Optional[float] = None
    try:
        download_mbps = float(raw_download)
        if not (0 < download_mbps < 10_000):
            errors.append("Download speed must be greater than 0 and less than 10,000 Mbps.")
    except (ValueError, TypeError):
        errors.append("Download speed is required and must be a number.")

    upload_mbps: Optional[float] = None
    try:
        upload_mbps = float(raw_upload)
        if not (0 < upload_mbps < 10_000):
            errors.append("Upload speed must be greater than 0 and less than 10,000 Mbps.")
    except (ValueError, TypeError):
        errors.append("Upload speed is required and must be a number.")

    ping_ms: Optional[float] = None
    if raw_ping:
        try:
            ping_ms = float(raw_ping)
            if not (0 < ping_ms < 60_000):
                errors.append("Ping must be between 0 and 60,000 ms.")
        except (ValueError, TypeError):
            errors.append("Ping must be a number.")

    lat: Optional[float] = None
    if raw_lat:
        try:
            lat = float(raw_lat)
            if not (-90 <= lat <= 90):
                errors.append("Invalid latitude.")
        except (ValueError, TypeError):
            errors.append("Latitude must be a number.")

    lng: Optional[float] = None
    if raw_lng:
        try:
            lng = float(raw_lng)
            if not (-180 <= lng <= 180):
                errors.append("Invalid longitude.")
        except (ValueError, TypeError):
            errors.append("Longitude must be a number.")

    if name and len(name) > 128:
        errors.append("Venue name must be 128 characters or fewer.")

    if errors:
        return templates.TemplateResponse(
            request,
            "submit.html",
            {"ssid": ssid, "errors": errors, "nav_active": "report", **_radius_ctx},
            status_code=422,
        )

    client_ip = request.client.host if request.client else "unknown"

    async with db.get_client() as client:
        venue_id = await db.find_matching_venue(client, ssid, lat, lng)

        if venue_id is not None:
            if await db.rate_limit_count(client, client_ip, venue_id, config.RATE_LIMIT_HOURS) >= 1:
                return templates.TemplateResponse(
                    request,
                    "submit.html",
                    {
                        "ssid": ssid,
                        "errors": [
                            "You've already submitted a report for this network recently. "
                            "Try again in an hour."
                        ],
                        "nav_active": "report",
                        **_radius_ctx,
                    },
                    status_code=429,
                )

        if venue_id is None:
            rs = await client.execute(
                "INSERT INTO venues (ssid, name, lat, lng) VALUES (?, ?, ?, ?)",
                [ssid, name, lat, lng],
            )
            venue_id = rs.last_insert_rowid

        await client.execute(
            "INSERT INTO speed_reports "
            "(venue_id, download_mbps, upload_mbps, ping_ms, submitter_ip) "
            "VALUES (?, ?, ?, ?, ?)",
            [venue_id, download_mbps, upload_mbps, ping_ms, client_ip],
        )

    return RedirectResponse(url=f"/venues/{venue_id}", status_code=303)
