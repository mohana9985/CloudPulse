# Labels use route templates (or 'unmatched'), never raw URLs or IDs, to keep
# cardinality low.

import threading
import time

from prometheus_client import Counter, Gauge, Histogram, Info

APP_START_TIME = time.time()

HTTP_REQUESTS_TOTAL = Counter(
    "cloudpulse_http_requests_total",
    "Total HTTP requests processed, by method, endpoint and status code.",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "cloudpulse_http_request_duration_seconds",
    "HTTP request duration in seconds, by method and endpoint.",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_ERRORS_TOTAL = Counter(
    "cloudpulse_http_errors_total",
    "Total HTTP responses with status >= 400, by method, endpoint and status code.",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "cloudpulse_http_requests_in_progress",
    "Number of HTTP requests currently being processed.",
)

APP_UPTIME_SECONDS = Gauge(
    "cloudpulse_app_uptime_seconds",
    "Seconds since the backend process started.",
)
APP_UPTIME_SECONDS.set_function(lambda: time.time() - APP_START_TIME)

APP_START_TIME_SECONDS = Gauge(
    "cloudpulse_app_start_time_seconds",
    "Unix timestamp when the backend process started.",
)
APP_START_TIME_SECONDS.set(APP_START_TIME)

APP_INFO = Info("cloudpulse_app", "Static information about the backend service.")

ORDERS_CREATED_TOTAL = Counter(
    "cloudpulse_orders_created_total",
    "Total demonstration orders created successfully.",
)

CONTACT_MESSAGES_TOTAL = Counter(
    "cloudpulse_contact_messages_total",
    "Total contact form submissions stored.",
)


class _RequestCounter:
    def __init__(self) -> None:
        self._value = 0
        self._lock = threading.Lock()

    def increment(self) -> None:
        with self._lock:
            self._value += 1

    @property
    def value(self) -> int:
        with self._lock:
            return self._value


TOTAL_REQUESTS = _RequestCounter()


def uptime_seconds() -> float:
    return time.time() - APP_START_TIME


def _endpoint_label(scope: dict) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if path else "unmatched"


class PrometheusMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        status_holder = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        HTTP_REQUESTS_IN_PROGRESS.inc()
        start = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status_holder["code"] = 500
            raise
        finally:
            duration = time.perf_counter() - start
            HTTP_REQUESTS_IN_PROGRESS.dec()

            endpoint = _endpoint_label(scope)
            status_code = str(status_holder["code"])

            HTTP_REQUESTS_TOTAL.labels(method, endpoint, status_code).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method, endpoint).observe(duration)
            if status_holder["code"] >= 400:
                HTTP_ERRORS_TOTAL.labels(method, endpoint, status_code).inc()
            if scope.get("path", "").startswith("/api"):
                TOTAL_REQUESTS.increment()
