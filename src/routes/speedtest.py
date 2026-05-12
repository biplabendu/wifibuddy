import os

from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter(prefix="/api/speedtest")

_NO_CACHE = {"Cache-Control": "no-store, no-cache", "Pragma": "no-cache"}


@router.get("/ping")
async def ping():
    return Response(b"\x00", media_type="application/octet-stream", headers=_NO_CACHE)


@router.get("/download")
async def download(bytes: int = 10_485_760):
    size = min(max(bytes, 1_024), 20 * 1_048_576)  # clamp 1 KB – 20 MB
    return Response(
        content=os.urandom(size),
        media_type="application/octet-stream",
        headers=_NO_CACHE,
    )


@router.post("/upload")
async def upload(request: Request):
    await request.body()  # consume and discard
    return Response(b"", status_code=200, headers=_NO_CACHE)
