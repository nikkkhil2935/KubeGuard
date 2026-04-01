#!/usr/bin/env python3
"""KubeGuard Failure Predictor - Predicts crashes from Prometheus metrics."""
import requests, time, os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from colorama import Fore, Style, init


init(autoreset=True)
ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ROOT_ENV)


PROMETHEUS = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
DISCORD    = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip()
NAMESPACE  = os.getenv("NAMESPACE", "kubeguard")
INTERVAL   = 30


prev_restarts = {}
warned = set()


def query(q):
    try:
        r = requests.get(f"{PROMETHEUS}/api/v1/query", params={"query":q}, timeout=5)
        data = r.json()
        if data["status"] == "success": return data["data"]["result"]
    except: pass
    return []


def risk_score(pod, restarts):
    score, reasons = 0, []
    prev = prev_restarts.get(pod, 0)
    delta = restarts - prev
    if restarts > 5:
        score += 30; reasons.append(f"High total restarts ({int(restarts)})")
    if delta > 2:
        score += 40; reasons.append(f"Rapid restart acceleration (+{delta} in {INTERVAL}s)")
    elif delta > 0:
        score += 20; reasons.append(f"New restart detected (+{delta})")
    return min(score, 100), reasons


def send_warning(pod, score, reasons):
    if not DISCORD or pod in warned: return
    embed = {
        "title": "Failure Predicted",
        "color": 16744272,
        "fields": [
            {"name":"Pod","value":f"`{pod}`","inline":True},
            {"name":"Risk Score","value":f"**{score}/100**","inline":True},
            {"name":"Namespace","value":f"`{NAMESPACE}`","inline":True},
            {"name":"Signals","value":"\n".join(f"- {r}" for r in reasons),"inline":False},
            {"name":"Action","value":"Monitor closely. Consider manual restart.","inline":False},
        ],
        "footer":{"text":"KubeGuard Failure Predictor - Team S8UL"},
        "timestamp": datetime.utcnow().isoformat()
    }
    try:
        r = requests.post(DISCORD, json={"username":"KubeGuard Predictor","embeds":[embed]}, timeout=5)
        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        print(f"{Fore.YELLOW}[WARN] Discord warning sent for {pod} (risk={score}){Style.RESET_ALL}")
        warned.add(pod)
    except Exception as e:
        print(f"{Fore.RED}Discord failed: {e}{Style.RESET_ALL}")


def run():
    print(f"{Fore.CYAN}Failure Predictor STARTED | prometheus={PROMETHEUS}{Style.RESET_ALL}")
    while True:
        print(f"\n{Fore.BLUE}[{datetime.now().strftime('%H:%M:%S')}] Analyzing...{Style.RESET_ALL}")
        results = query(f'kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}"}}')
        if not results:
            print(f"{Fore.YELLOW}No data from Prometheus. Is it port-forwarded?{Style.RESET_ALL}")
        else:
            print(f"  {'POD':<45} {'RESTARTS':>10} {'RISK':>8} STATUS")
            print(f"  {'-'*75}")
            for r in results:
                pod = r["metric"].get("pod","?")
                restarts = float(r["value"][1])
                score, reasons = risk_score(pod, restarts)
                if score >= 60:
                    c, status = Fore.RED, "HIGH RISK"
                    send_warning(pod, score, reasons)
                elif score >= 20:
                    c, status = Fore.YELLOW, "MEDIUM"
                else:
                    c, status = Fore.GREEN, "HEALTHY"
                    warned.discard(pod)
                print(f"  {c}{pod:<45} {int(restarts):>10} {score:>7}%  {status}{Style.RESET_ALL}")
        prev_restarts.update({r["metric"].get("pod","?"):float(r["value"][1]) for r in results})
        time.sleep(INTERVAL)


if __name__ == "__main__": run()
