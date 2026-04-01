#!/usr/bin/env python3
"""KubeGuard CrashWatcher - Detects crashes/restarts and fires Discord alerts."""
import subprocess, json, time, os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import requests
from colorama import Fore, Style, init


init(autoreset=True)
ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ROOT_ENV)


DISCORD_WEBHOOK = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip()
NAMESPACE       = os.getenv("NAMESPACE", "kubeguard")
INTERVAL        = int(os.getenv("CHECK_INTERVAL", "5"))
CRASH_REASONS   = {"CrashLoopBackOff","Error","OOMKilled","ImagePullBackOff"}


# State cache: {pod_name: {status, restarts, alerted}}
cache = {}


def get_pods():
    r = subprocess.run(["kubectl","get","pods","-n",NAMESPACE,"-o","json"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "kubectl get pods failed").strip())
    try:
        return json.loads(r.stdout).get("items", [])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid pod JSON from kubectl: {e}") from e


def parse_pod(pod):
    name = pod["metadata"]["name"]
    cs   = pod["status"].get("containerStatuses", [])
    if not cs: return name, "Pending", 0, None
    c = cs[0]; restarts = c.get("restartCount", 0)
    state = c.get("state", {})
    if "waiting" in state:
        reason = state["waiting"].get("reason","Unknown")
        return name, reason, restarts, state["waiting"].get("message","")
    if "running" in state:
        return name, "Running" if c.get("ready") else "NotReady", restarts, None
    return name, "Terminated", restarts, None


def discord_alert(pod, status, restarts, msg=None, recovered=False, restart_delta=0):
    if not DISCORD_WEBHOOK: return
    if recovered:
        color, title = 65280, "Pod Recovered"
    elif restart_delta > 0 and status not in CRASH_REASONS:
        color, title = 16744272, "Pod Restart Detected"
    elif status in CRASH_REASONS:
        color, title = 16711680, "Pod Crash Detected"
    else:
        color, title = 16744272, "Pod Unhealthy"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = {
        "username": "KubeGuard Shield",
        "embeds": [{"title": title, "color": color, "fields": [
            {"name":"Pod","value":f"`{pod}`","inline":True},
            {"name":"Status","value":f"`{status}`","inline":True},
            {"name":"Restarts","value":str(restarts),"inline":True},
            {"name":"Restart Delta","value":f"+{restart_delta}","inline":True},
            {"name":"Namespace","value":f"`{NAMESPACE}`","inline":True},
            {"name":"Time","value":ts,"inline":True},
            {"name":"Action","value":"Auto-restarting via K8s" if not recovered else "Healthy","inline":True},
        ], "footer":{"text":"KubeGuard Self-Healing System - Team S8UL"}}]
    }
    if msg: payload["embeds"][0]["fields"].append({"name":"Detail","value":f"```{msg[:200]}```","inline":False})
    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=5)
        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        print(f"{Fore.CYAN}[Discord] Sent: {pod} -> {status}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[Discord] FAIL: {e}{Style.RESET_ALL}")


def run():
    print(f"{Fore.GREEN}KubeGuard CrashWatcher STARTED | ns={NAMESPACE} | interval={INTERVAL}s{Style.RESET_ALL}")
    if DISCORD_WEBHOOK:
        print(f"{Fore.CYAN}[Discord] Webhook configured{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}[Discord] Webhook not configured; alerts disabled{Style.RESET_ALL}")

    first_pass = True
    while True:
        try:
            for pod in get_pods():
                name, status, restarts, msg = parse_pod(pod)
                prev = cache.get(name, {"status":"Running","restarts":0,"alerted":False})
                restart_delta = max(0, restarts - prev["restarts"])
                crashed  = status in CRASH_REASONS
                new_crash = crashed and not prev["alerted"]
                recovered = not crashed and prev["status"] in CRASH_REASONS
                clr = Fore.RED if crashed else (Fore.GREEN if status=="Running" else Fore.YELLOW)
                icon = "RED" if crashed else ("GRN" if status=="Running" else "YLW")
                print(f"{clr}[{icon}] {name:<50} {status:<25} restarts={restarts}{Style.RESET_ALL}")
                if first_pass:
                    # Prime cache without alert noise for existing restarts.
                    cache[name] = {"status":status,"restarts":restarts,"alerted":crashed}
                    continue

                if new_crash:
                    discord_alert(name, status, restarts, msg, restart_delta=restart_delta)
                    cache[name] = {"status":status,"restarts":restarts,"alerted":True}
                elif restart_delta > 0:
                    discord_alert(name, status, restarts, msg, restart_delta=restart_delta)
                    cache[name] = {"status":status,"restarts":restarts,"alerted":crashed}
                elif recovered:
                    discord_alert(name, status, restarts, recovered=True, restart_delta=restart_delta)
                    cache[name] = {"status":status,"restarts":restarts,"alerted":False}
                else:
                    cache[name] = {"status":status,"restarts":restarts,"alerted":prev["alerted"] if crashed else False}
            first_pass = False
            print(f"{Fore.BLUE}{'-'*80}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[ERROR] {e}{Style.RESET_ALL}")
        time.sleep(INTERVAL)


if __name__ == "__main__": run()
