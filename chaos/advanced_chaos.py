#!/usr/bin/env python3
"""KubeGuard Advanced Chaos - OOM, CPU stress, cascade kill, and random modes."""
import argparse
import json
import random
import subprocess
import threading
import time
from datetime import datetime

import requests
from colorama import Fore, Style, init


init(autoreset=True)


def kubectl(cmd):
    return subprocess.run(["kubectl"] + cmd, capture_output=True, text=True)


def get_running_pods(namespace):
    res = kubectl(["get", "pods", "-n", namespace, "-o", "json"])
    if res.returncode != 0:
        return []
    try:
        items = json.loads(res.stdout).get("items", [])
    except json.JSONDecodeError:
        return []

    pods = []
    for item in items:
        phase = item.get("status", {}).get("phase")
        cs = item.get("status", {}).get("containerStatuses", [])
        if phase == "Running" and cs and all(c.get("ready") for c in cs):
            pods.append(item["metadata"]["name"])
    return pods


def pod_delete(namespace, pod):
    kubectl(["delete", "pod", pod, "-n", namespace, "--grace-period=0", "--force"])
    print(f"{Fore.RED}[DELETE] {pod}{Style.RESET_ALL}")


def pod_ip(namespace, pod):
    res = kubectl(["get", "pod", pod, "-n", namespace, "-o", "jsonpath={.status.podIP}"])
    return res.stdout.strip() if res.returncode == 0 else ""


def oom_attack(namespace, pod):
    ip = pod_ip(namespace, pod)
    if ip:
        try:
            requests.get(f"http://{ip}:8000/oom", timeout=2)
        except Exception:
            pass
    print(f"{Fore.RED}[OOM] {pod}{Style.RESET_ALL}")


def cpu_bomb(namespace, pod, duration=20):
    ip = pod_ip(namespace, pod)

    def _stress():
        if not ip:
            return
        try:
            requests.get(f"http://{ip}:8000/stress", timeout=duration + 5)
        except Exception:
            pass

    for _ in range(3):
        threading.Thread(target=_stress, daemon=True).start()
    print(f"{Fore.YELLOW}[CPU] stress launched on {pod} (x3){Style.RESET_ALL}")


def cascade_kill(namespace, pods, count=2):
    targets = random.sample(pods, min(count, len(pods)))
    print(f"{Fore.RED}[CASCADE] targets={targets}{Style.RESET_ALL}")
    for pod in targets:
        threading.Thread(target=pod_delete, args=(namespace, pod), daemon=True).start()


def wait_recovery(namespace, expected, timeout=90):
    start = time.time()
    while time.time() - start < timeout:
        if len(get_running_pods(namespace)) >= expected:
            return True, round(time.time() - start, 1)
        time.sleep(3)
    return False, timeout


def run(namespace, mode, duration):
    print(f"{Fore.RED}ADVANCED CHAOS | ns={namespace} | mode={mode} | duration={duration}s{Style.RESET_ALL}")
    start = time.time()
    events = []

    while time.time() - start < duration:
        pods = get_running_pods(namespace)
        if not pods:
            print(f"{Fore.YELLOW}No running pods, retrying...{Style.RESET_ALL}")
            time.sleep(5)
            continue

        expected = len(pods)
        scenario = random.choice(["delete", "oom", "cpu", "cascade"]) if mode == "random" else mode
        target = random.choice(pods)
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"\n{Fore.RED}[{ts}] scenario={scenario.upper()} target={target}{Style.RESET_ALL}")

        if scenario == "delete":
            pod_delete(namespace, target)
        elif scenario == "oom":
            oom_attack(namespace, target)
        elif scenario == "cpu":
            cpu_bomb(namespace, target)
        elif scenario == "cascade":
            cascade_kill(namespace, pods, 2)

        ok, elapsed = wait_recovery(namespace, expected)
        state = "RECOVERED" if ok else "TIMEOUT"
        color = Fore.GREEN if ok else Fore.YELLOW
        print(f"{color}[{state}] {elapsed}s{Style.RESET_ALL}")
        events.append({"scenario": scenario, "ok": ok, "t": elapsed})

        if len(events) % 3 == 0:
            avg = sum(e["t"] for e in events) / len(events)
            sr = sum(1 for e in events if e["ok"]) * 100 / len(events)
            print(f"{Fore.CYAN}[REPORT] events={len(events)} avg_recovery={avg:.1f}s success={sr:.0f}%{Style.RESET_ALL}")

        time.sleep(10)

    print(f"{Fore.GREEN}Chaos complete. events={len(events)}{Style.RESET_ALL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default="kubeguard")
    parser.add_argument("--mode", choices=["delete", "oom", "cpu", "cascade", "random"], default="random")
    parser.add_argument("--duration", type=int, default=120)
    args = parser.parse_args()
    run(args.namespace, args.mode, args.duration)
