from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.connection import check_db_connection, get_db
from app.services.product_service import count_products

router = APIRouter(prefix="/api", tags=["Health"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.app_version,
        "timestamp": _now(),
    }


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    checks = {"database": "ok" if check_db_connection() else "unavailable"}
    product_count = 0
    if checks["database"] == "ok":
        try:
            product_count = count_products(db)
            checks["products_seeded"] = "ok" if product_count > 0 else "empty"
        except Exception:
            checks["database"] = "unavailable"

    is_ready = checks["database"] == "ok"
    body = {
        "status": "ready" if is_ready else "not_ready",
        "service": settings.service_name,
        "checks": checks,
        "product_count": product_count,
        "timestamp": _now(),
    }
    return JSONResponse(status_code=200 if is_ready else 503, content=body)
