#!/usr/bin/env python3

import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string


# -----------------------------
# NetSentry paths / constants
# -----------------------------

BASE_DIR = Path("/home/gbx/netsentry-gateway")

ALERTS_JSONL = BASE_DIR / "snort/alerts/alerts.jsonl"
ALERT_FAST = BASE_DIR / "snort/alerts/alert_fast.txt"

HONEYPOT_LOG = BASE_DIR / "logs/honeypot_lite_attempts.jsonl"
PORTAL_AUTH_LOG = BASE_DIR / "logs/portal_auth_attempts.jsonl"
PORTAL_DECOY_LOG = BASE_DIR / "logs/portal_decoy_attempts.jsonl"

DNSMASQ_LEASE_FILES = [
    Path("/var/lib/misc/dnsmasq.leases"),
    Path("/var/lib/misc/dnsmasq-netsentry.leases"),
    Path("/tmp/dnsmasq.leases"),
]

WAN_INTERFACE = "enp3s0"
AP_INTERFACE = "wlx200db0220b9a"

HOME_LAN = "192.168.1.0/24"
AP_LAN = "10.10.10.0/24"

NETSENTRY_HOME_IP = "192.168.1.19"
NETSENTRY_AP_IP = "10.10.10.1"


# -----------------------------
# Flask app
# -----------------------------

app = Flask(__name__)


# -----------------------------
# Helper functions
# -----------------------------

def run_cmd(command, timeout=3):
    """
    Runs a Linux command and returns stdout/stderr safely.

    This is read-only usage for V1.
    Do not use this for dangerous write actions from the web app.
    """
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )

        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    except Exception as error:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(error),
        }


