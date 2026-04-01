# KubeGuard: Kubernetes Resilience, Observability, and Auto-Remediation Lab

KubeGuard is a full-stack reliability engineering project that simulates real production failure scenarios on Kubernetes and demonstrates how to detect, visualize, and remediate them.

It combines:
- Python FastAPI microservices
- Kubernetes deployments with probes and scaling policies
- Prometheus metrics and alerting
- Live dashboards (FastAPI UI and Next.js UI)
- Automated crash detection and operator-style remediation
- Chaos engineering scripts (pod kill, OOM, CPU stress, cascade failures)
- ML-based anomaly detection on live Prometheus signals

This repository supports two operating modes:
- **Baseline mode**: Single microservice deployment (simple setup).
- **Advanced mode (v2)**: Multi-service architecture (`api-gateway`, `core-service`, `worker-service`) with richer observability and controls.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Repository Structure](#repository-structure)
3. [Tech Stack](#tech-stack)
4. [Prerequisites](#prerequisites)
5. [Environment Variables](#environment-variables)
6. [Quick Start (UI-first local workflow)](#quick-start-ui-first-local-workflow)
7. [Kubernetes Deployment: Baseline Mode](#kubernetes-deployment-baseline-mode)
8. [Kubernetes Deployment: Advanced Mode (Recommended)](#kubernetes-deployment-advanced-mode-recommended)
9. [Monitoring and Alerting](#monitoring-and-alerting)
10. [Dashboards and Frontend](#dashboards-and-frontend)
11. [Service and API Reference](#service-and-api-reference)
12. [Chaos Engineering Workflows](#chaos-engineering-workflows)
13. [Watchers, Operator, and ML](#watchers-operator-and-ml)
14. [Validation Checklist](#validation-checklist)
15. [Troubleshooting](#troubleshooting)
16. [Security Notes](#security-notes)
17. [Useful Commands](#useful-commands)

## Architecture Overview

### Baseline mode

- `microservice` runs as a FastAPI app exposed via NodePort.
- Prometheus scrapes `/metrics`.
- Crash and stress endpoints intentionally induce failures for testing.

### Advanced mode (v2)

- `api-gateway` receives external traffic and orchestrates downstream calls.
- `core-service` performs lightweight processing work.
- `worker-service` enqueues/consumes background jobs.
- Dashboard backend (`dashboard/live_server.py`) aggregates cluster status + Prometheus KPIs and exposes control APIs.
- Next.js frontend consumes dashboard APIs and websocket/socket stream for a modern real-time operations UI.
- Watchers/operator/ML scripts monitor failures and emit Discord/Slack notifications.

## Repository Structure

```text
.
├── api-gateway/                 # Public entry service (FastAPI)
├── core-service/                # Processing service (FastAPI)
├── worker-service/              # Queue worker service (FastAPI)
├── microservice/                # Baseline single service (FastAPI)
├── dashboard/                   # Dashboard backends + static UI
│   ├── server.py                # Static dashboard with REST + WS
│   └── live_server.py           # Unified live ops center on port 9001
├── frontend/                    # Next.js dashboard frontend
│   ├── app/api/*                # Proxy routes to backend dashboard
│   ├── components/              # Realtime dashboard client UI
│   └── lib/                     # Backend proxy + types
├── watcher/                     # Crash watcher, predictor, operator controller
├── ml/                          # IsolationForest anomaly detector
├── chaos/                       # Chaos scripts (basic + advanced)
├── k8s/                         # Kubernetes manifests (baseline + advanced)
├── start-services.bat           # Convenience launcher (backend + frontend)
├── requirements.txt             # Python dependencies for tooling/scripts
├── ADVANCED_IMPLEMENTATION_WINDOWS.md
└── CLAUDE.md
```

## Tech Stack

- **Backend services**: Python, FastAPI, Uvicorn, `prometheus_client`
- **Frontend**: Next.js 14, React 18, TypeScript, Recharts, Socket.IO client
- **Cluster**: Kubernetes (Docker Desktop or Minikube)
- **Monitoring**: Prometheus, Grafana
- **Alerting**: Discord and Slack (webhook and/or Slack Bot API)
- **Automation scripts**: Python (`requests`, `kubernetes`, `scikit-learn`, `numpy`)

## Prerequisites

Install and verify:

- Docker Desktop (with Kubernetes enabled) **or** Minikube
- `kubectl`
- Helm 3
- Python 3.10+
- Node.js 18+
- npm 9+

Optional but recommended on Windows:

- PowerShell 7+
- A Python virtual environment in project root (`.venv`)

## Environment Variables

Create a `.env` file in repository root (same level as `requirements.txt`).

Suggested template:

```env
# Common
NAMESPACE=kubeguard

# Monitoring endpoints (dashboard/scripts)
PROMETHEUS_URL=http://localhost:9090
GRAFANA_URL=http://localhost:30300
GATEWAY_URL=http://localhost:30081
DASHBOARD_PORT=9001

# Alerts
DISCORD_WEBHOOK_URL=
DISCORD_CRITICAL_URL=
SLACK_WEBHOOK_URL=
SLACK_BOT_TOKEN=
SLACK_CHANNEL_ID=
SLACK_APP_ID=

# Watchers
CHECK_INTERVAL=5
```

Frontend environment options (`frontend/.env.local`):

```env
KG_BACKEND_URL=http://localhost:9001
NEXT_PUBLIC_KG_BACKEND_URL=http://localhost:9001
NEXT_PUBLIC_KG_WS_URL=http://localhost:9001
NEXT_PUBLIC_KG_WS_PORT=9001
```

## Quick Start (UI-first local workflow)

If your cluster stack is already running and you just want the live dashboards:

```powershell
# From repo root
python -m pip install -r requirements.txt
npm --prefix frontend install

# Start backend dashboard + Next.js frontend
.\start-services.bat
```

Endpoints:
- Backend dashboard API/UI: `http://localhost:9001`
- Next.js frontend: `http://localhost:3000`

## Kubernetes Deployment: Baseline Mode

Use this when you want minimal setup and simple crash testing.

```powershell
# Build baseline service image
docker build -t kubeguard-microservice:latest .\microservice

# Deploy namespace + baseline service
kubectl apply -f k8s\namespace.yaml
kubectl apply -f k8s\deployment.yaml
kubectl apply -f k8s\service.yaml

# Verify
kubectl get pods -n kubeguard
kubectl get svc -n kubeguard
```

NodePort access (baseline):
- `http://localhost:30080/health`
- `http://localhost:30080/info`
- `http://localhost:30080/metrics`
- `http://localhost:30080/crash` (intentional crash)

## Kubernetes Deployment: Advanced Mode (Recommended)

Advanced mode gives better architecture parity with production systems.

### 1) Build service images

```powershell
docker build -t kubeguard-api-gateway:latest .\api-gateway
docker build -t kubeguard-core-service:latest .\core-service
docker build -t kubeguard-worker-service:latest .\worker-service
```

### 2) Apply namespace, RBAC, services, scaling, policies

```powershell
kubectl apply -f k8s\namespace-rbac.yaml
kubectl apply -f k8s\deployments-advanced.yaml
kubectl apply -f k8s\services-advanced.yaml
kubectl apply -f k8s\hpa-advanced.yaml
kubectl apply -f k8s\pdb-advanced.yaml
kubectl apply -f k8s\networkpolicy-advanced.yaml
```

### 3) Validate cluster resources

```powershell
kubectl get all -n kubeguard
kubectl get hpa -n kubeguard
kubectl get pdb -n kubeguard
kubectl get networkpolicy -n kubeguard
```

Primary advanced service access:
- API gateway NodePort: `http://localhost:30081`

## Monitoring and Alerting

### Prometheus/Grafana installation via Helm

```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack `
  --namespace monitoring --create-namespace `
  -f k8s/helm-values-dockerdesktop.yaml
```

### Apply service monitors and rules

```powershell
kubectl apply -f k8s\servicemonitor.yaml
kubectl apply -f k8s\servicemonitors-advanced.yaml
kubectl apply -f k8s\prometheus-rules-advanced.yaml
```

### Alertmanager config

- Example secret manifest: `k8s/alertmanager-secret.example.yaml`
- Alertmanager routing config file: `k8s/alertmanager-advanced.yml`

If you are using webhook URLs, store them in Kubernetes secrets and avoid committing real webhook values in git.

## Dashboards and Frontend

### Backend dashboards

1. `dashboard/server.py`
- Static HTML dashboard
- WebSocket endpoint at `/ws`
- Crash action endpoint `/api/crash`
- Prometheus metric summary/risk score endpoints

2. `dashboard/live_server.py` (recommended)
- Unified operations dashboard on port `9001`
- Integrations status API
- Crash trigger API
- Discord/Slack test APIs
- Emits live metrics via Socket.IO

Run:

```powershell
python dashboard/live_server.py
```

### Next.js frontend (recommended UI)

The frontend provides:
- Real-time pod fleet view
- KPI panels and history charts
- Crash/integration test controls
- API proxying to backend dashboard APIs

Run:

```powershell
npm --prefix frontend install
npm --prefix frontend run dev
```

## Service and API Reference

### Shared microservice endpoints (`api-gateway`, `core-service`, `worker-service`)

- `GET /health`
- `GET /ready`
- `GET /info`
- `GET /metrics`
- `GET /crash` (intentional process exit)
- `GET /stress`
- `GET /oom` (intentional memory pressure + exit)

### API gateway specific (`api-gateway/app.py`)

- `GET /api/process?payload=demo`
- `GET /api/health-all`

### Core service specific (`core-service/app.py`)

- `GET /process?payload=data`

### Worker service specific (`worker-service/app.py`)

- `GET /enqueue?job=default`
- `GET /queue-depth`

### Dashboard backend (`dashboard/live_server.py`)

- `GET /api/summary`
- `GET /api/integrations/status`
- `POST /api/actions/crash`
- `POST /api/integrations/test-discord`
- `POST /api/integrations/test-slack`

### Frontend proxy routes (`frontend/app/api/*`)

- `GET /api/summary` -> backend `/api/summary`
- `GET /api/status` -> backend `/api/integrations/status`
- `POST /api/trigger-crash` -> backend `/api/actions/crash`
- `POST /api/test-discord` -> backend `/api/integrations/test-discord`
- `POST /api/test-slack` -> backend `/api/integrations/test-slack`

## Chaos Engineering Workflows

### Basic chaos

```powershell
python chaos/chaos_monkey.py --mode high --duration 60
```

Modes:
- `low` (30s interval)
- `medium` (15s interval)
- `high` (5s interval)

### Advanced chaos

```powershell
python chaos/advanced_chaos.py --namespace kubeguard --mode random --duration 120
```

Supported attack modes:
- `delete`: force-delete random pod
- `oom`: invoke `/oom` on target pod
- `cpu`: invoke `/stress` concurrently
- `cascade`: delete multiple pods quickly
- `random`: randomize among all above modes

## Watchers, Operator, and ML

### Crash watcher

```powershell
python watcher/crash_watcher.py
```

What it does:
- Polls pod states with `kubectl get pods -o json`
- Detects crashes/restarts/recoveries
- Sends Discord alerts with restart deltas

### Failure predictor

```powershell
python watcher/failure_predictor.py
```

What it does:
- Pulls restart metrics from Prometheus
- Computes a risk score from total restarts + acceleration
- Sends warnings when risk crosses threshold

### Operator controller

```powershell
python watcher/operator_controller.py
```

What it does:
- Watches pod events via Kubernetes API
- Applies simple remediation decisions (natural restart, delete pod, etc.)
- Emits Discord/Slack alerts
- Tracks incident log in memory

### ML anomaly detector

```powershell
python ml/anomaly_detector.py
```

What it does:
- Extracts per-pod feature vectors from Prometheus
- Trains/retrains IsolationForest
- Flags anomalous pods and pushes alert notifications

## Validation Checklist

Run this after deployments/changes:

1. Cluster resources are healthy:
```powershell
kubectl get pods -n kubeguard
kubectl get svc -n kubeguard
kubectl get hpa -n kubeguard
```

2. Prometheus targets are up.
3. Dashboard shows live pod data and KPI changes.
4. Trigger crash path works and pod auto-recovers.
5. Discord/Slack test actions return success.
6. Chaos scripts show expected recoveries.

## Troubleshooting

### Pods not starting

- Check image pull and pod events:
```powershell
kubectl describe pod <pod-name> -n kubeguard
kubectl logs <pod-name> -n kubeguard
```

- Ensure local image tags match manifests (`:latest`) and `imagePullPolicy` behavior.

### Frontend cannot reach backend

- Verify `KG_BACKEND_URL` / `NEXT_PUBLIC_KG_BACKEND_URL`.
- Confirm backend dashboard is running on `9001`.
- Test directly:
```powershell
curl http://localhost:9001/api/summary
```

### Websocket/socket stream disconnected

- Confirm frontend WS configuration (`NEXT_PUBLIC_KG_WS_URL`, `NEXT_PUBLIC_KG_WS_PORT`).
- Verify backend process logs for Socket.IO/websocket errors.

### Prometheus has no data

- Verify ServiceMonitors are applied.
- Check Prometheus target status and scrape config.
- Confirm pod annotations expose `/metrics`.

### Alerts not delivered

- Verify webhook/token env vars are set in `.env`.
- Test via dashboard endpoints first (`/api/integrations/test-discord`, `/api/integrations/test-slack`).
- Check HTTP non-2xx responses in script logs.

## Security Notes

- Never commit real Discord/Slack webhook URLs or bot tokens.
- Keep alerting credentials in `.env` locally and Kubernetes secrets in cluster.
- Rotate any webhook URL that has been committed previously.
- Review `k8s/alertmanager-advanced.yml` before using in shared/public repos.

## Useful Commands

```powershell
# Install Python deps
python -m pip install -r requirements.txt

# Start dashboards quickly
.\start-services.bat

# Watch pods continuously
kubectl get pods -n kubeguard -w

# Trigger baseline crash
curl http://localhost:30080/crash

# Trigger advanced gateway crash path
curl http://localhost:30081/crash

# Query health-all through gateway
curl "http://localhost:30081/api/health-all"
```

---

If you want, the next step can be splitting this into:
- a contributor-focused `CONTRIBUTING.md`
- a security-focused `SECURITY.md`
- and per-folder `README.md` docs (`watcher`, `chaos`, `k8s`) for even cleaner navigation.
#   K u b e G u a r d  
 