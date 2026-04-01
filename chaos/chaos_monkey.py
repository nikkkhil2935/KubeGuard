#!/usr/bin/env python3
"""KubeGuard ChaosMonkey - Randomly kills pods to test self-healing."""
import subprocess, json, time, random, argparse
from datetime import datetime
from colorama import Fore, Style, init


init(autoreset=True)
MODES = {"low":30, "medium":15, "high":5}


def get_running_pods(ns):
    r = subprocess.run(["kubectl","get","pods","-n",ns,"-o","json"],
                       capture_output=True, text=True)
    items = json.loads(r.stdout).get("items",[])
    return [
        p["metadata"]["name"] for p in items
        if p["status"].get("phase")=="Running"
        and p["status"].get("containerStatuses",[{}])[0].get("ready",False)
    ]


def kill_pod(ns, name):
    subprocess.run(["kubectl","delete","pod",name,"-n",ns,
                    "--grace-period=0","--force"], capture_output=True)


def wait_recovery(ns, expected, timeout=60):
    start = time.time()
    while time.time()-start < timeout:
        if len(get_running_pods(ns)) >= expected:
            return True, round(time.time()-start, 1)
        time.sleep(2)
    return False, timeout


def run(ns, interval, duration):
    print(f"{Fore.RED}CHAOS MONKEY STARTED | ns={ns} | interval={interval}s | duration={duration}s{Style.RESET_ALL}")
    log, start, kills = [], time.time(), 0
    while time.time()-start < duration:
        pods = get_running_pods(ns)
        if not pods:
            print(f"{Fore.YELLOW}No running pods, waiting...{Style.RESET_ALL}"); time.sleep(5); continue
        target = random.choice(pods)
        expected = len(pods)
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.RED}[{ts}] KILLING: {target} ({expected} alive){Style.RESET_ALL}")
        kill_pod(ns, target); kills += 1
        ok, t = wait_recovery(ns, expected)
        if ok: print(f"{Fore.GREEN}[{ts}] RECOVERED in {t}s{Style.RESET_ALL}")
        else:  print(f"{Fore.YELLOW}[{ts}] Recovery timeout!{Style.RESET_ALL}")
        log.append({"pod":target, "ok":ok, "t":t})
        if kills % 3 == 0:
            avg = sum(k["t"] for k in log)/len(log)
            ok_rate = sum(1 for k in log if k["ok"])/len(log)*100
            print(f"{Fore.CYAN}CHAOS REPORT | Kills:{kills} | AvgRecovery:{avg:.1f}s | SuccessRate:{ok_rate:.0f}%{Style.RESET_ALL}")
        time.sleep(interval)
    print(f"{Fore.GREEN}Chaos complete. Total kills: {kills}{Style.RESET_ALL}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--namespace", default="kubeguard")
    p.add_argument("--mode", choices=["low","medium","high"], default="medium")
    p.add_argument("--interval", type=int, default=None)
    p.add_argument("--duration", type=int, default=120)
    a = p.parse_args()
    run(a.namespace, a.interval or MODES[a.mode], a.duration)
