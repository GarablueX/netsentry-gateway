#!/usr/bin/env python3

from pathlib import Path
import subprocess
import sys
import time
import os

BASE_DIR = Path.home() / "netsentry-gateway"
SCRIPTS_DIR = BASE_DIR / "scripts"
LOG_DIR = BASE_DIR / "logs"
PID_DIR = LOG_DIR / "pids"

LOG_DIR.mkdir(parents=True, exist_ok=True)
PID_DIR.mkdir(parents=True, exist_ok=True)

SERVICES = [
    {
        "name": "IDS Dashboard",
        "script": "netsentry_dashboard.py",
        "log": "dashboard_runtime.log",
        "pid": "dashboard.pid",
        "port": "5050",
    },
    {
        "name": "Status API",
        "script": "netsentry_status_api.py",
        "log": "status_api_runtime.log",
        "pid": "status_api.pid",
        "port": "5051",
    },
    {
        "name": "HTTP Test Service",
        "script": "http_test_service.py",
        "log": "http_test_service_runtime.log",
        "pid": "http_test_service.pid",
        "port": "8081",
    },
    {
        "name": "Honeypot-lite",
        "script": "honeypot_lite.py",
        "log": "honeypot_lite_runtime.log",
        "pid": "honeypot_lite.pid",
        "port": "8082",
    },
    {
        "name": "Snort Alert Watcher",
        "script": "snort_alert_watcher.py",
        "log": "snort_alert_watcher_runtime.log",
        "pid": "snort_alert_watcher.pid",
        "port": None,
    },
    {
        "name": "NetSentry Portal",
        "script": "netsentry_portal.py",
        "log": "portal_runtime.log",
        "pid": "portal.pid",
        "port": "5500",
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


def pid_file_running(pid_path: Path, script_name: str) -> bool:
    if not pid_path.exists():
        return False

    try:
        pid = int(pid_path.read_text().strip())
    except Exception:
        return False

    return process_matches_pid(pid, script_name)


def pgrep_running(script_name: str) -> bool:
    result = subprocess.run(
        ["pgrep", "-af", script_name],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return False

    for line in result.stdout.splitlines():
        if script_name in line and "pgrep" not in line:
            return True

    return False


def start_service(service: dict):
    name = service["name"]
    script_name = service["script"]
    script_path = SCRIPTS_DIR / script_name
    log_path = LOG_DIR / service["log"]
    pid_path = PID_DIR / service["pid"]

    if not script_path.exists():
        print(f"[!] Missing script: {script_path}")
        return

    if pid_file_running(pid_path, script_name) or pgrep_running(script_name):
        print(f"[=] Already running: {name} ({script_name})")
        return

    log_file = log_path.open("a", encoding="utf-8")

    process = subprocess.Popen(
        [sys.executable, "-u", str(script_path)],
        cwd=str(BASE_DIR),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    pid_path.write_text(str(process.pid), encoding="utf-8")

    print(f"[+] Started {name}")
    print(f"    PID: {process.pid}")
    print(f"    Script: {script_path}")
    print(f"    Log: {log_path}")


def main():
    print("[+] Starting NetSentry Python services...")
    print(f"[+] Base directory: {BASE_DIR}")

    for service in SERVICES:
        start_service(service)
        time.sleep(0.2)

    print("\n[+] Listening ports:")
    subprocess.run(
        ["ss", "-tulpen"],
        check=False,
    )

    print("\n[+] Matching processes:")
    subprocess.run(
        [
            "pgrep",
            "-af",
            "netsentry_dashboard.py|netsentry_status_api.py|http_test_service.py|honeypot_lite.py|snort_alert_watcher.py|netsentry_portal.py",
        ],
        check=False,
    )

    print("\n[+] Done.")
    print("[!] Snort itself is not started here because it needs sudo.")


if __name__ == "__main__":
    main()
