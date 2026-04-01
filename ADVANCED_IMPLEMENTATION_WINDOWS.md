# KubeGuard Advanced v2.0 (Windows)

This runbook upgrades the current repository to a 3-service KubeGuard stack with operator, ML anomaly detection, advanced chaos, and live dashboards.

## What Was Added

- `api-gateway/`, `core-service/`, `worker-service/` with FastAPI apps, Prometheus metrics, Dockerfiles.
- Advanced Kubernetes manifests:
  - `k8s/namespace-rbac.yaml`
  - `k8s/deployments-advanced.yaml`
  - `k8s/services-advanced.yaml`
  - `k8s/hpa-advanced.yaml`
  - `k8s/pdb-advanced.yaml`
  - `k8s/networkpolicy-advanced.yaml`
  - `k8s/servicemonitors-advanced.yaml`
  - `k8s/prometheus-rules-advanced.yaml`
  - `k8s/alertmanager-advanced.yml`
- New control-plane scripts:
  - `watcher/operator_controller.py`
  - `ml/anomaly_detector.py`
  - `chaos/advanced_chaos.py`
  - `dashboard/live_server.py`

## 0) One-Time Setup

```powershell
minikube start --cpus=4 --memory=8g --driver=docker
minikube addons enable metrics-server
minikube addons enable ingress

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

python -m pip install -r requirements.txt
```

## 1) Build Images Into Minikube Docker

```powershell
minikube docker-env | Invoke-Expression

docker build -t kubeguard-api-gateway:latest ./api-gateway
docker build -t kubeguard-core-service:latest ./core-service
docker build -t kubeguard-worker-service:latest ./worker-service
```

## 2) Deploy Advanced Kubernetes Stack

```powershell
kubectl apply -f k8s/namespace-rbac.yaml
kubectl apply -f k8s/deployments-advanced.yaml
kubectl apply -f k8s/services-advanced.yaml
kubectl apply -f k8s/hpa-advanced.yaml
kubectl apply -f k8s/pdb-advanced.yaml
kubectl apply -f k8s/networkpolicy-advanced.yaml
```

Validate:

```powershell
kubectl get all -n kubeguard
kubectl get hpa -n kubeguard
kubectl get pdb -n kubeguard
```

## 3) Install Monitoring (Prometheus + Grafana)

```powershell
helm install prometheus prometheus-community/kube-prometheus-stack `
  --namespace monitoring --create-namespace `
  --set prometheus.prometheusSpec.scrapeInterval=10s `
  --set grafana.adminPassword=kubeguard123 `
  --set grafana.service.type=NodePort `
  --set grafana.service.nodePort=30300 `
  --wait --timeout 6m

kubectl apply -f k8s/servicemonitors-advanced.yaml
kubectl apply -f k8s/prometheus-rules-advanced.yaml
```

## 4) Run Operator + ML + Dashboard

Use separate terminals:

```powershell
python watcher/operator_controller.py
```

```powershell
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```

```powershell
python ml/anomaly_detector.py
```

```powershell
python dashboard/live_server.py
```

Open `http://localhost:9001`.

## 5) Demo Chaos

```powershell
python chaos/advanced_chaos.py --namespace kubeguard --mode cascade --duration 30
python chaos/advanced_chaos.py --namespace kubeguard --mode cpu --duration 45
python chaos/advanced_chaos.py --namespace kubeguard --mode random --duration 60
```

Gateway URL:

```powershell
$GW = minikube service api-gateway -n kubeguard --url
curl "$GW/api/health-all"
curl "$GW/crash"
```

## Notes

- Replace `DISCORD_CRITICAL_URL` in `.env` with your real critical webhook.
- For Alertmanager webhook routing, update placeholders in `k8s/alertmanager-advanced.yml` and create secret if needed.
- Keep existing original KubeGuard files; this advanced stack is additive and uses `*-advanced.yaml` manifests.
