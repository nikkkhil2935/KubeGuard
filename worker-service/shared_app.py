from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
import logging
import os
import threading
import time


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SERVICE_NAME = os.environ.get("SERVICE_NAME", "unknown")
POD_NAME = os.environ.get("POD_NAME", "local")
NAMESPACE = os.environ.get("NAMESPACE", "kubeguard")
VERSION = os.environ.get("VERSION", "2.0.0")
START_TIME = time.time()

REQ_COUNTER = Counter("http_requests_total", "Requests", ["service", "endpoint", "status"])
CRASH_CTR = Counter("pod_crashes_total", "Crashes", ["service"])
ERR_COUNTER = Counter("http_errors_total", "Errors", ["service"])
REQ_LATENCY = Histogram("http_request_duration_seconds", "Latency", ["service", "endpoint"])
UPTIME_GAUGE = Gauge("service_uptime_seconds", "Uptime", ["service"])
MEMORY_GAUGE = Gauge("service_memory_mb", "Memory MB", ["service"])


def start_background_metrics():
    import psutil

    def _loop():
        while True:
            UPTIME_GAUGE.labels(service=SERVICE_NAME).set(time.time() - START_TIME)
            proc = psutil.Process()
            MEMORY_GAUGE.labels(service=SERVICE_NAME).set(proc.memory_info().rss / 1024 / 1024)
            time.sleep(5)

    threading.Thread(target=_loop, daemon=True).start()


def create_app(name: str) -> FastAPI:
    app = FastAPI(title=f"KubeGuard {name}")

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        endpoint = request.url.path
        timer = REQ_LATENCY.labels(service=SERVICE_NAME, endpoint=endpoint).time()
        timer.__enter__()
        status_code = "500"
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        except Exception:
            ERR_COUNTER.labels(service=SERVICE_NAME).inc()
            raise
        finally:
            timer.__exit__(None, None, None)
            REQ_COUNTER.labels(service=SERVICE_NAME, endpoint=endpoint, status=status_code).inc()

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "pod": POD_NAME,
            "uptime": round(time.time() - START_TIME, 2),
        }

    @app.get("/ready")
    def ready():
        return {"ready": True, "service": SERVICE_NAME}

    @app.get("/info")
    def info():
        return {
            "service": SERVICE_NAME,
            "version": VERSION,
            "pod": POD_NAME,
            "namespace": NAMESPACE,
        }

    @app.get("/crash")
    def crash():
        CRASH_CTR.labels(service=SERVICE_NAME).inc()
        log.error("CRASH endpoint hit on %s", POD_NAME)
        os._exit(1)

    @app.get("/stress")
    def stress():
        end = time.time() + 10
        while time.time() < end:
            _ = sum(i * i for i in range(50000))
        return {"status": "stress complete", "service": SERVICE_NAME}

    @app.get("/oom")
    def oom():
        data = []
        try:
            while True:
                data.append("x" * 1024 * 1024)
        except MemoryError:
            os._exit(1)

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
