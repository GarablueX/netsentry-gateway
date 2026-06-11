#!/usr/bin/env python3

from flask import Flask, request, redirect, url_for, session, jsonify, render_template_string
from pathlib import Path
from datetime import datetime
from functools import wraps
from html import escape
import json
import hmac
import secrets
import subprocess



# ============================================================
# NetSentry Portal V1 - Local Configuration
# Change these later if needed.
# ============================================================

SERVER_IP = "192.168.1.19"
PORTAL_PORT = 5500

ADMIN_USER = "admin"
ADMIN_PASSWORD = "saifzedess"

# Change this later to any long random string.
# Example: python3 -c 'import secrets; print(secrets.token_hex(32))'
PORTAL_SECRET = "change_this_secret_later_please"

BASE_DIR = Path.home() / "netsentry-gateway"
LOG_DIR = BASE_DIR / "logs"

AUTH_LOG = LOG_DIR / "portal_auth_attempts.jsonl"
DECOY_LOG = LOG_DIR / "portal_decoy_attempts.jsonl"
PUBLIC_REPORT_LOG = LOG_DIR / "portal_public_reports.jsonl"

app = Flask(__name__)
app.secret_key = PORTAL_SECRET if PORTAL_SECRET != "change_this_secret_later_please" else secrets.token_hex(32)


# ============================================================
# Helpers
# ============================================================

def now():
    return datetime.now().isoformat(timespec="seconds")


def client_ip():
    return request.remote_addr or "unknown"


def safe(value):
    return escape(str(value or ""))


def write_jsonl(path: Path, entry: dict):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_jsonl(path: Path, limit: int = 100):
    if not path.exists():
        return []

    entries = []

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return entries[-limit:][::-1]


def log_real_admin_attempt(username: str, success: bool):
    """
    Real admin login logger.
    Submitted admin passwords are NEVER stored.
    """
    write_jsonl(
        AUTH_LOG,
        {
            "time": now(),
            "remote_addr": client_ip(),
            "path": request.path,
            "method": request.method,
            "username": username,
            "success": success,
            "password_logged": False,
            "user_agent": request.headers.get("User-Agent", ""),
        },
    )


def log_decoy_attempt(username: str = "", password: str = ""):
    """
    Decoy login logger.
    This is fake, so submitted passwords are intentionally captured.
    Do not reuse this behavior for the real admin login.
    """
    write_jsonl(
        DECOY_LOG,
        {
            "time": now(),
            "remote_addr": client_ip(),
            "path": request.path,
            "method": request.method,
            "username": username,
            "password": password,
            "user_agent": request.headers.get("User-Agent", ""),
        },
    )


def log_public_report(message: str, contact: str):
    write_jsonl(
        PUBLIC_REPORT_LOG,
        {
            "time": now(),
            "remote_addr": client_ip(),
            "path": request.path,
            "method": request.method,
            "message": message,
            "contact": contact,
            "user_agent": request.headers.get("User-Agent", ""),
        },
    )


def is_admin():
    return session.get("admin") is True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin():
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