def get_uptime():
    """
    Reads /proc/uptime and converts seconds into a readable value.
    """
    try:
        raw_seconds = float(Path("/proc/uptime").read_text().split()[0])
    except Exception:
        return "unknown"

    days = int(raw_seconds // 86400)
    hours = int((raw_seconds % 86400) // 3600)
    minutes = int((raw_seconds % 3600) // 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m"

    if hours > 0:
        return f"{hours}h {minutes}m"

    return f"{minutes}m"


def internet_is_reachable():
    """
    Simple internet reachability check.

    It tries to open a TCP connection to Cloudflare DNS.
    It does not send a DNS query.
    """
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2).close()
        return True
    except OSError:
        return False


def read_jsonl_tail(path, limit=100):
    """
    Reads the last N lines of a JSONL log file.

    If a line is not valid JSON, it is returned as raw text.
    """
    if not path.exists():
        return []

    lines = path.read_text(errors="ignore").splitlines()
    items = []

    for line in lines[-limit:]:
        line = line.strip()

        if not line:
            continue

        try:
            items.append(json.loads(line))
        except Exception:
            items.append({"raw": line})

    return items


def read_text_tail(path, limit=100):
    """
    Reads the last N lines of a plain text file.
    """
    if not path.exists():
        return []

    return path.read_text(errors="ignore").splitlines()[-limit:]


def get_status_data():
    """
    Public-safe gateway status.

    This data is safe for /status and /api/status.
    It does not expose clients, alerts, firewall rules, or logs.
    """
    return {
        "gateway": "online",
        "internet": "online" if internet_is_reachable() else "offline",
        "uptime": get_uptime(),
        "last_update": datetime.now().isoformat(timespec="seconds"),
    }


def get_interfaces_data():
    """
    Returns interface state using ip -br addr.
    """
    return run_cmd(["ip", "-br", "addr"])


def get_routes_data():
    """
    Returns Linux routing table.
    """
    return run_cmd(["ip", "route"])


def get_firewall_rules_data():
    """
    Returns read-only iptables firewall state.

    sudo -n means:
    - do not ask for password
    - fail if sudo permission is not available

    If this fails, we later fix with a safe read-only sudoers rule
    or with a privileged agent in V2.
    """
    input_rules = run_cmd(
        ["sudo", "-n", "iptables", "-L", "INPUT", "-n", "-v", "--line-numbers"]
    )

    forward_rules = run_cmd(
        ["sudo", "-n", "iptables", "-L", "FORWARD", "-n", "-v", "--line-numbers"]
    )

    nat_rules = run_cmd(
        ["sudo", "-n", "iptables", "-t", "nat", "-L", "-n", "-v", "--line-numbers"]
    )

    return {
        "input": input_rules,
        "forward": forward_rules,
        "nat": nat_rules,
    }


def get_alerts_data(limit=100):
    """
    Reads parsed Snort alerts from alerts.jsonl.
    """
    return {
        "source": str(ALERTS_JSONL),
        "alerts": read_jsonl_tail(ALERTS_JSONL, limit=limit),
    }


def get_clients_data():
    """
    Reads dnsmasq leases if available.
    """
    lease_file = None

    for candidate in DNSMASQ_LEASE_FILES:
        if candidate.exists():
            lease_file = candidate
            break

    if lease_file is None:
        return {
            "lease_file": None,
            "clients": [],
            "warning": "No dnsmasq lease file found.",
        }

    clients = []

    for line in lease_file.read_text(errors="ignore").splitlines():
        parts = line.split()

        if len(parts) >= 4:
            expires = parts[0]
            mac = parts[1]
            ip = parts[2]
            hostname = parts[3]

            clients.append({
                "expires": expires,
                "mac": mac,
                "ip": ip,
                "hostname": hostname,
            })

    return {
        "lease_file": str(lease_file),
        "clients": clients,
        "warning": None,
    }


def get_logs_data():
    """
    Reads current NetSentry JSONL logs.
    """
    return {
        "honeypot": read_jsonl_tail(HONEYPOT_LOG, limit=50),
        "portal_auth": read_jsonl_tail(PORTAL_AUTH_LOG, limit=50),
        "portal_decoy": read_jsonl_tail(PORTAL_DECOY_LOG, limit=50),
    }


# -----------------------------
# HTML layout
# -----------------------------

def render_page(title, content):
    """
    Temporary single-file HTML renderer.

    Later we can move this to templates/base.html.
    For now, this keeps the app easy to understand.
    """
    html = """
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{{ title }} - NetSentry</title>

        <style>
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #0f172a;
                color: #e5e7eb;
            }

            header {
                background: #020617;
                padding: 20px 26px;
                border-bottom: 1px solid #1e293b;
            }

            header h1 {
                margin: 0;
                font-size: 24px;
            }

            header p {
                margin: 6px 0 0;
                color: #94a3b8;
            }

            nav {
                background: #111827;
                padding: 12px 26px;
                border-bottom: 1px solid #1f2937;
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
            }

            nav a {
                color: #93c5fd;
                text-decoration: none;
                font-size: 14px;
            }

            nav a:hover {
                color: white;
            }

            main {
                padding: 26px;
                max-width: 1200px;
            }

            .card {
                background: #111827;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 18px;
                margin-bottom: 16px;
            }

            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 14px;
                margin-bottom: 16px;
            }

            .metric {
                background: #020617;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 16px;
            }

            .metric strong {
                display: block;
                font-size: 22px;
                margin-top: 6px;
            }

            code, pre {
                background: #020617;
                color: #d1d5db;
                border: 1px solid #334155;
                border-radius: 8px;
            }

            code {
                padding: 2px 5px;
            }

            pre {
                padding: 12px;
                overflow-x: auto;
                white-space: pre-wrap;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                background: #020617;
                border: 1px solid #334155;
            }

            th, td {
                border-bottom: 1px solid #1f2937;
                padding: 8px;
                text-align: left;
                font-size: 14px;
            }

            th {
                color: #93c5fd;
            }

            .ok {
                color: #22c55e;
                font-weight: bold;
            }

            .bad {
                color: #ef4444;
                font-weight: bold;
            }

            .muted {
                color: #94a3b8;
            }
        </style>
    </head>

    <body>
        <header>
            <h1>NetSentry Gateway</h1>
            <p>v1.6 Unified Flask Web Foundation</p>
        </header>

        <nav>
            <a href="/">Home</a>
            <a href="/about">About</a>
            <a href="/features">Features</a>
            <a href="/architecture">Architecture</a>
            <a href="/status">Status</a>
            <a href="/docs">Docs</a>
            <a href="/hardware">Hardware</a>

            <span class="muted">|</span>

            <a href="/admin/dashboard">Dashboard</a>
            <a href="/admin/clients">Clients</a>
            <a href="/admin/dns">DNS</a>
            <a href="/admin/firewall">Firewall</a>
            <a href="/admin/ids">IDS</a>
            <a href="/admin/logs">Logs</a>
            <a href="/admin/network">Network</a>
        </nav>

        <main>
            <h2>{{ title }}</h2>
            {{ content|safe }}
        </main>
    </body>
    </html>
    """

    return render_template_string(html, title=title, content=content)


# -----------------------------
# Public routes
# -----------------------------

@app.route("/")
def public_home():
    content = """
    <div class="card">
        <h3>Secure Debian Gateway</h3>
        <p>
            NetSentry is a Debian-based gateway that provides controlled Wi-Fi access,
            DHCP, DNS filtering, firewalling, routing, IDS visibility, logs, and a
            web dashboard.
        </p>
    </div>

    <div class="grid">
        <div class="metric">Gateway Mode<strong>Active</strong></div>
        <div class="metric">Home LAN<strong>192.168.1.0/24</strong></div>
        <div class="metric">AP LAN<strong>10.10.10.0/24</strong></div>
        <div class="metric">Version<strong>v1.6</strong></div>
    </div>
    """

    return render_page("Home", content)


@app.route("/about")
def public_about():
    content = """
    <div class="card">
        <p>
            NetSentry is a lab-built security gateway. It sits between an upstream
            home/ISP LAN and a controlled AP/client LAN.
        </p>
        <p>
            Its goal is to provide practical security visibility: DNS filtering,
            firewall policy, IDS alerts, honeypot logging, and gateway monitoring.
        </p>
    </div>
    """

    return render_page("About", content)


@app.route("/features")
def public_features():
    content = """
    <div class="card">
        <ul>
            <li>Wi-Fi access point using hostapd</li>
            <li>DHCP for AP clients using dnsmasq</li>
            <li>DNS filtering through AdGuard Home</li>
            <li>Gateway NAT and LAN-to-LAN routing</li>
            <li>iptables gateway firewall policy</li>
            <li>Snort IDS alert pipeline</li>
            <li>Honeypot and log collection</li>
            <li>Unified Flask web interface</li>
        </ul>
    </div>
    """

    return render_page("Features", content)


@app.route("/architecture")
def public_architecture():
    content = f"""
    <div class="card">
        <h3>Web Architecture</h3>
        <pre>
Browser
  ↓
Nginx :80/:443
  ↓
Flask App :5000 localhost only
  ├── Public website
  ├── Admin dashboard
  └── API
        </pre>
    </div>

    <div class="card">
        <h3>Network Architecture</h3>
        <pre>
HOME LAN: {HOME_LAN}
  NetSentry: {NETSENTRY_HOME_IP} on {WAN_INTERFACE}

AP LAN: {AP_LAN}
  NetSentry: {NETSENTRY_AP_IP} on {AP_INTERFACE}
        </pre>
    </div>
    """

    return render_page("Architecture", content)


@app.route("/status")
def public_status():
    status = get_status_data()

    internet_class = "ok" if status["internet"] == "online" else "bad"

    content = f"""
    <div class="grid">
        <div class="metric">Gateway<strong class="ok">{status["gateway"]}</strong></div>
        <div class="metric">Internet<strong class="{internet_class}">{status["internet"]}</strong></div>
        <div class="metric">Uptime<strong>{status["uptime"]}</strong></div>
        <div class="metric">Updated<strong>{status["last_update"]}</strong></div>
    </div>

    <div class="card">
        <p class="muted">
            Public status is intentionally safe. It does not expose clients,
            firewall rules, Snort alerts, DNS logs, or internal service details.
        </p>
    </div>
    """

    return render_page("Status", content)


@app.route("/docs")
def public_docs():
    docs_dir = BASE_DIR / "docs"
    items = []

    if docs_dir.exists():
        for doc in sorted(docs_dir.glob("*.md")):
            items.append(f"<li><code>{doc.name}</code></li>")

    content = f"""
    <div class="card">
        <p>Documentation lives in the repository under <code>docs/</code>.</p>
        <ul>
            {''.join(items) if items else '<li>No docs found.</li>'}
        </ul>
    </div>
    """

    return render_page("Docs", content)


@app.route("/hardware")
def public_hardware():
    content = f"""
    <div class="card">
        <table>
            <tr><th>Component</th><th>Role</th></tr>
            <tr><td>Debian Server</td><td>Gateway, firewall, router, app host</td></tr>
            <tr><td>{WAN_INTERFACE}</td><td>Home / ISP LAN side</td></tr>
            <tr><td>{AP_INTERFACE}</td><td>AP / client LAN side</td></tr>
            <tr><td>AP IP</td><td>{NETSENTRY_AP_IP}/24</td></tr>
            <tr><td>Home IP</td><td>{NETSENTRY_HOME_IP}/24</td></tr>
        </table>
    </div>
    """

    return render_page("Hardware", content)


# -----------------------------
# Admin routes
# -----------------------------

@app.route("/admin/dashboard")
def admin_dashboard():
    status = get_status_data()
    clients = get_clients_data()
    alerts = get_alerts_data(limit=100)

    content = f"""
    <div class="grid">
        <div class="metric">Internet<strong>{status["internet"]}</strong></div>
        <div class="metric">Uptime<strong>{status["uptime"]}</strong></div>
        <div class="metric">Clients<strong>{len(clients["clients"])}</strong></div>
        <div class="metric">Recent Alerts<strong>{len(alerts["alerts"])}</strong></div>
    </div>

    <div class="card">
        <p>
            This dashboard is read-only in v1.6. Control actions come later through
            a privileged agent.
        </p>
    </div>
    """

    return render_page("Admin Dashboard", content)


@app.route("/admin/clients")
def admin_clients():
    data = get_clients_data()

    rows = ""

    for client in data["clients"]:
        rows += (
            "<tr>"
            f"<td>{client['ip']}</td>"
            f"<td>{client['mac']}</td>"
            f"<td>{client['hostname']}</td>"
            f"<td>{client['expires']}</td>"
            "</tr>"
        )

    content = f"""
    <div class="card">
        <p>Lease file: <code>{data["lease_file"]}</code></p>
        <table>
            <tr><th>IP</th><th>MAC</th><th>Hostname</th><th>Expires</th></tr>
            {rows if rows else '<tr><td colspan="4">No clients found.</td></tr>'}
        </table>
    </div>
    """

    return render_page("Clients", content)


@app.route("/admin/dns")
def admin_dns():
    content = """
    <div class="card">
        <p>DNS page placeholder.</p>
        <p>Next implementation: read AdGuard statistics safely.</p>
    </div>
    """

    return render_page("DNS", content)


@app.route("/admin/firewall")
def admin_firewall():
    rules = get_firewall_rules_data()

    content = f"""
    <div class="card">
        <h3>INPUT</h3>
        <pre>{rules["input"]["stdout"] or rules["input"]["stderr"]}</pre>
    </div>

    <div class="card">
        <h3>FORWARD</h3>
        <pre>{rules["forward"]["stdout"] or rules["forward"]["stderr"]}</pre>
    </div>

    <div class="card">
        <h3>NAT</h3>
        <pre>{rules["nat"]["stdout"] or rules["nat"]["stderr"]}</pre>
    </div>
    """

    return render_page("Firewall", content)


@app.route("/admin/ids")
def admin_ids():
    data = get_alerts_data(limit=100)
    rows = ""

    for alert in reversed(data["alerts"]):
        rows += (
            "<tr>"
            f"<td>{alert.get('timestamp') or alert.get('received_at') or ''}</td>"
            f"<td>{alert.get('sid', '')}</td>"
            f"<td>{alert.get('message', alert.get('raw', ''))}</td>"
            f"<td>{alert.get('src', '')}</td>"
            f"<td>{alert.get('dst', '')}</td>"
            f"<td>{alert.get('proto', '')}</td>"
            "</tr>"
        )

    content = f"""
    <div class="card">
        <p>Source: <code>{data["source"]}</code></p>
        <table>
            <tr>
                <th>Time</th>
                <th>SID</th>
                <th>Message</th>
                <th>Source</th>
                <th>Destination</th>
                <th>Protocol</th>
            </tr>
            {rows if rows else '<tr><td colspan="6">No alerts found.</td></tr>'}
        </table>
    </div>
    """

    return render_page("IDS", content)


@app.route("/admin/logs")
def admin_logs():
    logs = get_logs_data()

    content = f"""
    <div class="card">
        <h3>Honeypot</h3>
        <pre>{json.dumps(logs["honeypot"], indent=2)}</pre>
    </div>

    <div class="card">
        <h3>Portal Auth</h3>
        <pre>{json.dumps(logs["portal_auth"], indent=2)}</pre>
    </div>

    <div class="card">
        <h3>Portal Decoy</h3>
        <pre>{json.dumps(logs["portal_decoy"], indent=2)}</pre>
    </div>
    """

    return render_page("Logs", content)


@app.route("/admin/network")
def admin_network():
    interfaces = get_interfaces_data()
    routes = get_routes_data()
    ports = run_cmd(["ss", "-tulpen"], timeout=3)

    content = f"""
    <div class="card">
        <h3>Interfaces</h3>
        <pre>{interfaces["stdout"] or interfaces["stderr"]}</pre>
    </div>

    <div class="card">
        <h3>Routes</h3>
        <pre>{routes["stdout"] or routes["stderr"]}</pre>
    </div>

    <div class="card">
        <h3>Listening Ports</h3>
        <pre>{ports["stdout"] or ports["stderr"]}</pre>
    </div>
    """

    return render_page("Network", content)


# -----------------------------
# API routes
# -----------------------------

@app.route("/api/status")
def api_status():
    return jsonify(get_status_data())


@app.route("/api/network/interfaces")
def api_network_interfaces():
    return jsonify(get_interfaces_data())


@app.route("/api/network/routes")
def api_network_routes():
    return jsonify(get_routes_data())


@app.route("/api/ids/alerts")
def api_ids_alerts():
    return jsonify(get_alerts_data(limit=100))


@app.route("/api/firewall/rules")
def api_firewall_rules():
    return jsonify(get_firewall_rules_data())


# -----------------------------
# Run app
# -----------------------------

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
