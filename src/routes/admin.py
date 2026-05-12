import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import src.config as config
import src.db as db

router = APIRouter(prefix="/admin")
_security = HTTPBasic()


def _require_admin(credentials: HTTPBasicCredentials = Depends(_security)):
    ok_user = secrets.compare_digest(
        credentials.username.encode(), config.ADMIN_USERNAME.encode()
    )
    ok_pass = secrets.compare_digest(
        credentials.password.encode(), config.ADMIN_PASSWORD.encode()
    )
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
    return credentials


@router.delete("/reports/{report_id}", status_code=204)
async def delete_report(
    report_id: int, _: HTTPBasicCredentials = Depends(_require_admin)
):
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM speed_reports WHERE id = ?", (report_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404)
        conn.execute("DELETE FROM speed_reports WHERE id = ?", (report_id,))
        conn.commit()
    finally:
        conn.close()
    return Response(status_code=204)


@router.delete("/venues/{venue_id}", status_code=204)
async def delete_venue(
    venue_id: int, _: HTTPBasicCredentials = Depends(_require_admin)
):
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM venues WHERE id = ?", (venue_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404)
        conn.execute("DELETE FROM venues WHERE id = ?", (venue_id,))
        conn.commit()
    finally:
        conn.close()
    return Response(status_code=204)


@router.get("/reports")
async def list_reports(
    _: HTTPBasicCredentials = Depends(_require_admin),
    limit: int = 50,
    offset: int = 0,
):
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT r.id, r.venue_id, v.ssid, r.download_mbps, r.upload_mbps, "
            "r.ping_ms, r.submitted_at "
            "FROM speed_reports r JOIN venues v ON v.id = r.venue_id "
            "ORDER BY r.submitted_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        reports = [dict(r) for r in rows]
    finally:
        conn.close()
    return JSONResponse({"reports": reports})
