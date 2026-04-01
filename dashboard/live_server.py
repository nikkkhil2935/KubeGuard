#!/usr/bin/env python3
"""KubeGuard Unified Live Dashboard - Professional all-in-one ops view on port 9001."""
import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from kubernetes import client, config


import socketio

ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ROOT_ENV)

NAMESPACE = os.getenv("NAMESPACE", "kubeguard")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:30300")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:30081")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "9001"))

DISCORD_WEBHOOK_URL = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip()
SLACK_WEBHOOK_URL = (os.getenv("SLACK_WEBHOOK_URL") or "").strip()
SLACK_BOT_TOKEN = (os.getenv("SLACK_BOT_TOKEN") or "").strip()
SLACK_CHANNEL_ID = (os.getenv("SLACK_CHANNEL_ID") or "").strip()
SLACK_APP_ID = (os.getenv("SLACK_APP_ID") or "").strip()

CRASH_REASONS = {"CrashLoopBackOff", "Error", "OOMKilled", "ImagePullBackOff"}


def _env_float(name: str, default: float) -> float:
  value = os.getenv(name)
  if not value:
    return default
  try:
    return float(value)
  except ValueError:
    return default


PROMETHEUS_QUERY_TIMEOUT = _env_float("PROMETHEUS_QUERY_TIMEOUT", 1.2)
INTEGRATION_CHECK_TIMEOUT = _env_float("INTEGRATION_CHECK_TIMEOUT", 1.0)
K8S_LIST_TIMEOUT = _env_float("K8S_LIST_TIMEOUT", 2.0)

try:
    config.load_incluster_config()
except Exception:
    config.load_kube_config()

v1 = client.CoreV1Api()
app = FastAPI(title="KubeGuard Unified Dashboard")

# Add CORS middleware for frontend connections
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _query_prometheus(query: str) -> float:
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
      timeout=PROMETHEUS_QUERY_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            return 0.0
        results = payload.get("data", {}).get("result", [])
        return sum(float(item["value"][1]) for item in results)
    except Exception:
        return 0.0


def _prometheus_up() -> bool:
    try:
        response = requests.get(f"{PROMETHEUS_URL}/-/ready", timeout=INTEGRATION_CHECK_TIMEOUT)
        return response.status_code == 200
    except Exception:
        return False


def _grafana_up() -> bool:
    try:
        response = requests.get(f"{GRAFANA_URL}/api/health", timeout=INTEGRATION_CHECK_TIMEOUT)
        return response.status_code == 200
    except Exception:
        return False


def _get_cluster_state():
    try:
        pods = v1.list_namespaced_pod(NAMESPACE, _request_timeout=K8S_LIST_TIMEOUT).items
    except Exception:
        return []

    state = []
    for pod in pods:
        cs = (pod.status.container_statuses or [None])[0]
        restarts = cs.restart_count if cs else 0
        ready = cs.ready if cs else False
        phase = pod.status.phase or "Unknown"
        reason = ""
        if cs and cs.state and cs.state.waiting:
            reason = cs.state.waiting.reason or ""
        elif cs and cs.state and cs.state.terminated:
            reason = cs.state.terminated.reason or ""

        state.append(
            {
                "name": pod.metadata.name,
                "phase": phase,
                "ready": ready,
                "restarts": restarts,
                "reason": reason,
                "service": pod.metadata.labels.get("component", pod.metadata.labels.get("app", "?")),
            }
        )
    return state


