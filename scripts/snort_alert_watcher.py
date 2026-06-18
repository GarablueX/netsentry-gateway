#!/usr/bin/env python3
from pathlib import Path
import re
import time
import json
import subprocess
from datetime import datetime

alert_file = Path("/home/gbx/netsentry-gateway/snort/alerts/alert_fast.txt")

jsonl_path = Path("/home/gbx/netsentry-gateway/data/ids/alerts.jsonl")
latest_path = Path("/home/gbx/netsentry-gateway/data/ids/alerts_latest.json")
latest_rev3_path = Path("/home/gbx/netsentry-gateway/data/ids/latest_rev3.json")

rev3_dir = Path("/home/gbx/netsentry-gateway/data/ids/rev3_flags")
pcap_dir = Path("/home/gbx/netsentry-gateway/snort/pcaps")

interface = "wlx200db0220b9a"
pcap_cooldown_seconds = 60
last_pcap_by_src = {}

jsonl_path.parent.mkdir(parents=True, exist_ok=True)
rev3_dir.mkdir(parents=True, exist_ok=True)
pcap_dir.mkdir(parents=True, exist_ok=True)

ALERT_RE = re.compile(
    r"""
    ^(?P<snort_time>\d{2}/\d{2}-\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+
    \[\*\*\]\s+
    \[(?P<gid>\d+):(?P<sid>\d+):(?P<rev>\d+)\]\s+
    "?(?P<msg>.*?)"?\s+
    \[\*\*\]
    (?P<middle>.*?)
    \{(?P<proto>[A-Z]+)\}\s+
    (?P<src_ip>\d{1,3}(?:\.\d{1,3}){3})
    (?::(?P<src_port>\d+))?
    \s*->\s*
    (?P<dst_ip>\d{1,3}(?:\.\d{1,3}){3})
    (?::(?P<dst_port>\d+))?
    \s*$
    """,
    re.VERBOSE,
)


def severity_from_rev(rev):
    rev = int(rev)
    if rev >= 3:
        return "high"
    if rev == 2:
        return "medium"
    return "low"

def extract_priority(text):
    m = re.search(r"\[Priority:\s*(\d+)\]", text or "")
    if not m:
        return None
    return int(m.group(1))


def parse_alert_line(line):
    match = ALERT_RE.match(line.strip())
    if not match:
        return None

    alert = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "snort_time": match.group("snort_time"),
        "gid": int(match.group("gid")),
        "sid": int(match.group("sid")),
        "rev": int(match.group("rev")),
        "severity": severity_from_rev(match.group("rev")),
        "message": match.group("msg").strip().strip('"'),
        "protocol": match.group("proto"),
        "src_ip": match.group("src_ip"),
        "src_port": match.group("src_port"),
        "dst_ip": match.group("dst_ip"),
        "dst_port": match.group("dst_port"),
        "priority": extract_priority(match.group("middle")),
        "pcap_file": None,
        "raw": line.strip(),
    }

    return alert


def save_to_json_file(alert):
    with open(jsonl_path, "a", encoding="utf-8") as jsf:
        jsf.write(json.dumps(alert) + "\n")


def save_latest(alerts):
    latest_path.write_text(json.dumps(alerts[-100:], indent=2), encoding="utf-8")


def save_latest_rev3(alert):
    latest_rev3_path.write_text(json.dumps(alert, indent=2), encoding="utf-8")


def create_rev3_flag(alert):
    flag_path = rev3_dir / f"rev3_{alert['src_ip']}_to_{alert['dst_ip']}_{int(time.time())}.json"
    flag_path.write_text(json.dumps(alert, indent=2), encoding="utf-8")
    print("rev3 flag file created:", flag_path, flush=True)


def capture_rev3_pcap(alert):
    src_ip = alert["src_ip"]
    sid = alert["sid"]
    now = time.time()

    last_time = last_pcap_by_src.get(src_ip, 0)
    if now - last_time < pcap_cooldown_seconds:
        print(f"pcap skipped for {src_ip}: cooldown active", flush=True)
        return None

    last_pcap_by_src[src_ip] = now

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pcap_path = pcap_dir / f"rev3_{stamp}_{src_ip}_sid{sid}.pcap"

    cmd = [
        "/usr/bin/timeout", "10",
        "/usr/bin/tcpdump",
        "-Z", "root",
        "-ni", interface,
        "-w", str(pcap_path),
        "host", src_ip,
    ]

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print("pcap capture started:", pcap_path, flush=True)
        return str(pcap_path)
    except Exception as error:
        print("pcap capture failed:", error, flush=True)
        return None


def follow_file(file_path):
    alerts = []

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.touch(exist_ok=True)

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        print(f"watching {file_path} waiting for new alerts ..", flush=True)

        while True:
            line = f.readline()

            if line:
                alert = parse_alert_line(line)

                if alert:
                    print("alert detected:", alert, flush=True)

                    if alert["rev"] == 3:
                        print(
                            f"high severity alert from {alert['src_ip']} "
                            f"to {alert['dst_ip']} at {alert['timestamp']}.",
                            flush=True,
                        )
                        alert["pcap_file"] = capture_rev3_pcap(alert)
                        create_rev3_flag(alert)
                        save_latest_rev3(alert)

                    alerts.append(alert)
                    save_to_json_file(alert)
                    save_latest(alerts)

                else:
                    print("unparsed line:", line.strip(), flush=True)

            else:
                time.sleep(0.5)


if __name__ == "__main__":
    follow_file(alert_file)
