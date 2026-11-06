import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import contact, health, monitoring, orders, products
from app.core.config import settings
from app.core.metrics import APP_INFO, PrometheusMiddleware
from app.database.connection import SessionLocal, init_db
from app.database.seed import seed_products

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("cloudpulse")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting %s v%s (%s)", settings.app_name, settings.app_version, settings.environment)
    init_db()
    if settings.seed_on_startup:
        with SessionLocal() as db:
            seed_products(db)
    APP_INFO.info({"version": settings.app_version, "environment": settings.environment})
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend API for CloudPulse Store, a dummy e-commerce site used to generate "
        "realistic traffic for the CloudPulse monitoring project. Orders are demonstrations only."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS is only relevant for the Vite dev server; behind Nginx all calls are same-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.add_middleware(PrometheusMiddleware)

for router in (health.router, products.router, orders.router, contact.router, monitoring.router):
    app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    return {"service": settings.service_name, "docs": "/api/docs", "health": "/api/health"}
