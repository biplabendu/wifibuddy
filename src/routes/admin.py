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
    async with db.get_client() as client:
        rs = await client.execute(
            "SELECT id FROM speed_reports WHERE id = ?", [report_id]
        )
        if not rs.rows:
            raise HTTPException(status_code=404)
        await client.execute("DELETE FROM speed_reports WHERE id = ?", [report_id])
    return Response(status_code=204)


@router.delete("/venues/{venue_id}", status_code=204)
async def delete_venue(
    venue_id: int, _: HTTPBasicCredentials = Depends(_require_admin)
):
    async with db.get_client() as client:
        rs = await client.execute(
            "SELECT id FROM venues WHERE id = ?", [venue_id]
        )
        if not rs.rows:
            raise HTTPException(status_code=404)
        await client.execute("DELETE FROM speed_reports WHERE venue_id = ?", [venue_id])
        await client.execute("DELETE FROM venues WHERE id = ?", [venue_id])
    return Response(status_code=204)


@router.get("/reports")
async def list_reports(
    _: HTTPBasicCredentials = Depends(_require_admin),
    limit: int = 50,
    offset: int = 0,
):
    async with db.get_client() as client:
        rs = await client.execute(
            "SELECT r.id, r.venue_id, v.ssid, r.download_mbps, r.upload_mbps, "
            "r.ping_ms, r.submitted_at "
            "FROM speed_reports r JOIN venues v ON v.id = r.venue_id "
            "ORDER BY r.submitted_at DESC LIMIT ? OFFSET ?",
            [limit, offset],
        )
        reports = [dict(zip(rs.columns, row)) for row in rs.rows]
    return JSONResponse({"reports": reports})
