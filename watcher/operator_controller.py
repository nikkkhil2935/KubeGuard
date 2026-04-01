#!/usr/bin/env python3
"""KubeGuard Operator - Watches K8s events, auto-remediates, and alerts Discord."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from colorama import Fore, Style, init
from dotenv import load_dotenv
from kubernetes import client, config, watch


init(autoreset=True)
ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ROOT_ENV)

DISCORD = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip()
CRITICAL = (os.getenv("DISCORD_CRITICAL_URL") or DISCORD).strip()
SLACK_WEBHOOK_URL = (os.getenv("SLACK_WEBHOOK_URL") or "").strip()
SLACK_BOT_TOKEN = (os.getenv("SLACK_BOT_TOKEN") or "").strip()
SLACK_CHANNEL_ID = (os.getenv("SLACK_CHANNEL_ID") or "").strip()
NAMESPACE = os.getenv("NAMESPACE", "kubeguard")

try:
    config.load_incluster_config()
except Exception:
    config.load_kube_config()

v1 = client.CoreV1Api()

CRASH_REASONS = {"CrashLoopBackOff", "OOMKilled", "Error", "ImagePullBackOff"}
incident_log = []


def log_incident(pod, reason, action, severity="warning"):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pod": pod,
        "reason": reason,
        "action": action,
        "severity": severity,
    }
    incident_log.append(entry)
    print(f"{Fore.CYAN}[INCIDENT] {json.dumps(entry)}{Style.RESET_ALL}")


def auto_remediate(pod_name, reason, restart_count):
    if restart_count > 10:
        print(f"{Fore.RED}[REMEDIATE] Force deleting {pod_name}{Style.RESET_ALL}")
        v1.delete_namespaced_pod(name=pod_name, namespace=NAMESPACE)
        return "force-delete"
    if reason == "OOMKilled":
        print(f"{Fore.YELLOW}[REMEDIATE] OOM event on {pod_name}{Style.RESET_ALL}")
        return "oom-restart"
    print(f"{Fore.YELLOW}[REMEDIATE] Allowing natural restart for {pod_name}{Style.RESET_ALL}")
    return "k8s-natural-restart"


def discord_alert(pod, reason, restarts, action, severity="warning", recovered=False):
    url = CRITICAL if severity == "critical" else DISCORD
    if not url:
        return

    if recovered:
        color, title = 65280, "Pod Recovered"
    elif severity == "critical":
        color, title = 16711680, "CRITICAL: Service Down"
    else:
        color, title = 16744272, "Pod Crash Detected"

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = {
        "username": "KubeGuard Operator",
        "embeds": [
            {
                "title": title,
                "color": color,
                "fields": [
                    {"name": "Pod", "value": f"`{pod}`", "inline": True},
                    {"name": "Reason", "value": f"`{reason}`", "inline": True},
                    {"name": "Restarts", "value": str(restarts), "inline": True},
                    {"name": "Action Taken", "value": action, "inline": True},
                    {"name": "Namespace", "value": f"`{NAMESPACE}`", "inline": True},
                    {"name": "Time", "value": ts, "inline": True},
                ],
                "footer": {"text": "KubeGuard Operator v2.0 - Team S8UL"},
            }
        ],
    }

    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code < 200 or resp.status_code >= 300:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"{Fore.RED}[Discord] FAIL: {e}{Style.RESET_ALL}")


def slack_alert(pod, reason, restarts, action, severity="warning", recovered=False):
    if recovered:
        text = (
            f":large_green_circle: *KubeGuard Recovered*\n"
            f"Pod: `{pod}`\nNamespace: `{NAMESPACE}`\nRestarts: `{restarts}`\nAction: `{action}`"
        )
    elif severity == "critical":
        text = (
            f":red_circle: *KubeGuard Critical*\n"
            f"Pod: `{pod}`\nReason: `{reason}`\nRestarts: `{restarts}`\nAction: `{action}`"
        )
    else:
        text = (
            f":warning: *KubeGuard Crash Detected*\n"
            f"Pod: `{pod}`\nReason: `{reason}`\nRestarts: `{restarts}`\nAction: `{action}`"
        )

    try:
        if SLACK_WEBHOOK_URL:
            resp = requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=5)
            if resp.status_code < 200 or resp.status_code >= 300:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return

        if SLACK_BOT_TOKEN and SLACK_CHANNEL_ID:
            resp = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json={"channel": SLACK_CHANNEL_ID, "text": text},
                timeout=5,
            )
            if resp.status_code < 200 or resp.status_code >= 300:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack API error: {data}")
    except Exception as e:
        print(f"{Fore.RED}[Slack] FAIL: {e}{Style.RESET_ALL}")


def watch_pods():
    print(f"{Fore.GREEN}KubeGuard Operator STARTED | namespace={NAMESPACE}{Style.RESET_ALL}")
    w = watch.Watch()
    known_crashes = {}

    for event in w.stream(v1.list_namespaced_pod, namespace=NAMESPACE, timeout_seconds=0):
        pod_obj = event["object"]
        evt_type = event["type"]
        pod_name = pod_obj.metadata.name
        phase = pod_obj.status.phase or "Unknown"
        cs = (pod_obj.status.container_statuses or [None])[0]

        if not cs:
            continue

        restarts = cs.restart_count
        crash_reason = None
        if cs.state and cs.state.waiting and cs.state.waiting.reason in CRASH_REASONS:
            crash_reason = cs.state.waiting.reason
        elif cs.state and cs.state.terminated and cs.state.terminated.reason in CRASH_REASONS:
            crash_reason = cs.state.terminated.reason

        if crash_reason:
            prev = known_crashes.get(pod_name)
            if prev != crash_reason:
                severity = "critical" if restarts > 8 else "warning"
                action = auto_remediate(pod_name, crash_reason, restarts)
                discord_alert(pod_name, crash_reason, restarts, action, severity)
                slack_alert(pod_name, crash_reason, restarts, action, severity)
                log_incident(pod_name, crash_reason, action, severity)
                known_crashes[pod_name] = crash_reason
                tone = Fore.RED if severity == "critical" else Fore.YELLOW
                print(
                    f"{tone}[CRASH] {pod_name} | reason={crash_reason} | restarts={restarts} | action={action}{Style.RESET_ALL}"
                )
        elif cs.ready and pod_name in known_crashes:
            known_crashes.pop(pod_name, None)
            discord_alert(pod_name, "Recovered", restarts, "Self-healed", recovered=True)
            slack_alert(pod_name, "Recovered", restarts, "Self-healed", recovered=True)
            log_incident(pod_name, "Recovered", "self-heal", "info")
            print(f"{Fore.GREEN}[RECOVERED] {pod_name} after {restarts} restarts{Style.RESET_ALL}")
        else:
            color = Fore.GREEN if cs.ready else Fore.YELLOW
            print(
                f"{color}[{evt_type}] {pod_name:<50} phase={phase} restarts={restarts} ready={cs.ready}{Style.RESET_ALL}"
            )


if __name__ == "__main__":
    while True:
        try:
            watch_pods()
        except Exception as e:
            print(f"{Fore.RED}[ERROR] Stream broke: {e} - reconnecting in 5s{Style.RESET_ALL}")
            time.sleep(5)
