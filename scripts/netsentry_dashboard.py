#!/usr/bin/env python3

from pathlib import Path
import json
from flask import Flask, jsonify, render_template_string, request, redirect, url_for

BASE_DIR = Path.home() / "netsentry-gateway"
ALERTS_JSONL = BASE_DIR / "snort" / "alerts" / "alerts.jsonl"
ALERT_FAST = BASE_DIR / "snort" / "alerts" / "alert_fast.txt"

app = Flask(__name__)


SID_NAMES = {
    "10000001": "ICMP Ping",
    "10000002": "SSH SYN Probe",
    "10000003": "SSH Brute-force / Scan",
    "10000004": "AdGuard UI Attempt",
    "10000005": "DNS Query",
    "10000006": "Dashboard Access Attempt",
    "10000009": "HTTP Test Service Access",
    "10000010": "HTTP /admin Probe",
    "10000011": "HTTP /login Probe",
    "10000012": "HTTP /.env Probe",
    "10000013": "HTTP /wp-login.php Probe",
    "10000014": "HTTP /phpmyadmin Probe",
}


HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>NetSentry V0 IDS Dashboard</title>
    <meta http-equiv="refresh" content="10">
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

        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
        }

        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 999px;
            background: #2a2a35;
            color: #dddddd;
            font-size: 12px;
            font-weight: bold;
        }

        .stats, .summary {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        .card {
            background: #1b1b23;
            border: 1px solid #333342;
            border-radius: 8px;
            padding: 15px;
            min-width: 160px;
        }

        .summary-card {
            background: #181820;
            border: 1px solid #333342;
            border-radius: 8px;
            padding: 14px;
            min-width: 190px;
        }

        .stat-label {
            color: #aaaaaa;
            font-size: 13px;
            margin-bottom: 6px;
        }

        .stat-number {
            font-size: 30px;
            font-weight: bold;
        }

        .summary-title {
            color: #cccccc;
            font-size: 13px;
            margin-bottom: 6px;
        }

        .summary-count {
            font-size: 28px;
            font-weight: bold;
            color: #ffcc66;
        }

        .filters {
            background: #1b1b23;
            border: 1px solid #333342;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }

        .filters form {
            display: grid;
            grid-template-columns: repeat(4, minmax(150px, 1fr));
            gap: 12px;
            align-items: end;
        }

        label {
            display: block;
            color: #bbbbbb;
            font-size: 12px;
            margin-bottom: 5px;
        }

        input, select {
            width: 100%;
            box-sizing: border-box;
            padding: 8px;
            border-radius: 5px;
            border: 1px solid #444455;
            background: #111118;
            color: #eeeeee;
        }

        button, a.button {
            padding: 9px 12px;
            border-radius: 5px;
            border: 1px solid #555566;
            background: #272735;
            color: #eeeeee;
            cursor: pointer;
            text-decoration: none;
            text-align: center;
            font-size: 14px;
            display: inline-block;
        }

        button:hover, a.button:hover {
            background: #353548;
        }

        .danger {
            background: #4a1515;
            border-color: #8a2f2f;
        }

        .danger:hover {
            background: #6b1c1c;
        }

        .actions {
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: #17171f;
            border: 1px solid #333342;
        }

        th, td {
            border-bottom: 1px solid #333342;
            padding: 10px;
            text-align: left;
            font-size: 14px;
            vertical-align: top;
        }

        th {
            background: #22222d;
            color: #dddddd;
            position: sticky;
            top: 0;
        }

        tr:hover {
            background: #22222d;
        }

        .msg {
            font-weight: bold;
            color: #ffcc66;
        }

        .proto {
            display: inline-block;
            min-width: 42px;
            text-align: center;
            padding: 3px 7px;
            border-radius: 999px;
            background: #14324a;
            color: #8dd7ff;
            font-weight: bold;
            font-size: 12px;
        }

        .sid {
            color: #b5a7ff;
            font-family: monospace;
        }

        .ip {
            font-family: monospace;
            color: #dddddd;
        }

        .port {
            color: #ff9f6e;
            font-weight: bold;
        }

        .empty {
            color: #aaaaaa;
            padding: 20px;
            background: #1b1b23;
            border-radius: 8px;
            border: 1px solid #333342;
        }

        .raw {
            color: #888888;
            font-size: 12px;
            max-width: 420px;
            word-break: break-word;
        }

        .section-title {
            margin-top: 25px;
            margin-bottom: 10px;
            color: #eeeeee;
        }

        @media (max-width: 900px) {
            .filters form {
                grid-template-columns: 1fr;
            }

            .topbar {
                display: block;
            }
        }
    </style>
</head>
<body>
    <div class="topbar">
        <div>
            <h1>NetSentry V0 IDS Dashboard</h1>
            <div class="subtitle">
                Host-facing Snort IDS alerts from <code>alerts.jsonl</code>. Auto-refreshes every 10 seconds.
            </div>
        </div>
        <div>
            <span class="badge">Protected Dashboard</span>
            <span class="badge">Admin: 192.168.1.11</span>
        </div>
    </div>

    <div class="actions">
        <form method="post" action="/reset" onsubmit="return confirm('Clear all dashboard alerts? This will empty alert_fast.txt and alerts.jsonl.');">
            <button class="danger" type="submit">Reset Dashboard Alerts</button>
        </form>
        <a class="button" href="/">Refresh / Clear Filters</a>
        <a class="button" href="/api/alerts">API JSON</a>
    </div>

    <div class="stats">
        <div class="card">
            <div class="stat-label">Total Alerts Loaded</div>
            <div class="stat-number">{{ total_all }}</div>
        </div>
        <div class="card">
            <div class="stat-label">Matching Filters</div>
            <div class="stat-number">{{ total_filtered }}</div>
        </div>
        <div class="card">
            <div class="stat-label">Latest Source</div>
            <div class="stat-number" style="font-size: 20px;">{{ latest_src }}</div>
        </div>
        <div class="card">
            <div class="stat-label">Latest Destination Port</div>
            <div class="stat-number" style="font-size: 20px;">{{ latest_dst_port }}</div>
        </div>
        <div class="card">
            <div class="stat-label">Latest SID</div>
            <div class="stat-number" style="font-size: 20px;">{{ latest_sid }}</div>
        </div>
    </div>

    <h2 class="section-title">Alert Summary by Type</h2>
    <div class="summary">
        {% for sid, name, count in summary_cards %}
        <div class="summary-card">
            <div class="summary-title">{{ name }}</div>
            <div class="summary-count">{{ count }}</div>
            <div class="sid">SID {{ sid }}</div>
        </div>
        {% endfor %}
    </div>

    <div class="filters">
        <form method="get" action="/">
            <div>
                <label>Source IP</label>
                <input name="src" value="{{ filters.get('src', '') }}" placeholder="192.168.1.x">
            </div>

            <div>
                <label>Destination IP</label>
                <input name="dst" value="{{ filters.get('dst', '') }}" placeholder="192.168.1.17">
            </div>

            <div>
                <label>Destination Port</label>
                <input name="dst_port" value="{{ filters.get('dst_port', '') }}" placeholder="22 / 3001 / 5050">
            </div>

            <div>
                <label>Protocol</label>
                <select name="proto">
                    <option value="">Any</option>
                    {% for p in proto_values %}
                    <option value="{{ p }}" {% if filters.get('proto') == p %}selected{% endif %}>{{ p }}</option>
                    {% endfor %}
                </select>
            </div>

            <div>
                <label>SID</label>
                <input name="sid" value="{{ filters.get('sid', '') }}" placeholder="10000002">
            </div>

            <div>
                <label>REV</label>
                <input name="rev" value="{{ filters.get('rev', '') }}" placeholder="1 / 2 / 4">
            </div>

            <div>
                <label>Message contains</label>
                <input name="q" value="{{ filters.get('q', '') }}" placeholder="SSH / Dashboard / ICMP">
            </div>

            <div>
                <button type="submit">Apply Filters</button>
                <a class="button" href="/">Clear</a>
            </div>
        </form>
    </div>

    {% if alerts %}
    <table>
        <thead>
            <tr>
                <th>Received</th>
                <th>Message</th>
                <th>SID:REV</th>
                <th>Protocol</th>
                <th>Source</th>
                <th>Destination</th>
                <th>Priority</th>
                <th>Raw</th>
            </tr>
        </thead>
        <tbody>
        {% for alert in alerts %}
            <tr>
                <td>{{ alert.get("received_at", "unknown") }}</td>
                <td class="msg">{{ alert.get("message", "unknown") }}</td>
                <td class="sid">{{ alert.get("sid", "unknown") }}:{{ alert.get("rev", "unknown") }}</td>
                <td><span class="proto">{{ alert.get("proto", "unknown") }}</span></td>
                <td class="ip">
                    {{ alert.get("src", "unknown") }}
                    {% if alert.get("src_port") %}
                    :<span class="port">{{ alert.get("src_port") }}</span>
                    {% endif %}
                </td>
                <td class="ip">
                    {{ alert.get("dst", "unknown") }}
                    {% if alert.get("dst_port") %}
                    :<span class="port">{{ alert.get("dst_port") }}</span>
                    {% endif %}
                </td>
                <td>{{ alert.get("priority", "unknown") }}</td>
                <td class="raw">{{ alert.get("raw", "") }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
        <div class="empty">No alerts match the current filters, or the dashboard was reset.</div>
    {% endif %}
</body>
</html>
"""


def read_alerts(limit: int = 500) -> list[dict]:
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


def contains_filter(value: str, needle: str) -> bool:
    if not needle:
        return True
    return needle.lower() in str(value or "").lower()


def exact_filter(value: str, expected: str) -> bool:
    if not expected:
        return True
    return str(value or "").lower() == expected.lower()


def apply_filters(alerts: list[dict], filters: dict) -> list[dict]:
    filtered = []

    for alert in alerts:
        if not contains_filter(alert.get("src", ""), filters.get("src", "")):
            continue

        if not contains_filter(alert.get("dst", ""), filters.get("dst", "")):
            continue

        if not exact_filter(alert.get("dst_port", ""), filters.get("dst_port", "")):
            continue

        if not exact_filter(alert.get("proto", ""), filters.get("proto", "")):
            continue

        if not exact_filter(alert.get("sid", ""), filters.get("sid", "")):
            continue

        if not exact_filter(alert.get("rev", ""), filters.get("rev", "")):
            continue

        if not contains_filter(alert.get("message", ""), filters.get("q", "")):
            continue

        filtered.append(alert)

    return filtered


def get_filters() -> dict:
    return {
        "src": request.args.get("src", "").strip(),
        "dst": request.args.get("dst", "").strip(),
        "dst_port": request.args.get("dst_port", "").strip(),
        "proto": request.args.get("proto", "").strip(),
        "sid": request.args.get("sid", "").strip(),
        "rev": request.args.get("rev", "").strip(),
        "q": request.args.get("q", "").strip(),
    }


def build_summary(alerts: list[dict]) -> list[tuple[str, str, int]]:
    counts = {sid: 0 for sid in SID_NAMES}

    for alert in alerts:
        sid = str(alert.get("sid", ""))
        if sid in counts:
            counts[sid] += 1

    return [
        (sid, name, counts.get(sid, 0))
        for sid, name in SID_NAMES.items()
    ]


def reset_alert_files() -> None:
    ALERTS_JSONL.parent.mkdir(parents=True, exist_ok=True)

    ALERT_FAST.write_text("", encoding="utf-8")
    ALERTS_JSONL.write_text("", encoding="utf-8")


@app.route("/")
def dashboard():
    all_alerts = read_alerts(limit=500)
    filters = get_filters()
    filtered_alerts = apply_filters(all_alerts, filters)

    latest = filtered_alerts[0] if filtered_alerts else {}

    proto_values = sorted({
        alert.get("proto", "")
        for alert in all_alerts
        if alert.get("proto", "")
    })

    summary_cards = build_summary(all_alerts)

    return render_template_string(
        HTML_TEMPLATE,
        alerts=filtered_alerts[:100],
        total_all=len(all_alerts),
        total_filtered=len(filtered_alerts),
        latest_src=latest.get("src", "-"),
        latest_dst_port=latest.get("dst_port", "-"),
        latest_sid=latest.get("sid", "-"),
        filters=filters,
        proto_values=proto_values,
        summary_cards=summary_cards,
    )


@app.route("/reset", methods=["POST"])
def reset_dashboard():
    reset_alert_files()
    return redirect(url_for("dashboard"))


@app.route("/api/alerts")
def api_alerts():
    all_alerts = read_alerts(limit=500)
    filters = get_filters()
    return jsonify(apply_filters(all_alerts, filters))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
