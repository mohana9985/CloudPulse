from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import APP_START_TIME, TOTAL_REQUESTS, uptime_seconds
from app.database.connection import get_db
from app.services.contact_service import count_contact_messages
from app.services.order_service import count_orders
from app.services.product_service import count_products

router = APIRouter(prefix="/api", tags=["Monitoring"])


@router.get("/metrics", include_in_schema=True)
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    # Must never expose secrets or configuration values.
    uptime = uptime_seconds()
    return {
        "service": settings.service_name,
        "version": settings.app_version,
        "total_api_requests": TOTAL_REQUESTS.value,
        "total_products": count_products(db),
        "total_orders": count_orders(db),
        "total_contact_messages": count_contact_messages(db),
        "uptime_seconds": round(uptime, 2),
        "started_at": datetime.fromtimestamp(APP_START_TIME, tz=timezone.utc).isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
