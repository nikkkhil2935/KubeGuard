from fastapi import FastAPI
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import os, time, threading


app = FastAPI(title="KubeGuard Microservice")
START_TIME = time.time()


# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["endpoint", "pod", "namespace"],
)
CRASH_COUNT   = Counter("pod_crashes_total", "Total crashes triggered", ["pod", "namespace"])
UPTIME_GAUGE  = Gauge("service_uptime_seconds", "Service uptime in seconds")


POD_NAME  = os.environ.get("POD_NAME", "local-pod")
NAMESPACE = os.environ.get("NAMESPACE", "kubeguard")
VERSION   = os.environ.get("VERSION", "1.0.0")


def _uptime_loop():
    while True:
        UPTIME_GAUGE.set(time.time() - START_TIME)
        time.sleep(1)


threading.Thread(target=_uptime_loop, daemon=True).start()


@app.middleware("http")
async def count_requests(request, call_next):
    REQUEST_COUNT.labels(
        endpoint=request.url.path,
        pod=POD_NAME,
        namespace=NAMESPACE,
    ).inc()
    return await call_next(request)


@app.get("/health")
def health():
    return {"status":"ok","pod":POD_NAME,"uptime":round(time.time()-START_TIME,2)}


@app.get("/info")
def info():
    return {"version":VERSION,"pod":POD_NAME,"namespace":NAMESPACE}


@app.get("/crash")
def crash():
    CRASH_COUNT.labels(pod=POD_NAME, namespace=NAMESPACE).inc()
    print(f"CRASH triggered on {POD_NAME}", flush=True)
    os._exit(1)


@app.get("/stress")
def stress():
    end = time.time() + 10
    while time.time() < end:
        _ = sum(i*i for i in range(10000))
    return {"status":"stress complete","pod":POD_NAME}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
