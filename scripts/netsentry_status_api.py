#!/usr/bin/env python3

from pathlib import Path
from flask import Flask, jsonify, render_template_string
import os
import shutil
import socket
import subprocess
import time

BASE_DIR = Path.home() / "netsentry-gateway"
ALERTS_JSONL = BASE_DIR / "snort" / "alerts" / "alerts.jsonl"
ALERT_FAST = BASE_DIR / "snort" / "alerts" / "alert_fast.txt"

app = Flask(__name__)


HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>NetSentry Status API</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #101014;
            color: #eeeeee;
            margin: 0;
            padding: 20px;
        }

        h1 {
            margin-bottom: 5px;
        }

        .subtitle {
            color: #aaaaaa;
            margin-bottom: 20px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(220px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .card {
            background: #1b1b23;
            border: 1px solid #333342;
            border-radius: 8px;
            padding: 15px;
        }

        .label {
            color: #aaaaaa;
            font-size: 13px;
            margin-bottom: 6px;
        }

        .value {
            font-size: 22px;
            font-weight: bold;
        }

        .ok {
            color: #74e291;
        }

        .bad {
            color: #ff7777;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: #17171f;
            border: 1px solid #333342;
            margin-top: 15px;
        }

        th, td {
            border-bottom: 1px solid #333342;
            padding: 10px;
            text-align: left;
            font-size: 14px;
        }

        th {
            background: #22222d;
        }

        code {
            color: #ffcc66;
        }

        .button {
            display: inline-block;
            padding: 9px 12px;
            border-radius: 5px;
            border: 1px solid #555566;
            background: #272735;
            color: #eeeeee;
            text-decoration: none;
            font-size: 14px;
            margin-right: 8px;
        }

        .button:hover {
            background: #353548;
        }

        @media (max-width: 900px) {
            .grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <h1>NetSentry Status API</h1>
    <div class="subtitle">
        Local system health and service status. Auto-refreshes every 5 seconds.
    </div>

    <div>
        <a class="button" href="/api/status">API JSON</a>
        <a class="button" href="http://192.168.1.19:5050">IDS Dashboard</a>
    </div>

    <div class="grid">
        <div class="card">
            <div class="label">Hostname</div>
            <div class="value">{{ status.hostname }}</div>
        </div>

        <div class="card">
            <div class="label">Uptime</div>
            <div class="value">{{ status.uptime }}</div>
        </div>

        <div class="card">
            <div class="label">Load Average</div>
            <div class="value">{{ status.load_average }}</div>
        </div>

        <div class="card">
            <div class="label">Memory Used</div>
            <div class="value">{{ status.memory.used_percent }}%</div>
        </div>

        <div class="card">
            <div class="label">Disk Used</div>
            <div class="value">{{ status.disk.used_percent }}%</div>
        </div>

        <div class="card">
            <div class="label">Total Alerts</div>
            <div class="value">{{ status.alerts.total_alerts }}</div>
        </div>

        <div class="card">
            <div class="label">Snort Process</div>
            <div class="value {% if status.processes.snort %}ok{% else %}bad{% endif %}">
                {% if status.processes.snort %}RUNNING{% else %}STOPPED{% endif %}
            </div>
        </div>

        <div class="card">
            <div class="label">Watcher Process</div>
            <div class="value {% if status.processes.watcher %}ok{% else %}bad{% endif %}">
                {% if status.processes.watcher %}RUNNING{% else %}STOPPED{% endif %}
            </div>
        </div>

        <div class="card">
            <div class="label">AdGuard Process</div>
            <div class="value {% if status.processes.adguard %}ok{% else %}bad{% endif %}">
                {% if status.processes.adguard %}RUNNING{% else %}STOPPED{% endif %}
            </div>
        </div>
    </div>

    <h2>Interfaces</h2>
    <table>
        <thead>
            <tr>
                <th>Interface</th>
                <th>IPv4 Addresses</th>
            </tr>
        </thead>
        <tbody>
        {% for iface, ips in status.interfaces.items() %}
            <tr>
                <td><code>{{ iface }}</code></td>
                <td>{{ ips | join(", ") }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>

    <h2>Alert Files</h2>
    <table>
        <thead>
            <tr>
                <th>File</th>
                <th>Exists</th>
                <th>Size</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><code>alert_fast.txt</code></td>
                <td>{{ status.alerts.alert_fast_exists }}</td>
                <td>{{ status.alerts.alert_fast_size }}</td>
            </tr>
            <tr>
                <td><code>alerts.jsonl</code></td>
                <td>{{ status.alerts.alerts_jsonl_exists }}</td>
                <td>{{ status.alerts.alerts_jsonl_size }}</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""


def run_command(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def human_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.1f} GB"


def file_size(path: Path) -> str:
    if not path.exists():
        return "0 B"
    return human_size(path.stat().st_size)


def count_alerts() -> int:
    if not ALERTS_JSONL.exists():
        return 0

    count = 0
    with ALERTS_JSONL.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def get_uptime() -> str:
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            seconds = float(f.read().split()[0])

        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        if days:
            return f"{days}d {hours}h {minutes}m"
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return "unknown"


def get_memory() -> dict:
    try:
        meminfo = {}

        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                key, value = line.split(":", 1)
                meminfo[key] = int(value.strip().split()[0]) * 1024

        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", 0)
        used = total - available

        used_percent = round((used / total) * 100, 1) if total else 0

        return {
            "total": human_size(total),
            "used": human_size(used),
            "available": human_size(available),
            "used_percent": used_percent,
        }
    except Exception:
        return {
            "total": "unknown",
            "used": "unknown",
            "available": "unknown",
            "used_percent": "unknown",
        }


def get_disk() -> dict:
    usage = shutil.disk_usage(str(BASE_DIR))

    used_percent = round((usage.used / usage.total) * 100, 1)

    return {
        "total": human_size(usage.total),
        "used": human_size(usage.used),
        "free": human_size(usage.free),
        "used_percent": used_percent,
    }


def get_interfaces() -> dict:
    output = run_command(["ip", "-o", "-4", "addr", "show"])
    interfaces = {}

    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            iface = parts[1]
            ip_cidr = parts[3]
            interfaces.setdefault(iface, []).append(ip_cidr)

    return interfaces


def process_running(pattern: str) -> bool:
    output = run_command(["pgrep", "-af", pattern])
    return bool(output.strip())


def get_status() -> dict:
    load_average = os.getloadavg()
    load_text = f"{load_average[0]:.2f}, {load_average[1]:.2f}, {load_average[2]:.2f}"

    return {
        "hostname": socket.gethostname(),
        "uptime": get_uptime(),
        "load_average": load_text,
        "memory": get_memory(),
        "disk": get_disk(),
        "interfaces": get_interfaces(),
        "processes": {
            "snort": process_running("snort"),
            "watcher": process_running("snort_alert_watcher.py"),
            "dashboard": process_running("netsentry_dashboard.py"),
            "status_api": process_running("netsentry_status_api.py"),
            "adguard": process_running("AdGuardHome"),
        },
        "alerts": {
            "total_alerts": count_alerts(),
            "alert_fast_exists": ALERT_FAST.exists(),
            "alert_fast_size": file_size(ALERT_FAST),
            "alerts_jsonl_exists": ALERTS_JSONL.exists(),
            "alerts_jsonl_size": file_size(ALERTS_JSONL),
        },
    }


@app.route("/")
def index():
    status = get_status()
    return render_template_string(HTML_TEMPLATE, status=status)


@app.route("/api/status")
def api_status():
    return jsonify(get_status())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5051)
