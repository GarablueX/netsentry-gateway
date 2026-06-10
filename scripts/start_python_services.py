#!/usr/bin/env python3

from pathlib import Path
import subprocess
import sys
import os
import time

BASE_DIR = Path.home() / "netsentry-gateway"
SCRIPTS_DIR = BASE_DIR / "scripts"
LOG_DIR = BASE_DIR / "logs" / "runtime"
PID_DIR = BASE_DIR / "logs" / "pids"

SERVICES = [
    {
        "name": "http_test_service",
        "script": "http_test_service.py",
        "port": 8081,
    },
    {
        "name": "honeypot_lite",
        "script": "honeypot_lite.py",
        "port": 8082,
    },
    {
        "name": "netsentry_dashboard",
        "script": "netsentry_dashboard.py",
        "port": 5050,
    },
    {
        "name": "netsentry_status_api",
        "script": "netsentry_status_api.py",
        "port": 5051,
    },
    {
        "name": "snort_alert_watcher",
        "script": "snort_alert_watcher.py",
        "port": None,
    },
]


def pid_file(service_name: str) -> Path:
    return PID_DIR / f"{service_name}.pid"


def log_file(service_name: str) -> Path:
    return LOG_DIR / f"{service_name}.log"


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def read_existing_pid(service_name: str) -> int | None:
    path = pid_file(service_name)

    if not path.exists():
        return None

    try:
        return int(path.read_text().strip())
    except ValueError:
        return None


def start_service(service: dict) -> None:
    name = service["name"]
    script = service["script"]
    script_path = SCRIPTS_DIR / script

    if not script_path.exists():
        print(f"[!] Missing script: {script_path}")
        return

    existing_pid = read_existing_pid(name)

    if existing_pid and is_running(existing_pid):
        print(f"[=] {name} already running with PID {existing_pid}")
        return

    PID_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    out_path = log_file(name)

    out_file = out_path.open("a", encoding="utf-8")

    process = subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=str(BASE_DIR),
        stdout=out_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    pid_file(name).write_text(str(process.pid), encoding="utf-8")

    port_text = f" on port {service['port']}" if service["port"] else ""
    print(f"[+] Started {name}{port_text} with PID {process.pid}")
    print(f"    Log: {out_path}")


def main() -> None:
    print("[+] Starting NetSentry Python services...")
    print(f"[+] Base directory: {BASE_DIR}")

    for service in SERVICES:
        start_service(service)
        time.sleep(0.5)

    print("\n[+] Done.")
    print("[+] Useful URLs:")
    print("    IDS Dashboard:   http://192.168.1.19:5050")
    print("    Status API:      http://192.168.1.19:5051")
    print("    HTTP Test:       http://192.168.1.19:8081")
    print("    Honeypot-lite:   http://192.168.1.19:8082")
    print("\n[!] Snort itself is not started by this script. Start Snort separately with sudo.")


if __name__ == "__main__":
    main()
