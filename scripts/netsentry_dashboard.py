#!/usr/bin/env python3

from pathlib import Path
import json
from flask import Flask, jsonify, render_template_string

BASE_DIR = Path.home() / "netsentry-gateway"
ALERTS_JSONL = BASE_DIR / "snort" / "alerts" / "alerts.jsonl"

app = Flask(__name__)


HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>NetSentry V0 IDS Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #111;
            color: #eee;
            margin: 0;
            padding: 20px;
        }

        h1 {
            margin-bottom: 5px;
        }

        .subtitle {
            color: #aaa;
            margin-bottom: 20px;
        }

        .stats {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }

        .card {
            background: #1e1e1e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px;
        }

        .stat-number {
            font-size: 32px;
            font-weight: bold;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: #1a1a1a;
        }

        th, td {
            border-bottom: 1px solid #333;
            padding: 10px;
            text-align: left;
            font-size: 14px;
        }

        th {
            background: #222;
        }

        tr:hover {
            background: #252525;
        }

        .msg {
            font-weight: bold;
            color: #ffcc66;
        }

        .proto {
            color: #66ccff;
            font-weight: bold;
        }

        .empty {
            color: #aaa;
            padding: 20px;
            background: #1e1e1e;
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <h1>NetSentry V0 IDS Dashboard</h1>
    <div class="subtitle">
        Host-facing Snort IDS alerts from <code>alerts.jsonl</code>. Auto-refreshes every 5 seconds.
    </div>

    <div class="stats">
        <div class="card">
            <div>Total Alerts</div>
            <div class="stat-number">{{ total }}</div>
        </div>
        <div class="card">
            <div>Latest Source</div>
            <div class="stat-number" style="font-size: 22px;">{{ latest_src }}</div>
        </div>
        <div class="card">
            <div>Latest Protocol</div>
            <div class="stat-number" style="font-size: 22px;">{{ latest_proto }}</div>
        </div>
    </div>

    {% if alerts %}
    <table>
        <thead>
            <tr>
                <th>Received</th>
                <th>Message</th>
                <th>SID</th>
                <th>Protocol</th>
                <th>Source</th>
                <th>Destination</th>
                <th>Priority</th>
            </tr>
        </thead>
        <tbody>
        {% for alert in alerts %}
            <tr>
                <td>{{ alert.get("received_at", "unknown") }}</td>
                <td class="msg">{{ alert.get("message", "unknown") }}</td>
                <td>{{ alert.get("sid", "unknown") }}</td>
                <td class="proto">{{ alert.get("proto", "unknown") }}</td>
                <td>{{ alert.get("src", "unknown") }}</td>
                <td>{{ alert.get("dst", "unknown") }}</td>
                <td>{{ alert.get("priority", "unknown") }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
        <div class="empty">No alerts found yet. Start Snort, start the watcher, then trigger test traffic.</div>
    {% endif %}
</body>
</html>
"""


def read_alerts(limit: int = 50) -> list[dict]:
    if not ALERTS_JSONL.exists():
        return []

    alerts = []

    with ALERTS_JSONL.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                alerts.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return alerts[-limit:][::-1]


@app.route("/")
def dashboard():
    alerts = read_alerts(limit=50)

    latest = alerts[0] if alerts else {}

    return render_template_string(
        HTML_TEMPLATE,
        alerts=alerts,
        total=len(alerts),
        latest_src=latest.get("src", "-"),
        latest_proto=latest.get("proto", "-"),
    )


@app.route("/api/alerts")
def api_alerts():
    return jsonify(read_alerts(limit=100))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
