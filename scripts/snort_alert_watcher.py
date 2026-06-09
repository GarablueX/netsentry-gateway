#!/usr/bin/env python3

from pathlib import Path
import argparse
import json
import re
import time
from datetime import datetime

BASE_DIR = Path.home() / "netsentry-gateway"
ALERT_FILE = BASE_DIR / "snort" / "alerts" / "alert_fast.txt"
JSONL_FILE = BASE_DIR / "snort" / "alerts" / "alerts.jsonl"


def parse_alert(line: str) -> dict:
    sid_match = re.search(r"\[1:(\d+):(\d+)\]", line)
    proto_match = re.search(r"\{([A-Z]+)\}", line)
    ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+->\s+(\d+\.\d+\.\d+\.\d+)", line)
    priority_match = re.search(r"\[Priority:\s*(\d+)\]", line)

    timestamp_match = re.match(r"^(\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d+)", line)

    message = "Unknown alert"
    if "[**]" in line:
        parts = line.split("[**]")
        if len(parts) >= 3:
            message = parts[1].strip()
            message = re.sub(r"\[1:\d+:\d+\]\s*", "", message).strip()

    return {
        "received_at": datetime.now().isoformat(timespec="seconds"),
        "snort_time": timestamp_match.group(1) if timestamp_match else "unknown",
        "sid": sid_match.group(1) if sid_match else "unknown",
        "rev": sid_match.group(2) if sid_match else "unknown",
        "priority": priority_match.group(1) if priority_match else "unknown",
        "proto": proto_match.group(1) if proto_match else "unknown",
        "src": ip_match.group(1) if ip_match else "unknown",
        "dst": ip_match.group(2) if ip_match else "unknown",
        "message": message,
        "raw": line.strip(),
    }


def print_alert(alert: dict) -> None:
    print("=" * 70, flush=True)
    print(f"ALERT:    {alert['message']}", flush=True)
    print(f"SID:      {alert['sid']}  REV: {alert['rev']}", flush=True)
    print(f"PRIORITY: {alert['priority']}", flush=True)
    print(f"PROTO:    {alert['proto']}", flush=True)
    print(f"SRC:      {alert['src']}", flush=True)
    print(f"DST:      {alert['dst']}", flush=True)
    print(f"TIME:     {alert['received_at']}", flush=True)
    print("=" * 70, flush=True)


def write_jsonl(alert: dict) -> None:
    JSONL_FILE.parent.mkdir(parents=True, exist_ok=True)

    with JSONL_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")
        f.flush()


def follow_file(path: Path, from_start: bool = False) -> None:
    print(f"[+] Watching Snort alert file: {path}", flush=True)
    print(f"[+] Writing structured alerts to: {JSONL_FILE}", flush=True)

    while not path.exists():
        print("[!] Alert file does not exist yet. Waiting...", flush=True)
        time.sleep(2)

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        if from_start:
            print("[+] Reading alerts from start of file.", flush=True)
            f.seek(0)
        else:
            print("[+] Starting from end of file. Only new alerts will be shown.", flush=True)
            f.seek(0, 2)

        while True:
            line = f.readline()

            if not line:
                time.sleep(0.5)
                continue

            if "[**]" not in line:
                continue

            alert = parse_alert(line)
            print_alert(alert)
            write_jsonl(alert)


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch Snort alert_fast output and write JSONL alerts.")
    parser.add_argument(
        "--from-start",
        action="store_true",
        help="Read existing alerts from the beginning of the file.",
    )
    args = parser.parse_args()

    follow_file(ALERT_FILE, from_start=args.from_start)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[+] Watcher stopped.", flush=True)
