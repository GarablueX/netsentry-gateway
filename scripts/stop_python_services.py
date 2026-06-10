#!/usr/bin/env python3

from pathlib import Path
import os
import signal
import time
import subprocess

BASE_DIR = Path.home() / "netsentry-gateway"
PID_DIR = BASE_DIR / "logs" / "pids"

SERVICES = [
    "snort_alert_watcher",
    "netsentry_status_api",
    "netsentry_dashboard",
    "honeypot_lite",
    "http_test_service",
]


def pid_file(service_name: str) -> Path:
    return PID_DIR / f"{service_name}.pid"


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def stop_pid(service_name: str, pid: int) -> None:
    if not is_running(pid):
        print(f"[=] {service_name} PID {pid} is not running")
        return

    print(f"[+] Stopping {service_name} PID {pid}")
    os.kill(pid, signal.SIGTERM)

    for _ in range(10):
        if not is_running(pid):
            print(f"[+] Stopped {service_name}")
            return
        time.sleep(0.3)

    print(f"[!] {service_name} did not stop gracefully. Killing...")
    os.kill(pid, signal.SIGKILL)


def fallback_pkill() -> None:
    patterns = [
        "snort_alert_watcher.py",
        "netsentry_status_api.py",
        "netsentry_dashboard.py",
        "honeypot_lite.py",
        "http_test_service.py",
    ]

    for pattern in patterns:
        subprocess.run(["pkill", "-f", pattern], check=False)


def main() -> None:
    print("[+] Stopping NetSentry Python services...")

    for service_name in SERVICES:
        path = pid_file(service_name)

        if not path.exists():
            print(f"[=] No PID file for {service_name}")
            continue

        try:
            pid = int(path.read_text().strip())
        except ValueError:
            print(f"[!] Invalid PID file for {service_name}: {path}")
            path.unlink(missing_ok=True)
            continue

        stop_pid(service_name, pid)
        path.unlink(missing_ok=True)

    print("[+] Running fallback cleanup...")
    fallback_pkill()

    print("[+] Done.")


if __name__ == "__main__":
    main()
