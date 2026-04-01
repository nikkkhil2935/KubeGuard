#!/usr/bin/env python3
"""KubeGuard Dashboard - Real-time pod monitoring UI with Prometheus integration."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import subprocess
import json
import asyncio
import requests
import os
import time
from datetime import datetime
from collections import deque
from pathlib import Path

app = FastAPI(title="KubeGuard Dashboard")

NAMESPACE = "kubeguard"
SERVICE_URL = "http://localhost:30080"
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:30090")
CRASH_REASONS = {"CrashLoopBackOff", "Error", "OOMKilled", "ImagePullBackOff"}


# ============== Prometheus Integration ==============

def query_prometheus(query: str) -> dict:
    """Query Prometheus instant query endpoint."""
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=3
        )
        data = r.json()
        if data.get("status") == "success":
            return {"success": True, "data": data["data"]["result"]}
    except Exception:
        pass
    return {"success": False, "data": []}


def query_prometheus_range(query: str, start: int, end: int, step: str = "15s") -> dict:
    """Query Prometheus range query endpoint for time-series data."""
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "step": step},
            timeout=5
        )
        data = r.json()
        if data.get("status") == "success":
            return {"success": True, "data": data["data"]["result"]}
    except Exception:
        pass
    return {"success": False, "data": []}


def calculate_risk_score(restarts: float) -> tuple:
    """Calculate risk score based on restart count."""
    score, reasons = 0, []
    if restarts > 5:
        score += 30
        reasons.append(f"High restarts ({int(restarts)})")
    if restarts > 10:
        score += 40
        reasons.append("Critical level")
    if restarts > 0:
        score += 10
        reasons.append("Has restarted")
    return min(score, 100), reasons

# Event history (last 50 events)
events = deque(maxlen=50)

# Pod state cache for detecting changes
pod_cache = {}


def get_pods():
    """Fetch pods from Kubernetes."""
    r = subprocess.run(
        ["kubectl", "get", "pods", "-n", NAMESPACE, "-o", "json"],
        capture_output=True, text=True
    )
    try:
        return json.loads(r.stdout).get("items", [])
    except json.JSONDecodeError:
        return []


def parse_pod(pod):
    """Extract status info from pod object."""
    name = pod["metadata"]["name"]
    cs = pod["status"].get("containerStatuses", [])

    if not cs:
        return {"name": name, "status": "Pending", "restarts": 0, "ready": False, "message": None}

    c = cs[0]
    restarts = c.get("restartCount", 0)
    state = c.get("state", {})

    if "waiting" in state:
        return {
            "name": name,
            "status": state["waiting"].get("reason", "Unknown"),
            "restarts": restarts,
            "ready": False,
            "message": state["waiting"].get("message", "")
        }

    if "running" in state:
        return {
            "name": name,
            "status": "Running",
            "restarts": restarts,
            "ready": c.get("ready", False),
            "message": None
        }

    return {"name": name, "status": "Terminated", "restarts": restarts, "ready": False, "message": None}


def detect_events(pods_data):
    """Compare current state with cache and emit crash/recovery events."""
    global pod_cache

    for pod in pods_data:
        name = pod["name"]
        prev = pod_cache.get(name, {"status": "Running", "restarts": 0})

        crashed = pod["status"] in CRASH_REASONS
        was_crashed = prev.get("status", "Running") in CRASH_REASONS

        if crashed and not was_crashed:
            events.appendleft({
                "type": "crash",
                "pod": name,
                "status": pod["status"],
                "restarts": pod["restarts"],
                "time": datetime.now().isoformat()
            })
        elif not crashed and was_crashed and pod["status"] == "Running":
            events.appendleft({
                "type": "recovery",
                "pod": name,
                "status": pod["status"],
                "restarts": pod["restarts"],
                "time": datetime.now().isoformat()
            })

        pod_cache[name] = {"status": pod["status"], "restarts": pod["restarts"]}


class ConnectionManager:
    """Manage WebSocket connections."""
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        for ws in self.active:
            try:
                await ws.send_json(data)
            except:
                pass


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time pod updates."""
    await manager.connect(ws)
    try:
        while True:
            pods = [parse_pod(p) for p in get_pods()]
            detect_events(pods)
            await ws.send_json({
                "pods": pods,
                "events": list(events),
                "timestamp": datetime.now().isoformat()
            })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


@app.post("/api/crash")
async def trigger_crash():
    """Trigger a crash on the microservice."""
    events.appendleft({
        "type": "manual",
        "pod": "user-triggered",
        "status": "Crash Requested",
        "restarts": 0,
        "time": datetime.now().isoformat()
    })
    try:
        requests.get(f"{SERVICE_URL}/crash", timeout=2)
    except:
        pass  # Pod crashes, connection drops - expected
    return {"status": "crash triggered"}


@app.get("/api/pods")
async def get_pod_status():
    """REST endpoint for current pod status."""
    return [parse_pod(p) for p in get_pods()]


# ============== Prometheus Metrics Endpoints ==============

@app.get("/api/metrics/request-rate")
async def get_request_rate():
    """Get request rate over last 10 minutes."""
    end = int(time.time())
    start = end - 600
    result = query_prometheus_range(
        'sum(rate(http_requests_total[1m]))',
        start, end, "15s"
    )
    return result


@app.get("/api/metrics/restart-trends")
async def get_restart_trends():
    """Get restart counts per pod."""
    result = query_prometheus(
        f'kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}"}}'
    )
    return result


@app.get("/api/metrics/uptime")
async def get_uptime():
    """Get uptime per pod."""
    result = query_prometheus('service_uptime_seconds')
    return result


@app.get("/api/metrics/health-summary")
async def get_health_summary():
    """Get overall system health metrics."""
    total_requests = query_prometheus('sum(http_requests_total)')
    request_rate = query_prometheus('sum(rate(http_requests_total[1m]))')
    total_restarts = query_prometheus(
        f'sum(kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}"}})'
    )
    total_crashes = query_prometheus('sum(pod_crashes_total)')
    avg_uptime = query_prometheus('avg(service_uptime_seconds)')

    def extract_sum(result: dict) -> float:
        if result["success"] and result["data"]:
            return sum(float(item["value"][1]) for item in result["data"])
        return 0.0

    explicit_crashes = extract_sum(total_crashes)
    inferred_crashes = extract_sum(total_restarts)
    effective_crashes = max(explicit_crashes, inferred_crashes)

    return {
        "success": True,
        "prometheus_available": total_requests["success"],
        "total_requests": extract_sum(total_requests),
        "request_rate_per_sec": extract_sum(request_rate),
        "total_restarts": inferred_crashes,
        "total_crashes": effective_crashes,
        "avg_uptime": extract_sum(avg_uptime)
    }


@app.get("/api/metrics/risk-scores")
async def get_risk_scores():
    """Calculate risk scores for all pods."""
    pods = [parse_pod(p) for p in get_pods()]
    scores = []

    for pod in pods:
        score, reasons = calculate_risk_score(pod["restarts"])
        if pod["status"] in CRASH_REASONS:
            score = min(score + 40, 100)
            reasons.append(f"Currently {pod['status']}")
        scores.append({
            "pod": pod["name"],
            "score": score,
            "reasons": reasons,
            "status": pod["status"]
        })

    return {"success": True, "scores": scores}


# Serve static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
async def root():
    """Serve the dashboard HTML."""
    return FileResponse(str(static_path / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
