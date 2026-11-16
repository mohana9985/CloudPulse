# Failure demo: POST /admin/crash kills this process and keeps the port closed for N seconds.
# Safety: off unless ENABLE_CHAOS=true; the path is outside /api/ so Nginx never forwards it
# (only the gateway on the private network can call it); proxied requests are refused.
import asyncio
import logging
import os
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import settings

router = APIRouter(prefix="/admin", tags=["Failure demo"], include_in_schema=False)
logger = logging.getLogger("cloudpulse.chaos")

MAX_DOWN_SECONDS = 300


def marker_path() -> Path:
    return Path(os.getenv("CHAOS_MARKER", "/tmp/cloudpulse-down-until"))


def _exit_process() -> None:
    os._exit(1)


@router.post("/crash")
def crash(request: Request, down_seconds: float = Query(10, ge=0, le=MAX_DOWN_SECONDS)):
    if not settings.enable_chaos:
        raise HTTPException(status_code=403, detail="Failure demo disabled (ENABLE_CHAOS=false)")
    if request.headers.get("x-forwarded-for"):
        raise HTTPException(status_code=403, detail="Not allowed through a proxy")
    until = time.time() + down_seconds
    marker_path().write_text(f"{until:.3f}")
    logger.warning("CRASH requested: exiting now, staying down for %.0f s", down_seconds)
    threading.Timer(0.2, _exit_process).start()   # let this response go out first
    return {"service": settings.service_name, "crashing": True, "down_seconds": down_seconds,
            "down_until_unix": round(until, 3)}


async def wait_if_crashed() -> float:
    path = marker_path()
    try:
        until = float(path.read_text().strip())
    except (OSError, ValueError):
        return 0.0
    path.unlink(missing_ok=True)
    remaining = until - time.time()
    if remaining <= 0:
        return 0.0
    remaining = min(remaining, MAX_DOWN_SECONDS)
    logger.warning("Restarted after a demo crash: staying down %.1f s more", remaining)
    await asyncio.sleep(remaining)
    return remaining
