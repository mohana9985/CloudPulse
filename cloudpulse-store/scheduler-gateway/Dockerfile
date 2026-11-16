# Build context = monorepo root (see cloudpulse-store/compose.yaml), because the gateway
# imports the scheduling algorithms from cloudpulse-scheduler/src unchanged.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=60

WORKDIR /app
COPY cloudpulse-store/scheduler-gateway/requirements.txt .
RUN pip install -r requirements.txt && useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser cloudpulse-scheduler/src ./src
COPY --chown=appuser:appuser cloudpulse-store/scheduler-gateway/gateway ./gateway

USER appuser
EXPOSE 8090
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/gateway/health', timeout=4).status == 200 else 1)"

# One process: the scheduler state (mirror workers, queues) must live in a single event loop.
CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8090", "--log-level", "warning"]
