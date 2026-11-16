# CloudPulse website workload generator. Sends shopper API requests to the store's Nginx
# entry point (TARGET_URL), so every request is scheduled by the gateway like a browser click.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=60

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser loadgen ./loadgen

USER appuser
EXPOSE 8095
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8095/loadgen/health', timeout=4).status == 200 else 1)"

# One process: the running workload and its statistics live in one event loop.
CMD ["uvicorn", "loadgen.app:app", "--host", "0.0.0.0", "--port", "8095", "--log-level", "warning"]