def _summary(pods):
    total = len(pods)
    running = sum(1 for p in pods if p["ready"])
    crashed = sum(1 for p in pods if p["reason"] in CRASH_REASONS)
    restarts = sum(p["restarts"] for p in pods)

    metric_queries = [
        "sum(rate(http_requests_total[1m]))",
        "sum(pod_crashes_total)",
        'sum(ALERTS{alertstate="firing"})',
    ]

    with ThreadPoolExecutor(max_workers=3) as pool:
        req_rate_raw, crash_counter, alerts_firing = list(pool.map(_query_prometheus, metric_queries))

    req_rate_min = req_rate_raw * 60
    return {
        "total": total,
        "running": running,
        "crashed": crashed,
        "restarts": restarts,
        "request_rate_min": req_rate_min,
        "crash_counter": max(crash_counter, float(restarts)),
        "alerts_firing": alerts_firing,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _send_discord_test():
    if not DISCORD_WEBHOOK_URL:
        raise HTTPException(status_code=400, detail="DISCORD_WEBHOOK_URL is not configured")

    payload = {
        "username": "KubeGuard Unified Dashboard",
        "embeds": [
            {
                "title": "Discord Integration Test",
                "description": "Dashboard test alert sent successfully.",
                "color": 65280,
                "fields": [
                    {"name": "Namespace", "value": f"`{NAMESPACE}`", "inline": True},
                    {"name": "Source", "value": "Dashboard", "inline": True},
                ],
            }
        ],
    }
    response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    if response.status_code < 200 or response.status_code >= 300:
        raise HTTPException(status_code=502, detail=f"Discord HTTP {response.status_code}: {response.text[:200]}")


def _send_slack_test():
    text = f":white_check_mark: KubeGuard dashboard test alert from namespace {NAMESPACE}."

    if SLACK_WEBHOOK_URL:
        response = requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=5)
        if response.status_code < 200 or response.status_code >= 300:
            raise HTTPException(status_code=502, detail=f"Slack webhook HTTP {response.status_code}: {response.text[:200]}")
        return

    if SLACK_BOT_TOKEN and SLACK_CHANNEL_ID:
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={"channel": SLACK_CHANNEL_ID, "text": text},
            timeout=5,
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise HTTPException(status_code=502, detail=f"Slack API HTTP {response.status_code}: {response.text[:200]}")
        payload = response.json()
        if not payload.get("ok"):
            raise HTTPException(status_code=502, detail=f"Slack API error: {payload}")
        return

    raise HTTPException(
        status_code=400,
        detail="Slack runtime notifier not configured. Set SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID.",
    )


@app.get("/api/integrations/status")
def integrations_status():
    with ThreadPoolExecutor(max_workers=2) as pool:
        prometheus_future = pool.submit(_prometheus_up)
        grafana_future = pool.submit(_grafana_up)

    return {
        "prometheus_up": prometheus_future.result(),
        "grafana_up": grafana_future.result(),
        "discord_configured": bool(DISCORD_WEBHOOK_URL),
        "slack_app_configured": bool(SLACK_APP_ID),
        "slack_runtime_configured": bool(SLACK_WEBHOOK_URL or (SLACK_BOT_TOKEN and SLACK_CHANNEL_ID)),
        "prometheus_url": PROMETHEUS_URL,
        "grafana_url": GRAFANA_URL,
    }


@app.get("/api/summary")
def api_summary():
    pods = _get_cluster_state()
    return {"pods": pods, "summary": _summary(pods)}


@app.post("/api/actions/crash")
async def api_trigger_crash():
    await sio.emit("log", {"time": datetime.now().strftime("%H:%M:%S"), "level": "warning", "message": "Triggering crash via API gateway..."})
    try:
        requests.get(f"{GATEWAY_URL}/crash", timeout=3)
    except Exception:
        pass
    return {"ok": True, "message": "Crash triggered"}


@app.post("/api/integrations/test-discord")
async def api_test_discord():
    await sio.emit("log", {"time": datetime.now().strftime("%H:%M:%S"), "level": "info", "message": "Dispatching Discord test webhook..."})
    _send_discord_test()
    return {"ok": True, "message": "Discord test sent"}


@app.post("/api/integrations/test-slack")
async def api_test_slack():
    await sio.emit("log", {"time": datetime.now().strftime("%H:%M:%S"), "level": "info", "message": "Dispatching Slack test webhook..."})
    _send_slack_test()
    return {"ok": True, "message": "Slack test sent"}


DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>KubeGuard Unified Ops Center</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    :root {
      --bg: #f3f7fc;
      --surface: #ffffff;
      --surface-alt: #f8fbff;
      --border: #dbe7f3;
      --text: #0f172a;
      --muted: #64748b;
      --brand: #0ea5e9;
      --brand-strong: #0369a1;
      --good: #16a34a;
      --warn: #d97706;
      --bad: #dc2626;
      --shadow: 0 12px 30px rgba(14, 31, 53, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: 'Plus Jakarta Sans', sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 0% 0%, #dff2ff 0%, transparent 32%),
        radial-gradient(circle at 100% 8%, #e6f4ff 0%, transparent 25%),
        var(--bg);
      min-height: 100vh;
    }

    .shell {
      max-width: 1440px;
      margin: 0 auto;
      padding: 26px;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 18px;
      margin-bottom: 18px;
    }

    .brand h1 {
      margin: 0;
      font-size: 34px;
      letter-spacing: -0.03em;
      color: #0b2540;
    }

    .brand p {
      margin: 8px 0 0;
      font-size: 13px;
      color: var(--muted);
    }

    .status-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
      max-width: 520px;
    }

    .chip {
      border: 1px solid var(--border);
      background: var(--surface);
      padding: 7px 11px;
      border-radius: 999px;
      font-size: 12px;
      color: #0f2943;
      box-shadow: 0 2px 8px rgba(2, 8, 23, 0.05);
    }

    .chip.live { border-color: #9dd6ff; background: #ecf8ff; }

    .layout {
      display: grid;
      grid-template-columns: 2.3fr 1fr;
      gap: 14px;
    }

    .panel {
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--surface);
      padding: 14px;
      box-shadow: var(--shadow);
    }

    .panel + .panel { margin-top: 12px; }

    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
      gap: 10px;
    }

    .panel-title {
      margin: 0;
      font-size: 15px;
      color: #0f2943;
    }

    .subtle {
      font-size: 12px;
      color: var(--muted);
    }

    .kpis {
      display: grid;
      grid-template-columns: repeat(6, minmax(110px, 1fr));
      gap: 10px;
    }

    .kpi {
      background: var(--surface-alt);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
      min-height: 84px;
    }

    .kpi .label {
      font-size: 12px;
      color: var(--muted);
    }

    .kpi .value {
      margin-top: 7px;
      font-size: 28px;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: #0f2943;
    }

    .pods {
      display: grid;
      grid-template-columns: repeat(3, minmax(190px, 1fr));
      gap: 10px;
      max-height: 420px;
      overflow: auto;
      padding-right: 4px;
    }

    .pod {
      border: 1px solid var(--border);
      border-left: 4px solid #94a3b8;
      border-radius: 12px;
      background: #ffffff;
      padding: 10px;
    }

    .pod.good { border-left-color: var(--good); }
    .pod.warn { border-left-color: var(--warn); }
    .pod.bad { border-left-color: var(--bad); }

    .pod .name {
      font-size: 12px;
      color: #1d4f85;
      word-break: break-all;
    }

    .pod .status {
      margin-top: 6px;
      font-weight: 700;
      font-size: 16px;
      color: #0f2943;
    }

    .pod .meta {
      margin-top: 4px;
      font-size: 12px;
      color: var(--muted);
    }

    .timeline {
      border: 1px solid var(--border);
      border-radius: 12px;
      max-height: 250px;
      overflow: auto;
      background: #fcfeff;
    }

    .evt {
      border-bottom: 1px solid #eef3f8;
      padding: 8px 10px;
      font-size: 12px;
      color: #0f2943;
    }

    .evt.good { color: #166534; }
    .evt.bad { color: #b91c1c; }

    .integration-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 8px;
    }

    .integration {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 9px;
      background: var(--surface-alt);
      font-size: 12px;
      color: #0f2943;
    }

    .dot {
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      margin-right: 7px;
    }

    .dot.good { background: var(--good); }
    .dot.bad { background: var(--bad); }

    .btn-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }

    button, .linkbtn {
      border-radius: 10px;
      border: 1px solid #1d4ed8;
      background: #2563eb;
      color: white;
      font-size: 12px;
      font-weight: 600;
      padding: 9px 12px;
      cursor: pointer;
      text-decoration: none;
      display: inline-block;
    }

    .linkbtn.alt,
    button.alt {
      background: #ffffff;
      color: #0f2943;
      border-color: #bcd2e8;
    }

    button.danger {
      border-color: #dc2626;
      background: #dc2626;
    }

    .monitor-box {
      border: 1px dashed #c7d9eb;
      border-radius: 12px;
      padding: 10px;
      background: #f8fbff;
      margin-top: 10px;
    }

    .foot {
      margin-top: 8px;
      font-size: 11px;
      color: var(--muted);
      line-height: 1.4;
    }

    @media (max-width: 1200px) {
      .layout { grid-template-columns: 1fr; }
      .kpis { grid-template-columns: repeat(3, minmax(120px, 1fr)); }
    }

    @media (max-width: 760px) {
      .shell { padding: 14px; }
      .kpis { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      .pods { grid-template-columns: 1fr; }
      .header { flex-direction: column; align-items: flex-start; }
      .status-row { justify-content: flex-start; }
    }
  </style>
</head>
<body>
<div class='shell'>
  <header class='header'>
    <div class='brand'>
      <h1>KubeGuard Command Center</h1>
      <p>Unified light-mode operations cockpit for Kubernetes, Prometheus, Grafana, Discord, and Slack.</p>
    </div>
    <div class='status-row'>
      <span id='wsState' class='chip live'>WebSocket: Connecting</span>
      <span id='lastUpdate' class='chip'>Last update: --</span>
    </div>
  </header>

  <main class='layout'>
    <section>
      <div class='panel'>
        <div class='panel-head'>
          <h3 class='panel-title'>Cluster Health</h3>
          <span class='subtle'>Live metrics every 2 seconds</span>
        </div>
        <div class='kpis'>
          <div class='kpi'><div class='label'>Running Pods</div><div id='kRunning' class='value'>-</div></div>
          <div class='kpi'><div class='label'>Total Pods</div><div id='kTotal' class='value'>-</div></div>
          <div class='kpi'><div class='label'>Crash Count</div><div id='kCrashes' class='value'>-</div></div>
          <div class='kpi'><div class='label'>Restarts</div><div id='kRestarts' class='value'>-</div></div>
          <div class='kpi'><div class='label'>Req/Min</div><div id='kReq' class='value'>-</div></div>
          <div class='kpi'><div class='label'>Firing Alerts</div><div id='kAlerts' class='value'>-</div></div>
        </div>
      </div>

      <div class='panel'>
        <div class='panel-head'>
          <h3 class='panel-title'>Pod Fleet</h3>
          <span id='fleetSummary' class='subtle'>-</span>
        </div>
        <div id='pods' class='pods'></div>
      </div>

      <div class='panel'>
        <div class='panel-head'>
          <h3 class='panel-title'>Live Timeline</h3>
          <button class='alt' onclick='clearTimeline()'>Clear</button>
        </div>
        <div id='timeline' class='timeline'></div>
      </div>
    </section>

    <aside>
      <div class='panel'>
        <h3 class='panel-title'>Integrations</h3>
        <div class='integration-grid'>
          <div class='integration' id='sProm'>Prometheus: checking...</div>
          <div class='integration' id='sGraf'>Grafana: checking...</div>
          <div class='integration' id='sDisc'>Discord: checking...</div>
          <div class='integration' id='sSlack'>Slack: checking...</div>
        </div>
        <div class='btn-row'>
          <button class='danger' onclick='triggerCrash()'>Trigger Crash</button>
          <button onclick='testDiscord()'>Test Discord</button>
          <button onclick='testSlack()'>Test Slack</button>
          <a class='linkbtn alt' id='openGrafana' target='_blank' rel='noopener'>Open Grafana</a>
          <a class='linkbtn alt' id='openProm' target='_blank' rel='noopener'>Open Prometheus</a>
        </div>
      </div>

      <div class='panel'>
        <h3 class='panel-title'>Monitoring Links</h3>
        <div class='monitor-box'>
          <div class='subtle'>Grafana embed may be blocked by browser frame policy. Use the button above for full view.</div>
        </div>
        <div class='foot'>Prometheus URL: <span id='promUrlText'>--</span></div>
        <div class='foot'>Grafana URL: <span id='grafUrlText'>--</span></div>
      </div>

      <div class='panel'>
        <h3 class='panel-title'>Alert Channels</h3>
        <div class='foot'>Discord and Slack test actions are available from this panel.</div>
        <div class='foot'>Slack app credentials are loaded, but posting can require runtime webhook or bot/channel configuration.</div>
      </div>
    </aside>
  </main>
</div>

<script>
let prev = {};
const timeline = document.getElementById('timeline');

function fmtNum(v) {
  if (Number.isNaN(v)) return '-';
  return Math.round(v).toString();
}

function addEvent(text, cls) {
  const now = new Date().toLocaleTimeString();
  const row = document.createElement('div');
  row.className = `evt ${cls || ''}`;
  row.textContent = `[${now}] ${text}`;
  timeline.prepend(row);
  while (timeline.children.length > 100) timeline.removeChild(timeline.lastChild);
}

function clearTimeline() {
  timeline.innerHTML = '';
}

function podClass(p) {
  if (p.reason) return 'bad';
  if (p.ready) return 'good';
  return 'warn';
}

function podStatus(p) {
  if (p.reason) return p.reason;
  if (p.ready) return 'Running';
  return p.phase;
}

function renderPods(pods) {
  document.getElementById('pods').innerHTML = pods.map((p) => `
    <article class='pod ${podClass(p)}'>
      <div class='name'>${p.name}</div>
      <div class='status'>${podStatus(p)}</div>
      <div class='meta'>Service: ${p.service}</div>
      <div class='meta'>Restarts: ${p.restarts}</div>
    </article>
  `).join('');

  const running = pods.filter((p) => p.ready).length;
  document.getElementById('fleetSummary').textContent = `${running}/${pods.length} healthy`;

  pods.forEach((p) => {
    const old = prev[p.name];
    if (old && old.reason !== p.reason) {
      if (p.reason) addEvent(`Crash detected: ${p.name} (${p.reason})`, 'bad');
      else addEvent(`Recovered: ${p.name}`, 'good');
    }
    prev[p.name] = p;
  });
}

function renderSummary(sum) {
  document.getElementById('kRunning').textContent = `${sum.running}`;
  document.getElementById('kTotal').textContent = `${sum.total}`;
  document.getElementById('kCrashes').textContent = fmtNum(sum.crash_counter);
  document.getElementById('kRestarts').textContent = fmtNum(sum.restarts);
  document.getElementById('kReq').textContent = (sum.request_rate_min || 0).toFixed(1);
  document.getElementById('kAlerts').textContent = fmtNum(sum.alerts_firing || 0);
  document.getElementById('lastUpdate').textContent = `Last update: ${new Date(sum.timestamp).toLocaleTimeString()}`;
}

function setIntegration(id, ok, label) {
  document.getElementById(id).innerHTML = `<span class='dot ${ok ? 'good' : 'bad'}'></span>${label}`;
}

async function refreshStatus() {
  const r = await fetch('/api/integrations/status');
  const s = await r.json();
  setIntegration('sProm', s.prometheus_up, 'Prometheus');
  setIntegration('sGraf', s.grafana_up, 'Grafana');
  setIntegration('sDisc', s.discord_configured, 'Discord Webhook');
  setIntegration('sSlack', s.slack_runtime_configured || s.slack_app_configured, s.slack_runtime_configured ? 'Slack Runtime Alerts' : 'Slack App Configured');
  document.getElementById('openGrafana').href = s.grafana_url;
  document.getElementById('openProm').href = s.prometheus_url;
  document.getElementById('promUrlText').textContent = s.prometheus_url;
  document.getElementById('grafUrlText').textContent = s.grafana_url;
}

async function testDiscord() {
  try {
    const r = await fetch('/api/integrations/test-discord', { method: 'POST' });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Discord test failed');
    addEvent(data.message, 'good');
  } catch (e) {
    addEvent(`Discord test failed: ${e.message}`, 'bad');
  }
}

async function testSlack() {
  try {
    const r = await fetch('/api/integrations/test-slack', { method: 'POST' });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Slack test failed');
    addEvent(data.message, 'good');
  } catch (e) {
    addEvent(`Slack test failed: ${e.message}`, 'bad');
  }
}

async function triggerCrash() {
  await fetch('/api/actions/crash', { method: 'POST' });
  addEvent('Crash requested from dashboard', 'bad');
}

const ws = new WebSocket(`ws://${location.host}/ws`);
ws.onopen = () => {
  document.getElementById('wsState').textContent = 'WebSocket: Connected';
  addEvent('Realtime stream connected', 'good');
};
ws.onclose = () => {
  document.getElementById('wsState').textContent = 'WebSocket: Disconnected';
  addEvent('Realtime stream disconnected', 'bad');
};
ws.onmessage = (ev) => {
  const payload = JSON.parse(ev.data);
  renderPods(payload.pods);
  renderSummary(payload.summary);
};

refreshStatus();
setInterval(refreshStatus, 12000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return DASHBOARD_HTML


sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

@sio.event
async def connect(sid, environ):
    print(f"Socket.IO client connected: {sid}")
    await sio.emit("log", {"level": "good", "message": f"Client connected: {sid}"})

@sio.event
async def disconnect(sid):
    print(f"Socket.IO client disconnected: {sid}")
    await sio.emit("log", {"level": "warning", "message": f"Client disconnected: {sid}"})

async def background_task():
    while True:
        try:
            pods = _get_cluster_state()
            await sio.emit('metrics', {"pods": pods, "summary": _summary(pods)})
        except Exception as e:
            print(f"Error in background task: {e}")
        await asyncio.sleep(2)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_task())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(socket_app, host="0.0.0.0", port=DASHBOARD_PORT)
