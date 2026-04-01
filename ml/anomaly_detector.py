#!/usr/bin/env python3
"""KubeGuard ML - IsolationForest anomaly detection on Prometheus metrics."""
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
from colorama import Fore, Style, init
from dotenv import load_dotenv
from sklearn.ensemble import IsolationForest


init(autoreset=True)
ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ROOT_ENV)

PROMETHEUS = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
DISCORD = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip()
NAMESPACE = os.getenv("NAMESPACE", "kubeguard")
INTERVAL = 30

model = IsolationForest(contamination=0.1, random_state=42)
training_data = []
model_trained = False
prev_restarts = {}
warned_pods = set()


def prom_query_map(query: str):
    try:
        r = requests.get(f"{PROMETHEUS}/api/v1/query", params={"query": query}, timeout=5)
        payload = r.json()
        if payload.get("status") == "success":
            return {m["metric"].get("pod", "?"): float(m["value"][1]) for m in payload["data"]["result"]}
    except Exception as e:
        print(f"{Fore.RED}Prometheus error: {e}{Style.RESET_ALL}")
    return {}


def get_all_pods():
    data = prom_query_map(f'kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}"}}')
    return list(data.keys())


def get_features(pod):
    restarts = prom_query_map(
        f'kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}",pod="{pod}"}}'
    ).get(pod, 0.0)
    mem_usage = prom_query_map(
        f'container_memory_usage_bytes{{namespace="{NAMESPACE}",pod="{pod}"}}'
    ).get(pod, 0.0)
    mem_limit = prom_query_map(
        f'kube_pod_container_resource_limits{{namespace="{NAMESPACE}",pod="{pod}",resource="memory",unit="byte"}}'
    ).get(pod, 0.0)
    cpu_rate = prom_query_map(
        f'rate(container_cpu_usage_seconds_total{{namespace="{NAMESPACE}",pod="{pod}"}}[2m])'
    ).get(pod, 0.0)

    prev_r = prev_restarts.get(pod, restarts)
    restart_delta = restarts - prev_r
    # On some clusters, cadvisor limit metrics are missing; keep feature stable.
    mem_pct = (mem_usage / mem_limit) if mem_limit > 0 else 0.0
    prev_restarts[pod] = restarts

    return np.array([restarts, restart_delta, mem_pct, cpu_rate, restarts * restart_delta], dtype=float)


def send_anomaly_alert(pod, score, features):
    if not DISCORD or pod in warned_pods:
        return

    restarts, delta, mem_pct, cpu_rate, _ = features.tolist()
    payload = {
        "username": "KubeGuard ML",
        "embeds": [
            {
                "title": "ML Anomaly Detected",
                "color": 16744272,
                "description": f"IsolationForest flagged `{pod}` as anomalous.",
                "fields": [
                    {"name": "Anomaly Score", "value": f"{score:.3f}", "inline": True},
                    {"name": "Pod", "value": f"`{pod}`", "inline": True},
                    {"name": "Namespace", "value": f"`{NAMESPACE}`", "inline": True},
                    {"name": "Restart Count", "value": str(int(restarts)), "inline": True},
                    {"name": "Restart Delta", "value": str(int(delta)), "inline": True},
                    {"name": "Memory", "value": f"{mem_pct * 100:.1f}%", "inline": True},
                    {"name": "CPU Rate", "value": f"{cpu_rate:.4f}", "inline": True},
                ],
                "footer": {"text": "KubeGuard ML v2.0 - Team S8UL"},
                "timestamp": datetime.utcnow().isoformat(),
            }
        ],
    }

    try:
        resp = requests.post(DISCORD, json=payload, timeout=5)
        if resp.status_code < 200 or resp.status_code >= 300:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        warned_pods.add(pod)
        print(f"{Fore.YELLOW}[ML] Alert sent for {pod}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Discord error: {e}{Style.RESET_ALL}")


def run():
    global model_trained
    print(f"{Fore.MAGENTA}KubeGuard ML detector started | prometheus={PROMETHEUS}{Style.RESET_ALL}")
    run_count = 0

    while True:
        pods = get_all_pods()
        if not pods:
            print(f"{Fore.YELLOW}No pod metrics yet. Check Prometheus port-forward.{Style.RESET_ALL}")
            time.sleep(INTERVAL)
            continue

        pod_features = {}
        for pod in pods:
            features = get_features(pod)
            pod_features[pod] = features
            training_data.append(features)

        if len(training_data) > 1000:
            training_data.pop(0)

        if len(training_data) >= len(pods) * 3 and not model_trained:
            model.fit(np.array(training_data))
            model_trained = True
            print(f"{Fore.CYAN}[ML] Model trained on {len(training_data)} samples{Style.RESET_ALL}")

        if model_trained and run_count > 0 and run_count % 20 == 0:
            model.fit(np.array(training_data[-500:]))
            print(f"{Fore.CYAN}[ML] Model retrained at run {run_count}{Style.RESET_ALL}")

        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n{Fore.MAGENTA}[{now}] ML analysis (trained={model_trained}){Style.RESET_ALL}")
        print(f"  {'POD':<48} {'SCORE':>8} {'RESTARTS':>10} {'MEM%':>8} STATUS")
        print(f"  {'-' * 82}")

        for pod, features in pod_features.items():
            if model_trained:
                score = model.score_samples(features.reshape(1, -1))[0]
                is_anomaly = score < -0.3
            else:
                score = 0.0
                is_anomaly = features[0] > 5 or features[1] > 2

            restarts, _, mem_pct, _, _ = features.tolist()
            status = "ANOMALY" if is_anomaly else ("RISK" if restarts > 2 else "NORMAL")
            color = Fore.RED if is_anomaly else (Fore.YELLOW if restarts > 2 else Fore.GREEN)
            print(f"  {color}{pod:<48} {score:>8.3f} {int(restarts):>10} {mem_pct * 100:>7.1f}%  {status}{Style.RESET_ALL}")

            if is_anomaly:
                send_anomaly_alert(pod, score, features)
            else:
                warned_pods.discard(pod)

        run_count += 1
        time.sleep(INTERVAL)


if __name__ == "__main__":
    run()
