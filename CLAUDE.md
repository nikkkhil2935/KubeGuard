# KubeGuard Project

## Stack
- **Microservice**: Python FastAPI + uvicorn + prometheus_client
- **Container**: Docker Desktop
- **Orchestration**: Kubernetes (Docker Desktop built-in)
- **Monitoring**: Prometheus + Grafana (via Helm)
- **Alerting**: Discord Webhooks
- **Chaos Testing**: Custom Python ChaosMonkey

## Key Commands
```bash
# Build microservice
docker build -t kubeguard-microservice:latest ./microservice

# Deploy to K8s
kubectl apply -f k8s/

# Watch pods
kubectl get pods -n kubeguard -w

# Test crash
curl http://localhost:30080/crash

# Run CrashWatcher
python watcher/crash_watcher.py

# Run Chaos Monkey
python chaos/chaos_monkey.py --mode high --duration 60
```

## Conventions
- All K8s resources in `kubeguard` namespace
- 3 replicas for redundancy
- Liveness probe: /health every 5s
- Discord alerts within 10s of crash
- Team label: `team: s8ul`

## Critical Files
- `microservice/app.py` - FastAPI endpoints
- `k8s/deployment.yaml` - Pod spec with probes
- `watcher/crash_watcher.py` - Discord alerting
- `chaos/chaos_monkey.py` - Resilience testing
- `.env` - Discord webhook URL
