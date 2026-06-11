#!/usr/bin/env python3

from pathlib import Path
import os
import signal
import subprocess
import time

BASE_DIR = Path.home() / "netsentry-gateway"
LOG_DIR = BASE_DIR / "logs"
PID_DIR = LOG_DIR / "pids"

SERVICES = [
    {
        "name": "IDS Dashboard",
        "script": "netsentry_dashboard.py",
        "pid": "dashboard.pid",
    },
    {
        "name": "Status API",
        "script": "netsentry_status_api.py",
        "pid": "status_api.pid",
    },
    {
        "name": "HTTP Test Service",
        "script": "http_test_service.py",
        "pid": "http_test_service.pid",
    },
    {
        "name": "Honeypot-lite",
        "script": "honeypot_lite.py",
        "pid": "honeypot_lite.pid",
    },
    {
        "name": "Snort Alert Watcher",
        "script": "snort_alert_watcher.py",
        "pid": "snort_alert_watcher.pid",
    },
    {
        "name": "NetSentry Portal",
        "script": "netsentry_portal.py",
        "pid": "portal.pid",
    },
]


def pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def process_matches_pid(pid: int, script_name: str) -> bool:
    if not pid_running(pid):
        return False

    cmdline_path = Path(f"/proc/{pid}/cmdline")
    if not cmdline_path.exists():
        return False

    try:
        cmdline = cmdline_path.read_text(errors="ignore").replace("\x00", " ")
        return script_name in cmdline
    except Exception:
        return False


def terminate_pid(pid: int, name: str, script_name: str):
    if not process_matches_pid(pid, script_name):
        return False

    print(f"[-] Stopping {name} PID {pid}...")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True

    for _ in range(20):
        if not pid_running(pid):
            print(f"[+] Stopped {name}")
            return True
        time.sleep(0.1)

    print(f"[!] {name} did not stop gracefully. Killing PID {pid}...")
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

    return True


def stop_from_pid_file(service: dict):
    pid_path = PID_DIR / service["pid"]

    if not pid_path.exists():
        return False

    try:
        pid = int(pid_path.read_text().strip())
    except Exception:
        pid_path.unlink(missing_ok=True)
        return False

    stopped = terminate_pid(pid, service["name"], service["script"])
    pid_path.unlink(missing_ok=True)
    return stopped


def fallback_pkill(service: dict):
    script_name = service["script"]
    name = service["name"]

    result = subprocess.run(
        ["pgrep", "-af", script_name],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return

    pids = []

    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=1)
        if not parts:
            continue

        try:
            pid = int(parts[0])
        except ValueError:
            continue

        if pid == os.getpid():
            continue

        if script_name in line and "pgrep" not in line:
            pids.append(pid)

    for pid in pids:
        terminate_pid(pid, name, script_name)


def main():
    print("[+] Stopping NetSentry Python services...")

    for service in SERVICES:
        stopped = stop_from_pid_file(service)

        if not stopped:
            fallback_pkill(service)

    print("\n[+] Remaining matching processes:")
    subprocess.run(
        [
            "pgrep",
            "-af",
            "netsentry_dashboard.py|netsentry_status_api.py|http_test_service.py|honeypot_lite.py|snort_alert_watcher.py|netsentry_portal.py",
        ],
        check=False,
    )

    print("\n[+] Done.")


if __name__ == "__main__":
    main()
