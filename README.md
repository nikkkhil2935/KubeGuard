<p align="center">
  <img src="https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white" alt="Kubernetes"/>
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=next.js&logoColor=white" alt="Next.js"/>
  <img src="https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white" alt="Prometheus"/>
  <img src="https://img.shields.io/badge/Grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white" alt="Grafana"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
</p>

<h1 align="center">🛡️ KubeGuard</h1>
<h3 align="center">Kubernetes Resilience, Observability & Auto-Remediation Platform</h3>

<p align="center">
  <strong>Team S8UL</strong> | Production-Grade Reliability Engineering Lab
</p>

---

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
2. [System Architecture Diagram](#system-architecture-diagram)
3. [Repository Structure](#repository-structure)
4. [Tech Stack](#tech-stack)
5. [Prerequisites](#prerequisites)
6. [Environment Variables](#environment-variables)
7. [Quick Start (UI-first local workflow)](#quick-start-ui-first-local-workflow)
8. [Kubernetes Deployment: Baseline Mode](#kubernetes-deployment-baseline-mode)
9. [Kubernetes Deployment: Advanced Mode (Recommended)](#kubernetes-deployment-advanced-mode-recommended)
10. [Monitoring and Alerting](#monitoring-and-alerting)
11. [Dashboards and Frontend](#dashboards-and-frontend)
12. [Service and API Reference](#service-and-api-reference)
13. [Prometheus Metrics Reference](#prometheus-metrics-reference)
14. [Chaos Engineering Workflows](#chaos-engineering-workflows)
15. [Watchers, Operator, and ML](#watchers-operator-and-ml)
16. [Machine Learning Anomaly Detection](#machine-learning-anomaly-detection)
17. [Kubernetes Resource Specifications](#kubernetes-resource-specifications)
18. [Network Policies & Security](#network-policies--security)
19. [Alerting Configuration](#alerting-configuration)
20. [Validation Checklist](#validation-checklist)
21. [Troubleshooting](#troubleshooting)
22. [Security Notes](#security-notes)
23. [Useful Commands](#useful-commands)
24. [Contributing](#contributing)
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

---

## System Architecture Diagram

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL ACCESS                                      │
│                                                                                   │
│    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                       │
│    │   Users     │     │  DevOps     │     │  Grafana    │                       │
│    │  (Browser)  │     │  (kubectl)  │     │  Dashboard  │                       │
│    └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                       │
│           │                   │                   │                               │
└───────────┼───────────────────┼───────────────────┼───────────────────────────────┘
            │                   │                   │
            ▼                   ▼                   ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           KUBERNETES CLUSTER                                       │
│                          (Docker Desktop / Minikube)                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                        kubeguard NAMESPACE                                   │  │
│  │                                                                              │  │
│  │   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐      │  │
│  │   │   API-GATEWAY    │    │   CORE-SERVICE   │    │  WORKER-SERVICE  │      │  │
│  │   │   (3 replicas)   │───▶│   (3 replicas)   │───▶│   (2 replicas)   │      │  │
│  │   │   Port: 8000     │    │   Port: 8001     │    │   Port: 8002     │      │  │
│  │   │   NodePort:30081 │    │   ClusterIP      │    │   ClusterIP      │      │  │
│  │   └────────┬─────────┘    └──────────────────┘    └──────────────────┘      │  │
│  │            │                       │                       │                 │  │
│  │            │              ┌────────┴────────┬──────────────┤                 │  │
│  │            ▼              ▼                 ▼              ▼                 │  │
│  │   ┌──────────────────────────────────────────────────────────────────┐      │  │
│  │   │                    PROMETHEUS METRICS                             │      │  │
│  │   │  • http_requests_total    • pod_crashes_total                     │      │  │
│  │   │  • http_errors_total      • http_request_duration_seconds         │      │  │
│  │   │  • service_uptime_seconds • service_memory_mb                     │      │  │
│  │   └──────────────────────────────────────────────────────────────────┘      │  │
│  │                                                                              │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                        monitoring NAMESPACE                                  │  │
│  │  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐             │  │
│  │  │   PROMETHEUS   │───▶│    GRAFANA     │    │  ALERTMANAGER  │             │  │
│  │  │  NodePort:30090│    │ NodePort:30300 │    │                │             │  │
│  │  └────────────────┘    └────────────────┘    └───────┬────────┘             │  │
│  │                                                       │                      │  │
│  └───────────────────────────────────────────────────────┼──────────────────────┘  │
│                                                          │                         │
└──────────────────────────────────────────────────────────┼─────────────────────────┘
                                                           │
                                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            ALERTING TARGETS                                       │
│    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                       │
│    │   Discord   │     │    Slack    │     │   Webhook   │                       │
│    │  (Webhook)  │     │  (Bot/Hook) │     │  (Custom)   │                       │
│    └─────────────┘     └─────────────┘     └─────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Service Communication Flow

```
                                    ┌─────────────────┐
                                    │   Client/User   │
                                    └────────┬────────┘
                                             │
                                             │ HTTP Request
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│                              API-GATEWAY SERVICE                                    │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │  Endpoints:                                                                   │  │
│  │  • GET  /health        - Liveness check                                      │  │
│  │  • GET  /ready         - Readiness check                                     │  │
│  │  • GET  /info          - Service metadata                                    │  │
│  │  • GET  /metrics       - Prometheus metrics                                  │  │
│  │  • GET  /crash         - Intentional crash (testing)                         │  │
│  │  • GET  /stress        - CPU stress test                                     │  │
│  │  • GET  /oom           - Memory exhaustion test                              │  │
│  │  • GET  /api/process   - Orchestrated processing                             │  │
│  │  • GET  /api/health-all- All services health check                           │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────┬───────────────────────────────────────────┬───────────────────┘
                     │                                           │
                     │ Internal HTTP                             │ Internal HTTP
                     ▼                                           ▼
┌────────────────────────────────────────┐  ┌────────────────────────────────────────┐
│         CORE-SERVICE                   │  │         WORKER-SERVICE                 │
│  ┌──────────────────────────────────┐  │  │  ┌──────────────────────────────────┐  │
│  │  • /health, /ready, /info        │  │  │  │  • /health, /ready, /info        │  │
│  │  • /metrics                      │  │  │  │  • /metrics                      │  │
│  │  • /process?payload=<data>       │  │  │  │  • /enqueue?job=<name>           │  │
│  │  • /crash, /stress, /oom         │  │  │  │  • /queue-depth                  │  │
│  └──────────────────────────────────┘  │  │  │  • /crash, /stress, /oom         │  │
│                                        │  │  └──────────────────────────────────┘  │
│  Processing Mode:                      │  │                                        │
│  • Lightweight data processing         │  │  Processing Mode:                      │
│  • JSON payload handling               │  │  • Background job queue management     │
│  • Validation and transformation       │  │  • Job enqueue/dequeue operations      │
└────────────────────────────────────────┘  └────────────────────────────────────────┘
```

### Monitoring & Observability Stack

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          OBSERVABILITY PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

     ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
     │  API-Gateway   │   │  Core-Service  │   │ Worker-Service │
     │    /metrics    │   │    /metrics    │   │    /metrics    │
     └───────┬────────┘   └───────┬────────┘   └───────┬────────┘
             │                    │                    │
             │    prometheus_client (Python)           │
             │                    │                    │
             └─────────────┬──────┴────────────────────┘
                           │
                           │  Scrape every 15s
                           ▼
              ┌────────────────────────────┐
              │        PROMETHEUS          │
              │   • ServiceMonitors        │
              │   • AlertRules             │
              │   • Recording Rules        │
              └─────────────┬──────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│    GRAFANA     │ │  ALERTMANAGER  │ │  ML DETECTOR   │
│ • Dashboards   │ │ • Routing      │ │ • Anomaly Det. │
│ • Visualize    │ │ • Grouping     │ │ • Feature Eng. │
│ • Alerts       │ │ • Silencing    │ │ • Prediction   │
└────────────────┘ └───────┬────────┘ └───────┬────────┘
                           │                  │
                           ▼                  ▼
              ┌────────────────────────────────────────┐
              │           NOTIFICATION CHANNELS         │
              │  ┌──────────┐  ┌──────────┐  ┌───────┐ │
              │  │ Discord  │  │  Slack   │  │ Email │ │
              │  │ Webhooks │  │ Bot API  │  │       │ │
              │  └──────────┘  └──────────┘  └───────┘ │
              └────────────────────────────────────────┘
```

---

## Repository Structure

```text
.
├── api-gateway/                 # Public entry service (FastAPI)
│   ├── app.py                   # Main application with orchestration endpoints
│   ├── shared_app.py            # Shared FastAPI factory with common endpoints
│   ├── Dockerfile               # Container build configuration
│   └── requirements.txt         # Python dependencies
│
├── core-service/                # Processing service (FastAPI)
│   ├── app.py                   # Main application with /process endpoint
│   ├── shared_app.py            # Shared FastAPI factory
│   ├── Dockerfile               # Container build configuration
│   └── requirements.txt         # Python dependencies
│
├── worker-service/              # Queue worker service (FastAPI)
│   ├── app.py                   # Main application with job queue endpoints
│   ├── shared_app.py            # Shared FastAPI factory
│   ├── Dockerfile               # Container build configuration
│   └── requirements.txt         # Python dependencies
│
├── microservice/                # Baseline single service (FastAPI)
│   ├── app.py                   # Standalone service with full endpoint set
│   ├── Dockerfile               # Container build configuration
│   └── requirements.txt         # Python dependencies
│
├── dashboard/                   # Dashboard backends + static UI
│   ├── server.py                # Static dashboard with REST + WebSocket
│   ├── live_server.py           # Unified live ops center (port 9001)
│   └── static/                  # Static HTML/CSS/JS files
│
├── frontend/                    # Next.js dashboard frontend
│   ├── app/                     # Next.js App Router structure
│   │   ├── api/                 # API route proxies
│   │   │   ├── summary/         # /api/summary proxy
│   │   │   ├── status/          # /api/status proxy
│   │   │   ├── trigger-crash/   # /api/trigger-crash proxy
│   │   │   ├── test-discord/    # /api/test-discord proxy
│   │   │   └── test-slack/      # /api/test-slack proxy
│   │   └── page.tsx             # Main dashboard page
│   ├── components/              # React components
│   │   ├── Dashboard.tsx        # Main dashboard container
│   │   ├── PodFleet.tsx         # Pod status grid
│   │   ├── KPIPanel.tsx         # Metrics display
│   │   └── ControlPanel.tsx     # Action buttons
│   ├── lib/                     # Backend proxy + types
│   │   ├── backend-proxy.ts     # Server-side API calls
│   │   └── types.ts             # TypeScript interfaces
│   ├── package.json             # Node.js dependencies
│   └── next.config.js           # Next.js configuration
│
├── watcher/                     # Crash watcher, predictor, operator controller
│   ├── crash_watcher.py         # Pod crash detection + Discord alerts
│   ├── failure_predictor.py     # Prometheus-based risk scoring
│   └── operator_controller.py   # K8s event watcher + auto-remediation
│
├── ml/                          # IsolationForest anomaly detector
│   └── anomaly_detector.py      # ML-based pod anomaly detection
│
├── chaos/                       # Chaos scripts (basic + advanced)
│   ├── chaos_monkey.py          # Basic chaos: random pod kills
│   └── advanced_chaos.py        # Advanced: OOM, CPU, cascade attacks
│
├── k8s/                         # Kubernetes manifests (baseline + advanced)
│   ├── namespace.yaml           # Baseline namespace definition
│   ├── namespace-rbac.yaml      # Advanced namespace + RBAC
│   ├── deployment.yaml          # Baseline deployment (5 replicas)
│   ├── deployments-advanced.yaml# Advanced multi-service deployments
│   ├── service.yaml             # Baseline NodePort service
│   ├── services-advanced.yaml   # Advanced service definitions
│   ├── hpa.yaml                 # Baseline HPA configuration
│   ├── hpa-advanced.yaml        # Advanced HPA per service
│   ├── pdb.yaml                 # Baseline Pod Disruption Budget
│   ├── pdb-advanced.yaml        # Advanced PDBs per service
│   ├── networkpolicy-advanced.yaml # Network isolation rules
│   ├── servicemonitor.yaml      # Baseline Prometheus ServiceMonitor
│   ├── servicemonitors-advanced.yaml # Advanced ServiceMonitors
│   ├── prometheus-rules-advanced.yaml # Alert rules
│   ├── alertmanager-advanced.yml # Alertmanager routing config
│   ├── alertmanager-secret.example.yaml # Secret template
│   └── helm-values-dockerdesktop.yaml # Helm values for Docker Desktop
│
├── start-services.bat           # Convenience launcher (backend + frontend)
├── requirements.txt             # Python dependencies for tooling/scripts
├── ADVANCED_IMPLEMENTATION_WINDOWS.md # Windows setup guide
└── CLAUDE.md                    # AI assistant context
```

---

## Tech Stack

### Backend Services

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Web Framework | FastAPI | 0.104+ | High-performance async REST APIs |
| ASGI Server | Uvicorn | 0.24+ | Lightning-fast ASGI server |
| Metrics | prometheus_client | 0.18+ | Prometheus metrics exposition |
| HTTP Client | requests | 2.31+ | Service-to-service communication |
| K8s Client | kubernetes | 28.1+ | Kubernetes API interactions |
| ML | scikit-learn | 1.3+ | Anomaly detection models |
| Data | numpy | 1.26+ | Numerical computations |

### Frontend

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Framework | Next.js | 14.0+ | React framework with App Router |
| UI Library | React | 18.2+ | Component-based UI |
| Language | TypeScript | 5.2+ | Type-safe JavaScript |
| Charts | Recharts | 2.9+ | Data visualization |
| Real-time | Socket.IO Client | 4.7+ | WebSocket communication |
| Styling | Tailwind CSS | 3.3+ | Utility-first CSS |

### Infrastructure

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Container Runtime | Docker Desktop | 4.25+ | Container management |
| Orchestration | Kubernetes | 1.28+ | Container orchestration |
| Package Manager | Helm | 3.13+ | Kubernetes package manager |
| Monitoring | Prometheus | 2.47+ | Metrics collection |
| Visualization | Grafana | 10.2+ | Dashboards and alerts |

### Alerting Integrations

| Platform | Integration Type | Features |
|----------|-----------------|----------|
| Discord | Webhook | Rich embeds, color-coded severity |
| Slack | Webhook / Bot API | Blocks, buttons, threads |
| Custom | HTTP Webhook | JSON payloads |

---

## Prerequisites

### Required Software

| Software | Minimum Version | Download Link | Verification Command |
|----------|----------------|---------------|---------------------|
| Docker Desktop | 4.25+ | [docker.com/products/docker-desktop](https://docker.com/products/docker-desktop) | `docker --version` |
| kubectl | 1.28+ | [kubernetes.io/docs/tasks/tools](https://kubernetes.io/docs/tasks/tools/) | `kubectl version --client` |
| Helm | 3.13+ | [helm.sh/docs/intro/install](https://helm.sh/docs/intro/install/) | `helm version` |
| Python | 3.10+ | [python.org/downloads](https://python.org/downloads/) | `python --version` |
| Node.js | 18.0+ | [nodejs.org](https://nodejs.org/) | `node --version` |
| npm | 9.0+ | (included with Node.js) | `npm --version` |

### Enabling Kubernetes in Docker Desktop

1. Open Docker Desktop Settings
2. Navigate to **Kubernetes** tab
3. Check **Enable Kubernetes**
4. Click **Apply & Restart**
5. Wait for Kubernetes indicator to turn green
6. Verify: `kubectl cluster-info`

### Optional (Recommended for Windows)

| Software | Purpose | Download Link |
|----------|---------|---------------|
| PowerShell 7+ | Modern shell scripting | [github.com/PowerShell/PowerShell](https://github.com/PowerShell/PowerShell) |
| Windows Terminal | Better terminal experience | Microsoft Store |
| Visual Studio Code | IDE with K8s extensions | [code.visualstudio.com](https://code.visualstudio.com/) |

### Python Virtual Environment Setup

```powershell
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (Windows CMD)
.\.venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in repository root (same level as `requirements.txt`).

### Complete Environment Template

```env
# ════════════════════════════════════════════════════════════════════════════════
# KUBEGUARD ENVIRONMENT CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────────
# KUBERNETES CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────────
NAMESPACE=kubeguard
KUBECONFIG=~/.kube/config

# ─────────────────────────────────────────────────────────────────────────────────
# SERVICE URLS (Internal Communication)
# ─────────────────────────────────────────────────────────────────────────────────
# Baseline mode
MICROSERVICE_URL=http://localhost:30080

# Advanced mode
GATEWAY_URL=http://localhost:30081
CORE_SERVICE_URL=http://core-service:8001
WORKER_SERVICE_URL=http://worker-service:8002

# ─────────────────────────────────────────────────────────────────────────────────
# MONITORING ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────────
PROMETHEUS_URL=http://localhost:30090
GRAFANA_URL=http://localhost:30300

# ─────────────────────────────────────────────────────────────────────────────────
# DASHBOARD CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────────
DASHBOARD_PORT=9001
DASHBOARD_HOST=0.0.0.0

# ─────────────────────────────────────────────────────────────────────────────────
# DISCORD INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────────
# Primary webhook for general alerts
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Critical alerts channel (optional, falls back to primary)
DISCORD_CRITICAL_URL=https://discord.com/api/webhooks/...

# ─────────────────────────────────────────────────────────────────────────────────
# SLACK INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────────
# Option 1: Webhook (simpler setup)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Option 2: Bot API (richer features)
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C0123456789
SLACK_APP_ID=A0123456789

# ─────────────────────────────────────────────────────────────────────────────────
# WATCHER CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────────
CHECK_INTERVAL=5                    # Seconds between pod checks
ALERT_COOLDOWN=60                   # Seconds between duplicate alerts
RISK_THRESHOLD=50                   # Failure predictor threshold (0-100)

# ─────────────────────────────────────────────────────────────────────────────────
# ML ANOMALY DETECTOR
# ─────────────────────────────────────────────────────────────────────────────────
ML_CONTAMINATION=0.1                # Expected anomaly ratio (0.0-0.5)
ML_RETRAIN_INTERVAL=300             # Seconds between model retraining
ML_ANOMALY_THRESHOLD=-0.3           # IsolationForest score threshold
```

### Frontend Environment (`frontend/.env.local`)

```env
# ═══════════════════════════════════════════════════════════════════════════════
# KUBEGUARD FRONTEND CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Backend API URL (server-side)
KG_BACKEND_URL=http://localhost:9001

# Backend API URL (client-side, must be NEXT_PUBLIC_)
NEXT_PUBLIC_KG_BACKEND_URL=http://localhost:9001

# WebSocket configuration
NEXT_PUBLIC_KG_WS_URL=http://localhost:9001
NEXT_PUBLIC_KG_WS_PORT=9001

# Feature flags
NEXT_PUBLIC_ENABLE_CHAOS=true
NEXT_PUBLIC_ENABLE_ML=true
```

---

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

### Complete API Endpoint Documentation

#### Common Endpoints (All Services)

All services (`api-gateway`, `core-service`, `worker-service`, `microservice`) expose these common endpoints via the shared app factory:

| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/health` | GET | Kubernetes liveness probe | `{"status": "healthy", "service": "<name>", "timestamp": "..."}` |
| `/ready` | GET | Kubernetes readiness probe | `{"status": "ready", "service": "<name>", "timestamp": "..."}` |
| `/info` | GET | Service metadata | `{"service": "<name>", "version": "2.0.0", "uptime": <seconds>, "request_count": <int>}` |
| `/metrics` | GET | Prometheus metrics | Prometheus text format |
| `/crash` | GET | **Testing only** - Intentional crash | Process exits with code 1 |
| `/stress` | GET | **Testing only** - CPU stress (5s) | `{"status": "stress_complete", "duration": 5}` |
| `/oom` | GET | **Testing only** - Memory exhaustion | Process exits after allocating 1GB |

#### Example: Health Check Response

```json
{
  "status": "healthy",
  "service": "api-gateway",
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

#### Example: Info Response

```json
{
  "service": "api-gateway",
  "version": "2.0.0",
  "uptime": 3600.5,
  "request_count": 1234
}
```

---

### API Gateway Specific Endpoints

| Endpoint | Method | Parameters | Description |
|----------|--------|------------|-------------|
| `/api/process` | GET | `payload` (query) | Orchestrates request through core and worker services |
| `/api/health-all` | GET | - | Aggregates health from all downstream services |

#### Example: /api/process

```bash
curl "http://localhost:30081/api/process?payload=demo-data"
```

**Response:**
```json
{
  "gateway": "received",
  "payload": "demo-data",
  "core_result": {
    "service": "core-service",
    "processed": "demo-data",
    "processing_time_ms": 45
  },
  "worker_result": {
    "service": "worker-service",
    "job_id": "job-12345",
    "queued": true
  }
}
```

#### Example: /api/health-all

```bash
curl "http://localhost:30081/api/health-all"
```

**Response:**
```json
{
  "gateway": {"status": "healthy", "service": "api-gateway"},
  "core": {"status": "healthy", "service": "core-service"},
  "worker": {"status": "healthy", "service": "worker-service"}
}
```

---

### Core Service Specific Endpoints

| Endpoint | Method | Parameters | Description |
|----------|--------|------------|-------------|
| `/process` | GET | `payload` (query) | Processes payload data |

#### Example: /process

```bash
curl "http://core-service:8001/process?payload=sample-data"
```

**Response:**
```json
{
  "service": "core-service",
  "processed": "sample-data",
  "processing_time_ms": 23,
  "timestamp": "2024-01-15T10:30:00.456789"
}
```

---

### Worker Service Specific Endpoints

| Endpoint | Method | Parameters | Description |
|----------|--------|------------|-------------|
| `/enqueue` | GET | `job` (query, default: "default") | Enqueues a job for processing |
| `/queue-depth` | GET | - | Returns current queue depth |

#### Example: /enqueue

```bash
curl "http://worker-service:8002/enqueue?job=process-order-123"
```

**Response:**
```json
{
  "service": "worker-service",
  "job_id": "job-67890",
  "job_name": "process-order-123",
  "queued": true,
  "queue_depth": 5
}
```

#### Example: /queue-depth

```bash
curl "http://worker-service:8002/queue-depth"
```

**Response:**
```json
{
  "service": "worker-service",
  "queue_depth": 5,
  "processing": 2,
  "pending": 3
}
```

---

### Dashboard Backend API (`live_server.py` - Port 9001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/summary` | GET | Cluster summary with pod states and KPIs |
| `/api/integrations/status` | GET | Status of Discord/Slack integrations |
| `/api/actions/crash` | POST | Trigger a crash on random pod |
| `/api/integrations/test-discord` | POST | Send test message to Discord |
| `/api/integrations/test-slack` | POST | Send test message to Slack |

#### Example: /api/summary Response

```json
{
  "cluster": {
    "total_pods": 8,
    "running": 7,
    "pending": 1,
    "failed": 0,
    "restarts_total": 23
  },
  "pods": [
    {
      "name": "api-gateway-5d8f9-abc12",
      "status": "Running",
      "restarts": 2,
      "age": "2h15m",
      "ready": true
    }
  ],
  "kpis": {
    "requests_per_minute": 450,
    "error_rate": 0.02,
    "avg_latency_ms": 45,
    "memory_usage_mb": 256
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### Frontend Proxy Routes

The Next.js frontend proxies these routes to the backend dashboard:

| Frontend Route | Backend Target | Method |
|----------------|----------------|--------|
| `/api/summary` | `${KG_BACKEND_URL}/api/summary` | GET |
| `/api/status` | `${KG_BACKEND_URL}/api/integrations/status` | GET |
| `/api/trigger-crash` | `${KG_BACKEND_URL}/api/actions/crash` | POST |
| `/api/test-discord` | `${KG_BACKEND_URL}/api/integrations/test-discord` | POST |
| `/api/test-slack` | `${KG_BACKEND_URL}/api/integrations/test-slack` | POST |

---

## Prometheus Metrics Reference

### Metrics Exposed by All Services

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `http_requests_total` | Counter | `service`, `method`, `endpoint`, `status` | Total HTTP requests processed |
| `http_errors_total` | Counter | `service`, `error_type` | Total HTTP errors |
| `http_request_duration_seconds` | Histogram | `service`, `endpoint` | Request latency distribution |
| `service_uptime_seconds` | Gauge | `service` | Service uptime in seconds |
| `service_memory_mb` | Gauge | `service` | Memory usage in MB |
| `pod_crashes_total` | Counter | `service`, `reason` | Total pod crashes |

### Example Prometheus Queries

```promql
# Request rate per service (last 5 minutes)
rate(http_requests_total{namespace="kubeguard"}[5m])

# Error rate percentage
100 * rate(http_errors_total[5m]) / rate(http_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Total restarts across all pods
sum(kube_pod_container_status_restarts_total{namespace="kubeguard"})

# Memory usage trend
avg_over_time(service_memory_mb{namespace="kubeguard"}[1h])

# Pod availability
sum(kube_pod_status_ready{namespace="kubeguard"}) / count(kube_pod_status_ready{namespace="kubeguard"})
```

### Recording Rules (from `prometheus-rules-advanced.yaml`)

```yaml
# Pre-computed aggregations for dashboard performance
- record: kubeguard:http_requests:rate5m
  expr: sum(rate(http_requests_total{namespace="kubeguard"}[5m])) by (service)

- record: kubeguard:error_rate:ratio
  expr: sum(rate(http_errors_total{namespace="kubeguard"}[5m])) / sum(rate(http_requests_total{namespace="kubeguard"}[5m]))

- record: kubeguard:latency:p95
  expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{namespace="kubeguard"}[5m])) by (le, service))
```

---

## Chaos Engineering Workflows

### Overview

KubeGuard includes two chaos engineering tools for testing system resilience:

1. **Basic Chaos Monkey** (`chaos/chaos_monkey.py`) - Simple random pod deletion
2. **Advanced Chaos** (`chaos/advanced_chaos.py`) - Multi-modal failure injection

### Basic Chaos Monkey

```powershell
python chaos/chaos_monkey.py --mode high --duration 60
```

#### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--mode` | Chaos intensity level | `medium` |
| `--duration` | Total runtime in seconds | `300` |
| `--namespace` | Target Kubernetes namespace | `kubeguard` |
| `--dry-run` | Log actions without executing | `false` |

#### Intensity Modes

| Mode | Interval | Description |
|------|----------|-------------|
| `low` | 30 seconds | Light chaos, good for initial testing |
| `medium` | 15 seconds | Moderate chaos, standard resilience test |
| `high` | 5 seconds | Aggressive chaos, stress testing |

#### How It Works

```python
# Simplified logic from chaos_monkey.py
while time.time() < end_time:
    pods = get_running_pods(namespace)
    if pods:
        target = random.choice(pods)
        kubectl_delete_pod(target, force=True)
        log_incident(target)
    time.sleep(interval)
```

---

### Advanced Chaos Engineering

```powershell
python chaos/advanced_chaos.py --namespace kubeguard --mode random --duration 120
```

#### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--mode` | Attack mode | `random` |
| `--duration` | Total runtime in seconds | `300` |
| `--namespace` | Target Kubernetes namespace | `kubeguard` |
| `--target` | Specific pod pattern (regex) | `.*` |
| `--intensity` | Attack frequency | `medium` |

#### Attack Modes

| Mode | Description | Effect |
|------|-------------|--------|
| `delete` | Force-delete random pod | Immediate pod termination |
| `oom` | Invoke `/oom` endpoint | Memory exhaustion + crash |
| `cpu` | Invoke `/stress` endpoint | CPU spike for 5 seconds |
| `cascade` | Delete 3+ pods rapidly | Simulates cascading failure |
| `random` | Random selection of above | Unpredictable chaos |

#### Example: Targeted Chaos

```powershell
# Only target api-gateway pods
python chaos/advanced_chaos.py --mode cpu --target "api-gateway.*" --duration 60

# Cascade failure on worker pods
python chaos/advanced_chaos.py --mode cascade --target "worker-service.*"
```

#### Attack Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ADVANCED CHAOS ENGINE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │  DELETE  │    │   OOM    │    │   CPU    │    │ CASCADE  │     │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘     │
│       │               │               │               │           │
│       ▼               ▼               ▼               ▼           │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   TARGET SELECTOR                            │  │
│  │  • Get pods from namespace                                   │  │
│  │  • Filter by --target regex                                  │  │
│  │  • Select random victim(s)                                   │  │
│  └───────────────────────┬─────────────────────────────────────┘  │
│                          │                                        │
│                          ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   ATTACK EXECUTOR                            │  │
│  │  • DELETE: kubectl delete pod --force --grace-period=0      │  │
│  │  • OOM: curl http://<pod-ip>:8000/oom                        │  │
│  │  • CPU: curl http://<pod-ip>:8000/stress (concurrent)        │  │
│  │  • CASCADE: Rapid multi-pod deletion                         │  │
│  └───────────────────────┬─────────────────────────────────────┘  │
│                          │                                        │
│                          ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   INCIDENT LOGGER                            │  │
│  │  • Log attack type, target, timestamp                        │  │
│  │  • Update metrics counters                                   │  │
│  │  • Optional: Send Discord/Slack notification                 │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Resilience Testing Scenarios

#### Scenario 1: Basic Pod Recovery

```powershell
# Terminal 1: Watch pods
kubectl get pods -n kubeguard -w

# Terminal 2: Run basic chaos
python chaos/chaos_monkey.py --mode medium --duration 120

# Expected: Pods restart within 10-30 seconds
# HPA may scale up if sustained load
```

#### Scenario 2: Stress Under Load

```powershell
# Terminal 1: Generate load
for i in {1..100}; do curl -s http://localhost:30081/api/process?payload=test$i & done

# Terminal 2: Run CPU stress
python chaos/advanced_chaos.py --mode cpu --duration 60

# Expected: Latency spikes, then recovery
# Dashboard shows increased latency_ms
```

#### Scenario 3: Cascade Failure Recovery

```powershell
# Delete multiple pods simultaneously
python chaos/advanced_chaos.py --mode cascade --duration 30

# Expected: PDB prevents complete outage
# At least minAvailable pods remain
# Full recovery within 60 seconds
```

---

## Watchers, Operator, and ML

### Overview

KubeGuard includes three monitoring components:

| Component | File | Purpose |
|-----------|------|---------|
| Crash Watcher | `watcher/crash_watcher.py` | Poll-based crash detection |
| Failure Predictor | `watcher/failure_predictor.py` | Prometheus-based risk scoring |
| Operator Controller | `watcher/operator_controller.py` | Event-driven auto-remediation |

---

### Crash Watcher

The crash watcher polls Kubernetes for pod state changes and sends Discord alerts.

```powershell
python watcher/crash_watcher.py
```

#### Configuration

```python
# Environment variables
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "5"))
NAMESPACE = os.getenv("NAMESPACE", "kubeguard")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
```

#### Detection Logic

```python
# Simplified detection algorithm
for pod in current_pods:
    previous = pod_states.get(pod.name)
    current_restarts = pod.status.container_statuses[0].restart_count
    
    if previous is None:
        # New pod discovered
        pod_states[pod.name] = current_restarts
    elif current_restarts > previous:
        # CRASH DETECTED
        delta = current_restarts - previous
        send_discord_alert(pod.name, delta, current_restarts)
        pod_states[pod.name] = current_restarts
    elif pod.status.phase == "Running" and previous.phase != "Running":
        # RECOVERY DETECTED
        send_recovery_alert(pod.name)
```

#### Discord Alert Format

```json
{
  "embeds": [{
    "title": "🚨 Pod Crash Detected",
    "color": 16711680,
    "fields": [
      {"name": "Pod", "value": "api-gateway-5d8f9-abc12", "inline": true},
      {"name": "Restarts", "value": "3 (+1)", "inline": true},
      {"name": "Namespace", "value": "kubeguard", "inline": true}
    ],
    "timestamp": "2024-01-15T10:30:00Z"
  }]
}
```

---

### Failure Predictor

The failure predictor queries Prometheus metrics and calculates risk scores.

```powershell
python watcher/failure_predictor.py
```

#### Risk Score Calculation

```python
def calculate_risk_score(pod_name: str) -> float:
    # Query Prometheus for restart metrics
    total_restarts = query_prometheus(
        f'kube_pod_container_status_restarts_total{{pod="{pod_name}"}}'
    )
    
    # Calculate restart acceleration (restarts per minute)
    restart_rate = query_prometheus(
        f'rate(kube_pod_container_status_restarts_total{{pod="{pod_name}"}}[5m])'
    )
    
    # Risk formula: base_risk + acceleration_factor
    base_risk = min(total_restarts * 10, 50)  # Max 50 from total restarts
    acceleration = min(restart_rate * 100, 50)  # Max 50 from rate
    
    return base_risk + acceleration  # 0-100 scale
```

#### Risk Levels

| Score Range | Level | Action |
|-------------|-------|--------|
| 0-25 | LOW | No action |
| 26-50 | MODERATE | Log warning |
| 51-75 | HIGH | Send alert |
| 76-100 | CRITICAL | Alert + remediation consideration |

---

### Operator Controller

The operator controller watches Kubernetes events in real-time and takes remediation actions.

```powershell
python watcher/operator_controller.py
```

#### Event Processing

```python
def process_event(event: dict):
    event_type = event["type"]  # ADDED, MODIFIED, DELETED
    pod = event["object"]
    
    if event_type == "MODIFIED":
        if is_crash_loop_backoff(pod):
            handle_crash_loop(pod)
        elif is_oom_killed(pod):
            handle_oom_kill(pod)
        elif is_unhealthy(pod):
            handle_unhealthy(pod)
```

#### Remediation Strategies

| Condition | Detection | Remediation |
|-----------|-----------|-------------|
| CrashLoopBackOff | `waiting.reason == "CrashLoopBackOff"` | Delete pod (force K8s reschedule) |
| OOMKilled | `terminated.reason == "OOMKilled"` | Log + alert (may need resource adjustment) |
| Unhealthy | Failed readiness probe | Soft restart via endpoint or delete |
| Stuck Terminating | `deletionTimestamp` > 5 min | Force delete |

#### Auto-Remediation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OPERATOR CONTROLLER                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐                                                  │
│  │  K8s Watch   │◀─── watch.stream(v1.list_namespaced_pod, ...)    │
│  │   Stream     │                                                  │
│  └──────┬───────┘                                                  │
│         │                                                          │
│         │ Event: ADDED/MODIFIED/DELETED                            │
│         ▼                                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    EVENT CLASSIFIER                          │  │
│  │  • Check container statuses                                  │  │
│  │  • Identify crash patterns                                   │  │
│  │  • Calculate severity                                        │  │
│  └──────────────────────┬───────────────────────────────────────┘  │
│                         │                                          │
│         ┌───────────────┼───────────────┐                         │
│         │               │               │                         │
│         ▼               ▼               ▼                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                   │
│  │ CrashLoop  │  │  OOMKill   │  │ Unhealthy  │                   │
│  │  Handler   │  │  Handler   │  │  Handler   │                   │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                   │
│        │               │               │                          │
│        └───────────────┼───────────────┘                          │
│                        ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    REMEDIATION ENGINE                        │  │
│  │  1. Log incident to memory store                             │  │
│  │  2. Execute remediation (delete/restart)                     │  │
│  │  3. Send Discord/Slack notification                          │  │
│  │  4. Update metrics counters                                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Machine Learning Anomaly Detection

### Overview

The ML anomaly detector (`ml/anomaly_detector.py`) uses IsolationForest to identify pods with unusual behavior patterns.

```powershell
python ml/anomaly_detector.py
```

### Feature Engineering

| Feature | Source | Description |
|---------|--------|-------------|
| `restarts` | Prometheus | Total restart count |
| `restart_delta` | Prometheus | Restarts in last 5 minutes |
| `mem_percent` | Prometheus | Memory usage percentage |
| `cpu_rate` | Prometheus | CPU utilization rate |
| `interaction_term` | Computed | `restarts * restart_delta` |

### Feature Extraction Code

```python
def extract_features(pod_name: str) -> np.ndarray:
    restarts = query_prometheus(
        f'kube_pod_container_status_restarts_total{{pod=~"{pod_name}"}}'
    )
    restart_delta = query_prometheus(
        f'delta(kube_pod_container_status_restarts_total{{pod=~"{pod_name}"}}[5m])'
    )
    mem_percent = query_prometheus(
        f'container_memory_usage_bytes{{pod=~"{pod_name}"}} / container_spec_memory_limit_bytes'
    )
    cpu_rate = query_prometheus(
        f'rate(container_cpu_usage_seconds_total{{pod=~"{pod_name}"}}[5m])'
    )
    
    interaction = restarts * restart_delta
    
    return np.array([restarts, restart_delta, mem_percent, cpu_rate, interaction])
```

### Model Configuration

```python
from sklearn.ensemble import IsolationForest

model = IsolationForest(
    contamination=0.1,      # Expect ~10% anomalies
    n_estimators=100,       # Number of trees
    max_samples='auto',     # Auto-select sample size
    random_state=42         # Reproducibility
)
```

### Anomaly Detection Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ML ANOMALY DETECTOR                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    DATA COLLECTION                             │ │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │ │
│  │  │  Prometheus  │───▶│   Feature    │───▶│   Feature    │     │ │
│  │  │   Queries    │    │  Extraction  │    │   Vectors    │     │ │
│  │  └──────────────┘    └──────────────┘    └──────────────┘     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                │                                    │
│                                ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    MODEL TRAINING                              │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  IsolationForest(contamination=0.1, n_estimators=100)    │  │ │
│  │  │  • Builds 100 random trees                               │  │ │
│  │  │  • Isolates anomalies via shorter paths                  │  │ │
│  │  │  • Retrains every 5 minutes                              │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                │                                    │
│                                ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    INFERENCE                                   │ │
│  │  for each pod:                                                 │ │
│  │    score = model.decision_function(features)                   │ │
│  │    if score < -0.3:  # ANOMALY THRESHOLD                       │ │
│  │      flag_as_anomalous(pod)                                    │ │
│  │      send_alert(pod, score, features)                          │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Anomaly Score Interpretation

| Score | Interpretation | Action |
|-------|---------------|--------|
| > 0 | Normal behavior | None |
| -0.1 to 0 | Slightly unusual | Monitor |
| -0.3 to -0.1 | Suspicious | Warning alert |
| < -0.3 | **ANOMALY** | Critical alert |

### Example Alert Output

```
[2024-01-15 10:30:00] ANOMALY DETECTED
Pod: worker-service-7b8c9-xyz99
Score: -0.45
Features:
  - restarts: 12
  - restart_delta: 5
  - mem_percent: 0.95
  - cpu_rate: 0.82
  - interaction: 60
Recommendation: Investigate memory pressure and restart pattern
```

---

## Kubernetes Resource Specifications

### Deployment Specifications

#### API Gateway Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: kubeguard
  labels:
    app: api-gateway
    team: s8ul
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
        team: s8ul
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: api-gateway
        image: kubeguard-api-gateway:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
        env:
        - name: SERVICE_NAME
          value: "api-gateway"
        - name: CORE_SERVICE_URL
          value: "http://core-service:8001"
        - name: WORKER_SERVICE_URL
          value: "http://worker-service:8002"
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
```

### Resource Quotas by Service

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | Replicas |
|---------|------------|-----------|----------------|--------------|----------|
| api-gateway | 100m | 500m | 128Mi | 256Mi | 3 |
| core-service | 100m | 500m | 128Mi | 256Mi | 3 |
| worker-service | 100m | 500m | 128Mi | 256Mi | 2 |

### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: kubeguard
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 25
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
```

### HPA Configuration by Service

| Service | Min Replicas | Max Replicas | CPU Target | Memory Target |
|---------|-------------|--------------|------------|---------------|
| api-gateway | 3 | 10 | 70% | 80% |
| core-service | 3 | 8 | 70% | 80% |
| worker-service | 2 | 6 | 70% | 80% |

### Pod Disruption Budget (PDB)

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway-pdb
  namespace: kubeguard
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api-gateway
```

### PDB Configuration by Service

| Service | minAvailable | Purpose |
|---------|-------------|---------|
| api-gateway | 2 | Ensure 2+ pods during voluntary disruptions |
| core-service | 2 | Maintain processing capacity |
| worker-service | 1 | At least 1 worker always available |

---

## Network Policies & Security

### Default Deny Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: kubeguard
spec:
  podSelector: {}
  policyTypes:
  - Ingress
```

### Allow Gateway External Access

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-gateway-ingress
  namespace: kubeguard
spec:
  podSelector:
    matchLabels:
      app: api-gateway
  policyTypes:
  - Ingress
  ingress:
  - from: []
    ports:
    - protocol: TCP
      port: 8000
```

### Allow Gateway to Internal Services

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-gateway-to-internal
  namespace: kubeguard
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/part-of: kubeguard-internal
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway
    ports:
    - protocol: TCP
      port: 8001
    - protocol: TCP
      port: 8002
```

### Allow Prometheus Scraping

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-prometheus-scrape
  namespace: kubeguard
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 8000
    - protocol: TCP
      port: 8001
    - protocol: TCP
      port: 8002
```

### RBAC Configuration

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: kubeguard-controller
  namespace: kubeguard
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: kubeguard-controller-role
  namespace: kubeguard
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch", "delete"]
- apiGroups: [""]
  resources: ["events"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: kubeguard-controller-binding
  namespace: kubeguard
subjects:
- kind: ServiceAccount
  name: kubeguard-controller
  namespace: kubeguard
roleRef:
  kind: Role
  name: kubeguard-controller-role
  apiGroup: rbac.authorization.k8s.io
```

---

## Alerting Configuration

### Prometheus Alert Rules

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: kubeguard-alerts
  namespace: monitoring
spec:
  groups:
  - name: kubeguard.rules
    rules:
    - alert: HighRestartRate
      expr: |
        rate(kube_pod_container_status_restarts_total{namespace="kubeguard"}[5m]) > 0.1
      for: 2m
      labels:
        severity: warning
        team: s8ul
      annotations:
        summary: "High restart rate detected"
        description: "Pod {{ $labels.pod }} has restarted more than expected"

    - alert: PodCrashLooping
      expr: |
        kube_pod_container_status_waiting_reason{namespace="kubeguard", reason="CrashLoopBackOff"} == 1
      for: 5m
      labels:
        severity: critical
        team: s8ul
      annotations:
        summary: "Pod in CrashLoopBackOff"
        description: "Pod {{ $labels.pod }} is crash looping"

    - alert: HighErrorRate
      expr: |
        rate(http_errors_total{namespace="kubeguard"}[5m]) / rate(http_requests_total{namespace="kubeguard"}[5m]) > 0.05
      for: 5m
      labels:
        severity: warning
        team: s8ul
      annotations:
        summary: "High error rate detected"
        description: "Error rate is above 5% for service {{ $labels.service }}"

    - alert: HighLatency
      expr: |
        histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{namespace="kubeguard"}[5m])) > 1
      for: 5m
      labels:
        severity: warning
        team: s8ul
      annotations:
        summary: "High latency detected"
        description: "95th percentile latency is above 1 second"

    - alert: LowPodAvailability
      expr: |
        sum(kube_pod_status_ready{namespace="kubeguard", condition="true"}) / count(kube_pod_status_ready{namespace="kubeguard"}) < 0.7
      for: 2m
      labels:
        severity: critical
        team: s8ul
      annotations:
        summary: "Low pod availability"
        description: "Less than 70% of pods are ready"
```

### Alertmanager Configuration

```yaml
# k8s/alertmanager-advanced.yml
global:
  slack_api_url: 'https://hooks.slack.com/services/...'
  
route:
  receiver: 'default-receiver'
  group_by: ['alertname', 'namespace', 'pod']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
  - match:
      severity: critical
    receiver: 'critical-alerts'
    continue: true
  - match:
      severity: warning
    receiver: 'warning-alerts'

receivers:
- name: 'default-receiver'
  webhook_configs:
  - url: 'http://dashboard-service:9001/api/alerts/webhook'

- name: 'critical-alerts'
  slack_configs:
  - channel: '#kubeguard-critical'
    send_resolved: true
    title: '🚨 CRITICAL: {{ .GroupLabels.alertname }}'
    text: |
      {{ range .Alerts }}
      *Pod:* {{ .Labels.pod }}
      *Description:* {{ .Annotations.description }}
      {{ end }}
  webhook_configs:
  - url: '${DISCORD_CRITICAL_URL}'

- name: 'warning-alerts'
  slack_configs:
  - channel: '#kubeguard-alerts'
    send_resolved: true
    title: '⚠️ WARNING: {{ .GroupLabels.alertname }}'
    text: |
      {{ range .Alerts }}
      *Pod:* {{ .Labels.pod }}
      *Description:* {{ .Annotations.description }}
      {{ end }}
```

---

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

---

<p align="center">
  <strong>Built with ❤️ by Team S8UL</strong>
</p>#   K u b e G u a r d 
 
 