# ============================================================
# UI
# ============================================================
def run_command(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def process_running(pattern: str) -> bool:
    output = run_command(["pgrep", "-af", pattern])
    return bool(output.strip())


def port_listening(port: int) -> bool:
    output = run_command(["ss", "-tulpen"])
    return f":{port}" in output


def get_public_status() -> dict:
    snort_running = process_running("snort")
    watcher_running = process_running("snort_alert_watcher.py")
    dashboard_running = port_listening(5050)
    status_api_running = port_listening(5051)
    honeypot_running = port_listening(8082)
    portal_running = port_listening(PORTAL_PORT)
    adguard_ui_running = port_listening(3001)
    adguard_dns_running = port_listening(53)

    monitoring_enabled = snort_running and watcher_running

    protected_services_active = (
        dashboard_running
        and status_api_running
        and honeypot_running
        and portal_running
        and adguard_ui_running
    )

    if monitoring_enabled and protected_services_active:
        overall = "Online"
        overall_class = "ok"
    elif portal_running:
        overall = "Degraded"
        overall_class = "warn"
    else:
        overall = "Offline"
        overall_class = "bad"

    return {
        "overall": overall,
        "overall_class": overall_class,
        "monitoring_enabled": monitoring_enabled,
        "protected_services_active": protected_services_active,
        "snort_running": snort_running,
        "watcher_running": watcher_running,
        "dashboard_running": dashboard_running,
        "status_api_running": status_api_running,
        "honeypot_running": honeypot_running,
        "portal_running": portal_running,
        "adguard_ui_running": adguard_ui_running,
        "adguard_dns_running": adguard_dns_running,
    }


def status_text(value: bool) -> str:
    return "RUNNING" if value else "STOPPED"


def status_class(value: bool) -> str:
    return "ok" if value else "bad"



STYLE = """
<style>
:root {
    --bg: #101014;
    --panel: #1b1b23;
    --panel2: #17171f;
    --border: #333342;
    --text: #eeeeee;
    --muted: #aaaaaa;
    --accent: #8dd7ff;
    --warn: #ffcc66;
    --ok: #74e291;
    --bad: #ff7777;
}

* {
    box-sizing: border-box;
}

body {
    font-family: Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    padding: 30px;
}

a {
    color: var(--accent);
}

.container {
    max-width: 1180px;
    margin: 0 auto;
}

.card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 22px;
    margin-bottom: 18px;
}

.grid-3 {
    display: grid;
    grid-template-columns: repeat(3, minmax(220px, 1fr));
    gap: 16px;
}

.grid-2 {
    display: grid;
    grid-template-columns: repeat(2, minmax(260px, 1fr));
    gap: 16px;
}

.button, button {
    display: inline-block;
    padding: 11px 14px;
    border-radius: 7px;
    border: 1px solid #555566;
    background: #29293a;
    color: var(--text);
    text-decoration: none;
    font-weight: bold;
    cursor: pointer;
    margin-right: 6px;
    margin-bottom: 6px;
}

.button:hover, button:hover {
    background: #3a3a50;
}

.button.danger {
    background: #481818;
    border-color: #8a3333;
}

input, textarea {
    width: 100%;
    padding: 10px;
    margin-bottom: 12px;
    border-radius: 6px;
    border: 1px solid #444455;
    background: #111118;
    color: var(--text);
}

label {
    display: block;
    margin-bottom: 6px;
    color: #cccccc;
}

.badge {
    display: inline-block;
    background: #29293a;
    border: 1px solid #444455;
    border-radius: 999px;
    padding: 5px 9px;
    font-size: 12px;
    color: #dddddd;
    margin-right: 6px;
    margin-bottom: 6px;
}

.ok {
    color: var(--ok);
    font-weight: bold;
}

.warn {
    color: var(--warn);
}

.bad {
    color: var(--bad);
    font-weight: bold;
}

.muted {
    color: var(--muted);
}

.error {
    background: #3a1717;
    border: 1px solid #7a2c2c;
    color: #ffaaaa;
    padding: 10px;
    border-radius: 7px;
    margin-bottom: 12px;
}

.success {
    background: #173a20;
    border: 1px solid #2c7a42;
    color: #aaffbd;
    padding: 10px;
    border-radius: 7px;
    margin-bottom: 12px;
}

.hero-title {
    font-size: 34px;
    margin-top: 0;
    margin-bottom: 8px;
}

.small {
    font-size: 13px;
}

code {
    color: var(--warn);
}

ul {
    line-height: 1.7;
}

table {
    width: 100%;
    border-collapse: collapse;
    background: var(--panel2);
    border: 1px solid var(--border);
    margin-top: 12px;
}

th, td {
    border-bottom: 1px solid var(--border);
    padding: 10px;
    text-align: left;
    vertical-align: top;
    font-size: 14px;
}

th {
    background: #22222d;
}

td {
    word-break: break-word;
}

@media (max-width: 850px) {
    .grid-3, .grid-2 {
        grid-template-columns: 1fr;
    }
}
</style>
"""


def page(title: str, body: str):
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
{STYLE}
</head>
<body>
<div class="container">
{body}
</div>
</body>
</html>
"""


# ============================================================
# Routes
# ============================================================

@app.route("/")
def landing():
    body = f"""
    <div class="card">
        <h1 class="hero-title">NetSentry Portal</h1>
        <p class="muted">Unified entry point for public information, admin access, and security lab pages.</p>
        <span class="badge">Server: {safe(SERVER_IP)}</span>
        <span class="badge">Portal: {PORTAL_PORT}</span>
        <span class="badge">Mode: Portal V1</span>
    </div>

    <div class="grid-3">
        <div class="card">
            <h2>Admin Console</h2>
            <p class="muted">Real admin login. Passwords are not logged.</p>
            <a class="button" href="/admin/login">Open Admin Console</a>
        </div>

        <div class="card">
            <h2>Public Services</h2>
            <p class="muted">Safe LAN-visible project information.</p>
            <a class="button" href="/public">Open Public Services</a>
        </div>

        <div class="card">
            <h2>Security Lab / Honeypot</h2>
            <p class="muted">Fake login pages. Attempts are logged.</p>
            <a class="button danger" href="/decoy-login">Open Honeypot</a>
        </div>
    </div>
    """
    return page("NetSentry Portal", body)

@app.route("/public")
def public_page():
    sent_box = ""
    if request.args.get("sent") == "1":
        sent_box = '<div class="success">Report submitted.</div>'

    status = get_public_status()

    monitoring_text = "Enabled" if status["monitoring_enabled"] else "Disabled"
    protected_text = "Active" if status["protected_services_active"] else "Degraded"

    body = f"""
    <div class="card">
        <h1>Public Services</h1>
        {sent_box}

        <p class="{status['overall_class']}">NetSentry Status: {status['overall']}</p>

        <p class="{status_class(status['protected_services_active'])}">
            Protected Services: {protected_text}
        </p>

        <p class="{status_class(status['monitoring_enabled'])}">
            Security Monitoring: {monitoring_text}
        </p>

        <p class="warn">This network is monitored when monitoring services are running.</p>

        <a class="button" href="/">Home</a>
        <a class="button" href="/api/public">Public API</a>
    </div>

    <div class="card">
        <h2>Live Public Status</h2>
        <table>
            <tr>
                <th>Component</th>
                <th>Status</th>
            </tr>
            <tr>
                <td>Portal 5500</td>
                <td class="{status_class(status['portal_running'])}">
                    {status_text(status['portal_running'])}
                </td>
            </tr>
            <tr>
                <td>Snort IDS</td>
                <td class="{status_class(status['snort_running'])}">
                    {status_text(status['snort_running'])}
                </td>
            </tr>
            <tr>
                <td>Snort Alert Watcher</td>
                <td class="{status_class(status['watcher_running'])}">
                    {status_text(status['watcher_running'])}
                </td>
            </tr>
            <tr>
                <td>IDS Dashboard 5050</td>
                <td class="{status_class(status['dashboard_running'])}">
                    {status_text(status['dashboard_running'])}
                </td>
            </tr>
            <tr>
                <td>Status API 5051</td>
                <td class="{status_class(status['status_api_running'])}">
                    {status_text(status['status_api_running'])}
                </td>
            </tr>
            <tr>
                <td>Honeypot-lite 8082</td>
                <td class="{status_class(status['honeypot_running'])}">
                    {status_text(status['honeypot_running'])}
                </td>
            </tr>
            <tr>
                <td>AdGuard UI 3001</td>
                <td class="{status_class(status['adguard_ui_running'])}">
                    {status_text(status['adguard_ui_running'])}
                </td>
            </tr>
            <tr>
                <td>AdGuard DNS 53</td>
                <td class="{status_class(status['adguard_dns_running'])}">
                    {status_text(status['adguard_dns_running'])}
                </td>
            </tr>
        </table>
    </div>

    <div class="grid-2">
        <div class="card">
            <h2>NetSentry Project Information</h2>
            <p>
                NetSentry is a local network security monitoring project using IDS alerts,
                firewall rules, protected services, and honeypot logging.
            </p>

            <h3>Basic Allowed Services</h3>
            <ul>
                <li>Public portal information</li>
                <li>Monitored security lab page</li>
                <li>Admin services for authorized users only</li>
            </ul>

            <h3>Guest Network Rules</h3>
            <ul>
                <li>Do not scan protected services.</li>
                <li>Do not attempt unauthorized login.</li>
                <li>Suspicious activity may be logged when monitoring is active.</li>
            </ul>
        </div>

        <div class="card">
            <h2>Public Security Tips</h2>
            <ul>
                <li>Use strong passwords.</li>
                <li>Do not reuse credentials.</li>
                <li>Do not submit real credentials to unknown login pages.</li>
                <li>Report suspicious network behavior.</li>
            </ul>

            <h3 class="warn">Honeypot Warning</h3>
            <p>Some pages in this lab are intentionally fake and monitored.</p>

            <h3>Educational Note</h3>
            <p>
                An IDS observes traffic and raises alerts.
                A firewall enforces access rules.
                A honeypot is a fake target designed to reveal suspicious behavior.
            </p>
        </div>
    </div>

    <div class="card">
        <h2>Contact / Report Suspicious Activity</h2>
        <form method="post" action="/public/report">
            <label>Message</label>
            <textarea name="message" rows="4" placeholder="Describe what happened..."></textarea>

            <label>Contact optional</label>
            <input name="contact" placeholder="Optional contact">

            <button type="submit">Submit Report</button>
        </form>
    </div>
    """
    return page("NetSentry Public", body)

@app.route("/public/report", methods=["POST"])
def public_report():
    message = request.form.get("message", "").strip()
    contact = request.form.get("contact", "").strip()

    if message:
        log_public_report(message, contact)

    return redirect(url_for("public_page", sent="1"))


@app.route("/admin/login", methods=["GET", "POST"])
@app.route("/portal/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    next_path = request.args.get("next", "/admin")

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        next_path = request.form.get("next", "/admin")

        success = (
            hmac.compare_digest(username, ADMIN_USER)
            and hmac.compare_digest(password, ADMIN_PASSWORD)
        )

        log_real_admin_attempt(username=username, success=success)

        if success:
            session["admin"] = True
            session["admin_user"] = username

            if not next_path.startswith("/admin"):
                next_path = "/admin"

            return redirect(next_path)

        error = "Invalid username or password."

    error_box = f'<div class="error">{safe(error)}</div>' if error else ""

    body = f"""
    <div class="card" style="max-width: 460px;">
        <h1>Admin Login</h1>
        <p class="muted">Real admin login. Submitted passwords are not logged.</p>
        {error_box}

        <form method="post" action="{safe(request.path)}">
            <input type="hidden" name="next" value="{safe(next_path)}">

            <label>Username</label>
            <input name="username" autocomplete="off">

            <label>Password</label>
            <input name="password" type="password" autocomplete="off">

            <button type="submit">Sign in</button>
        </form>

        <p class="warn">Authorized access only.</p>
        <a class="button" href="/">Home</a>
    </div>
    """
    return page("NetSentry Admin Login", body)


@app.route("/admin")
@login_required
def admin_home():
    body = """
    <div class="card">
        <h1>Admin Console</h1>
        <p class="ok">Authenticated admin session.</p>
        <p class="muted">
            Portal V1 home. Current admin modules are organized here.
            Native deep integration comes later.
        </p>
        <a class="button" href="/admin/ids">IDS Module</a>
        <a class="button" href="/admin/status">Status Module</a>
        <a class="button" href="/admin/adguard">AdGuard Module</a>
        <a class="button" href="/admin/events">Portal Events</a>
        <a class="button" href="/api/admin">Admin API</a>
        <a class="button" href="/logout">Logout</a>
    </div>

    <div class="grid-2">
        <div class="card">
            <h2>Current Role</h2>
            <ul>
                <li>Central admin entry point</li>
                <li>Real login gate</li>
                <li>Public/admin split</li>
                <li>Decoy login separation</li>
                <li>Portal event visibility</li>
            </ul>
        </div>

        <div class="card">
            <h2>Planned Reviewer Features</h2>
            <ul>
                <li>Attack timeline per source IP</li>
                <li>PCAP-on-alert for high-risk events</li>
                <li>Firewall log/drop visibility</li>
                <li>Evidence archive instead of destructive reset</li>
            </ul>
        </div>
    </div>
    """
    return page("NetSentry Admin", body)


@app.route("/admin/ids")
@login_required
def admin_ids():
    body = f"""
    <div class="card">
        <h1>IDS Module</h1>
        <p class="muted">
            Placeholder for future native IDS view inside the portal.
            For now, the existing IDS dashboard remains available separately.
        </p>
        <a class="button" href="/admin">Back Admin</a>
        <a class="button" href="http://{safe(SERVER_IP)}:5050">Open Existing IDS Dashboard</a>
    </div>

    <div class="card">
        <h2>Planned IDS Portal Features</h2>
        <ul>
            <li>Latest Snort alerts</li>
            <li>SID summary</li>
            <li>Source IP timeline</li>
            <li>Attack timeline per source</li>
            <li>PCAP-on-alert integration</li>
        </ul>
    </div>
    """
    return page("NetSentry IDS Module", body)


@app.route("/admin/status")
@login_required
def admin_status():
    body = f"""
    <div class="card">
        <h1>Status Module</h1>
        <p class="muted">
            Placeholder for future native system health view inside the portal.
            For now, the existing status page remains available separately.
        </p>
        <a class="button" href="/admin">Back Admin</a>
        <a class="button" href="http://{safe(SERVER_IP)}:5051">Open Existing Status API</a>
    </div>

    <div class="card">
        <h2>Planned Status Portal Features</h2>
        <ul>
            <li>Snort process status</li>
            <li>Watcher status</li>
            <li>Firewall rule state</li>
            <li>Alert file sizes</li>
            <li>Interface/IP summary</li>
        </ul>
    </div>
    """
    return page("NetSentry Status Module", body)


@app.route("/admin/adguard")
@login_required
def admin_adguard():
    body = f"""
    <div class="card">
        <h1>AdGuard Module</h1>
        <p class="muted">
            AdGuard is a separate service. For now this page keeps it organized under the portal.
        </p>
        <a class="button" href="/admin">Back Admin</a>
        <a class="button" href="http://{safe(SERVER_IP)}:3001">Open AdGuard UI</a>
    </div>
    """
    return page("NetSentry AdGuard Module", body)


@app.route("/admin/events")
@login_required
def admin_events():
    auth_events = read_jsonl(AUTH_LOG, limit=50)
    decoy_events = read_jsonl(DECOY_LOG, limit=50)
    public_reports = read_jsonl(PUBLIC_REPORT_LOG, limit=50)

    auth_rows = ""
    for event in auth_events:
        success = bool(event.get("success", False))
        status = "SUCCESS" if success else "FAILED"
        status_class = "ok" if success else "bad"

        auth_rows += f"""
        <tr>
            <td>{safe(event.get("time"))}</td>
            <td>{safe(event.get("remote_addr"))}</td>
            <td>{safe(event.get("path"))}</td>
            <td>{safe(event.get("username"))}</td>
            <td class="{status_class}">{status}</td>
            <td>{safe(event.get("user_agent"))}</td>
        </tr>
        """

    decoy_rows = ""
    for event in decoy_events:
        decoy_rows += f"""
        <tr>
            <td>{safe(event.get("time"))}</td>
            <td>{safe(event.get("remote_addr"))}</td>
            <td>{safe(event.get("path"))}</td>
            <td>{safe(event.get("method"))}</td>
            <td>{safe(event.get("username"))}</td>
            <td class="bad">{safe(event.get("password"))}</td>
            <td>{safe(event.get("user_agent"))}</td>
        </tr>
        """

    report_rows = ""
    for event in public_reports:
        report_rows += f"""
        <tr>
            <td>{safe(event.get("time"))}</td>
            <td>{safe(event.get("remote_addr"))}</td>
            <td>{safe(event.get("message"))}</td>
            <td>{safe(event.get("contact"))}</td>
            <td>{safe(event.get("user_agent"))}</td>
        </tr>
        """

    body = f"""
    <div class="card">
        <h1>Portal Events</h1>
        <p class="muted">
            Application-level portal logs. This is separate from Snort network alerts.
        </p>
        <a class="button" href="/admin">Back Admin</a>
    </div>

    <div class="card">
        <h2>Real Admin Login Attempts</h2>
        <p class="muted">Real admin passwords are not logged.</p>
        <table>
            <tr>
                <th>Time</th>
                <th>Source IP</th>
                <th>Path</th>
                <th>Username</th>
                <th>Status</th>
                <th>User-Agent</th>
            </tr>
            {auth_rows}
        </table>
    </div>

    <div class="card">
        <h2>Decoy / Honeypot Login Attempts</h2>
        <p class="warn">These are fake login pages. Submitted passwords are intentionally logged.</p>
        <table>
            <tr>
                <th>Time</th>
                <th>Source IP</th>
                <th>Path</th>
                <th>Method</th>
                <th>Username</th>
                <th>Password Tried</th>
                <th>User-Agent</th>
            </tr>
            {decoy_rows}
        </table>
    </div>

    <div class="card">
        <h2>Public Reports</h2>
        <table>
            <tr>
                <th>Time</th>
                <th>Source IP</th>
                <th>Message</th>
                <th>Contact</th>
                <th>User-Agent</th>
            </tr>
            {report_rows}
        </table>
    </div>
    """
    return page("NetSentry Portal Events", body)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/decoy-login", methods=["GET", "POST"])
@app.route("/admin-old", methods=["GET", "POST"])
@app.route("/wp-admin", methods=["GET", "POST"])
@app.route("/phpmyadmin", methods=["GET", "POST"])
@app.route("/decoy-login", methods=["GET"])
def decoy_login_redirect():
    return redirect(f"http://{SERVER_IP}:8082")


@app.route("/admin-old", methods=["GET", "POST"])
@app.route("/wp-admin", methods=["GET", "POST"])
@app.route("/phpmyadmin", methods=["GET", "POST"])
def decoy_login():
    error = ""

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        log_decoy_attempt(username=username, password=password)

        error = "Invalid username or password."
    else:
        log_decoy_attempt()

    error_box = f'<div class="error">{safe(error)}</div>' if error else ""

    body = f"""
    <div class="card" style="max-width: 460px;">
        <h1>NetSentry Admin</h1>
        <p class="muted">Management console</p>
        {error_box}

        <form method="post" action="{safe(request.path)}">
            <label>Username</label>
            <input name="username" autocomplete="off">

            <label>Password</label>
            <input name="password" type="password" autocomplete="off">

            <button type="submit">Sign in</button>
        </form>

        <p class="warn">Authorized access only.</p>
        <a class="button" href="/">Home</a>
    </div>
    """
    return page("NetSentry Decoy Login", body)
@app.route("/api/public")
def api_public():
    status = get_public_status()

    return jsonify(
        {
            "project": "NetSentry",
            "overall_status": status["overall"],
            "protected_services_active": status["protected_services_active"],
            "security_monitoring_enabled": status["monitoring_enabled"],
            "components": {
                "portal": status["portal_running"],
                "snort": status["snort_running"],
                "snort_alert_watcher": status["watcher_running"],
                "ids_dashboard": status["dashboard_running"],
                "status_api": status["status_api_running"],
                "honeypot_lite": status["honeypot_running"],
                "adguard_ui": status["adguard_ui_running"],
                "adguard_dns": status["adguard_dns_running"],
            },
            "message": "This network is monitored when Snort and the alert watcher are running.",
        }
    )

@app.route("/api/admin")
@login_required
def api_admin():
    return jsonify(
        {
            "project": "NetSentry",
            "admin": True,
            "server_ip": SERVER_IP,
            "portal_port": PORTAL_PORT,
            "mode": "portal_v1",
            "modules": {
                "ids": "/admin/ids",
                "status": "/admin/status",
                "adguard": "/admin/adguard",
                "events": "/admin/events",
            },
            "external_services": {
                "ids_dashboard": f"http://{SERVER_IP}:5050",
                "status_api": f"http://{SERVER_IP}:5051",
                "adguard": f"http://{SERVER_IP}:3001",
            },
            "logs": {
                "auth_attempts": str(AUTH_LOG),
                "decoy_attempts": str(DECOY_LOG),
                "public_reports": str(PUBLIC_REPORT_LOG),
            },
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORTAL_PORT)
