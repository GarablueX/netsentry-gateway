#!/usr/bin/env python3
"""
NetSentry Unified Web App
V1 full read-only monitoring interface.

Architecture:
Browser -> Nginx :80/:443 -> Flask 127.0.0.1:5000

This app is intentionally read-only. It does not modify firewall rules,
restart services, or start packet captures. Those actions belong in a later
privileged agent.
"""

import base64
import hmac
import json
import os
import secrets
import shutil
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash


# ============================================================
# NetSentry constants — matches your current gateway deployment
# ============================================================

BASE_DIR = Path(os.getenv("NETSENTRY_BASE_DIR", "/home/gbx/netsentry-gateway"))

WAN_INTERFACE = os.getenv("NETSENTRY_WAN_INTERFACE", "enp3s0")
AP_INTERFACE = os.getenv("NETSENTRY_AP_INTERFACE", "wlx200db0220b9a")

HOME_LAN = os.getenv("NETSENTRY_HOME_LAN", "192.168.1.0/24")
AP_LAN = os.getenv("NETSENTRY_AP_LAN", "10.10.10.0/24")

ADMIN_IP = os.getenv("NETSENTRY_ADMIN_IP", "192.168.1.11")
NETSENTRY_HOME_IP = os.getenv("NETSENTRY_HOME_IP", "192.168.1.19")
NETSENTRY_AP_IP = os.getenv("NETSENTRY_AP_IP", "10.10.10.1")

SSID_NAME = os.getenv("NETSENTRY_SSID", "NetSentry-Test")

PROJECT_OWNER = os.getenv("NETSENTRY_PROJECT_OWNER", "Saif / GarablueX")
GITHUB_URL = os.getenv("NETSENTRY_GITHUB_URL", "https://github.com/GarablueX/netsentry-gateway")
CONTACT_EMAIL = os.getenv("NETSENTRY_CONTACT_EMAIL", "Add contact email in /etc/netsentry/netsentry-web.env")
CONTACT_NOTE = os.getenv("NETSENTRY_CONTACT_NOTE", "For lab/project questions, use the GitHub repository or the configured contact address.")

IDS_ALERTS_JSONL = BASE_DIR / "data/ids/alerts.jsonl"
IDS_ALERTS_LATEST_JSON = BASE_DIR / "data/ids/alerts_latest.json"
IDS_LATEST_REV3_JSON = BASE_DIR / "data/ids/latest_rev3.json"

ALERTS_JSONL = IDS_ALERTS_JSONL
ALERT_FAST = BASE_DIR / "snort/alerts/alert_fast.txt"

HONEYPOT_LOG = BASE_DIR / "logs/honeypot_lite_attempts.jsonl"
HTTP_TEST_LOG = BASE_DIR / "logs/http_test_service_access.jsonl"
PORTAL_AUTH_LOG = BASE_DIR / "logs/portal_auth_attempts.jsonl"
PORTAL_DECOY_LOG = BASE_DIR / "logs/portal_decoy_attempts.jsonl"
APP_LOG = BASE_DIR / "logs/netsentry_app.log"
AGENT_LOG = BASE_DIR / "logs/agent.log"

DNSMASQ_LEASE_FILES = [
    Path("/var/lib/misc/dnsmasq.leases"),
    Path("/var/lib/misc/dnsmasq-netsentry.leases"),
    Path("/run/dnsmasq/dnsmasq.leases"),
    Path("/tmp/dnsmasq.leases"),
]

ADGUARD_URL = os.getenv("NETSENTRY_ADGUARD_URL", "http://127.0.0.1:3001")
ADGUARD_USER = os.getenv("NETSENTRY_ADGUARD_USER", "")
ADGUARD_PASSWORD = os.getenv("NETSENTRY_ADGUARD_PASSWORD", "")

FIREWALL_READ_HELPER = Path("/usr/local/sbin/netsentry-read-firewall")


ADMIN_USER = os.getenv("NETSENTRY_WEB_USER", "admin")
ADMIN_PASSWORD = os.getenv("NETSENTRY_WEB_PASSWORD", "")
ADMIN_PASSWORD_HASH = os.getenv("NETSENTRY_WEB_PASSWORD_HASH", "")
SECRET_KEY = os.getenv("NETSENTRY_WEB_SECRET", "") or secrets.token_hex(32)

SESSION_TIMEOUT_SECONDS = int(os.getenv("NETSENTRY_SESSION_TIMEOUT", "14400"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("NETSENTRY_LOGIN_LOCKOUT", "30"))
LOGIN_MAX_FAILURES = int(os.getenv("NETSENTRY_LOGIN_MAX_FAILURES", "5"))

PUBLIC_ROUTES = [
    ("/", "Home"),
    ("/about", "About"),
    ("/features", "Features"),
    ("/architecture", "Architecture"),
    ("/status", "Status"),
    ("/docs", "Docs"),
    ("/hardware", "Hardware"),
    ("/contact", "Contact"),
]

ADMIN_ROUTES = [
    ("/admin/dashboard", "Dashboard"),
    ("/admin/clients", "Clients"),
    ("/admin/dns", "DNS"),
    ("/admin/firewall", "Firewall"),
    ("/admin/ids", "IDS"),
    ("/admin/logs", "Logs"),
    ("/admin/network", "Network"),
]


# ============================================================
# Flask app object
# ============================================================

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
)

LOGIN_FAILURES = {}


# ============================================================
# Utility helpers
# ============================================================

def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def run_cmd(command, timeout=4):
    """Run a read-only command and return structured output."""
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
            "command": " ".join(command),
        }
    except Exception as error:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(error),
            "command": " ".join(command),
        }


def read_jsonl_tail(path, limit=200):
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


def read_text_tail(path, limit=200):
    if not path.exists():
        return []
    return path.read_text(errors="ignore").splitlines()[-limit:]


def read_jsonl(path, limit=None):
    if not path.exists():
        return []
    lines = path.read_text(errors="ignore").splitlines()
    if limit is not None:
        lines = lines[-limit:]
    items = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except Exception:
            items.append({"raw": line})
    return items


def contains_ci(text, needle):
    return needle.lower() in str(text).lower()


def internet_is_reachable():
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2).close()
        return True
    except OSError:
        return False


def get_uptime():
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


def get_loadavg():
    try:
        one, five, fifteen = os.getloadavg()
        return [round(one, 2), round(five, 2), round(fifteen, 2)]
    except Exception:
        return []


def get_memory_percent():
    try:
        data = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            data[key] = int(value.strip().split()[0])
        total = data.get("MemTotal", 0)
        available = data.get("MemAvailable", 0)
        if not total:
            return None
        used = total - available
        return round((used / total) * 100, 1)
    except Exception:
        return None


def get_disk_percent(path="/"):
    try:
        usage = shutil.disk_usage(path)
        return round((usage.used / usage.total) * 100, 1)
    except Exception:
        return None


def service_active(name):
    result = run_cmd(["systemctl", "is-active", name], timeout=2)
    state = result["stdout"].strip() or result["stderr"].strip() or "unknown"
    return {"name": name, "active": state == "active", "state": state}


def process_running(pattern):
    result = run_cmd(["pgrep", "-af", pattern], timeout=2)
    return {"pattern": pattern, "running": result["ok"] and bool(result["stdout"]), "raw": result["stdout"]}


# ============================================================
# Authentication
# ============================================================

def client_ip():
    return request.headers.get("X-Real-IP") or request.remote_addr or "unknown"


def login_locked(ip):
    failures = LOGIN_FAILURES.get(ip, [])
    failures = [t for t in failures if datetime.now().timestamp() - t < LOGIN_LOCKOUT_SECONDS]
    LOGIN_FAILURES[ip] = failures
    return len(failures) >= LOGIN_MAX_FAILURES


def record_login_failure(ip):
    failures = LOGIN_FAILURES.get(ip, [])
    failures.append(datetime.now().timestamp())
    LOGIN_FAILURES[ip] = failures


def verify_password(password):
    if ADMIN_PASSWORD_HASH:
        try:
            return check_password_hash(ADMIN_PASSWORD_HASH, password)
        except Exception:
            return False
    return hmac.compare_digest(password, ADMIN_PASSWORD)


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def check_csrf():
    posted = request.form.get("csrf_token", "")
    stored = session.get("csrf_token", "")
    return bool(posted and stored and hmac.compare_digest(posted, stored))


def is_logged_in():
    if not session.get("logged_in"):
        return False
    login_time = session.get("login_time", 0)
    age = datetime.now().timestamp() - float(login_time)
    if age > SESSION_TIMEOUT_SECONDS:
        session.clear()
        return False
    return True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {
        "public_routes": PUBLIC_ROUTES,
        "admin_routes": ADMIN_ROUTES,
        "is_logged_in": is_logged_in,
        "current_user": session.get("user", ""),
        "default_password_warning": not ADMIN_PASSWORD_HASH and ADMIN_PASSWORD,
    }


# ============================================================
# Data collection
# ============================================================

def get_public_status_data():
    internet_ok = internet_is_reachable()
    return {
        "gateway": "online",
        "internet": "online" if internet_ok else "offline",
        "internet_ok": internet_ok,
        "uptime": get_uptime(),
        "last_update": now_iso(),
    }


def get_full_status_data():
    public = get_public_status_data()
    public.update(
        {
            "hostname": socket.gethostname(),
            "loadavg": get_loadavg(),
            "memory_percent": get_memory_percent(),
            "disk_percent": get_disk_percent("/"),
            "services": {
                "nginx": service_active("nginx"),
                "AdGuardHome": service_active("AdGuardHome"),
                "netsentry_ap_interface": service_active("netsentry-ap-interface"),
                "netsentry_snort_ap": service_active("netsentry-snort-ap"),
                "netsentry_snort_watcher": service_active("netsentry-snort-watcher"),
                "hostapd_process": process_running("hostapd"),
                "dnsmasq_process": process_running("dnsmasq"),
                "snort_process": process_running("snort"),
                "snort_watcher_process": process_running("snort_alert_watcher.py"),
            },
        }
    )
    return public


def get_interfaces_data():
    json_result = run_cmd(["ip", "-j", "addr"], timeout=3)
    interfaces = []
    if json_result["ok"] and json_result["stdout"]:
        try:
            for item in json.loads(json_result["stdout"]):
                name = item.get("ifname", "")
                role = "other"
                if name == WAN_INTERFACE:
                    role = "WAN/HOME"
                elif name == AP_INTERFACE:
                    role = "AP/CLIENT"
                ipv4 = []
                for addr in item.get("addr_info", []):
                    if addr.get("family") == "inet":
                        ipv4.append(f"{addr.get('local')}/{addr.get('prefixlen')}")
                interfaces.append(
                    {
                        "name": name,
                        "state": item.get("operstate", "unknown"),
                        "role": role,
                        "mac": item.get("address", ""),
                        "ipv4": ipv4,
                    }
                )
        except Exception:
            interfaces = []
    return {"interfaces": interfaces, "raw": run_cmd(["ip", "-br", "addr"], timeout=3)}


def get_routes_data():
    raw = run_cmd(["ip", "route"], timeout=3)
    routes = []
    for line in raw["stdout"].splitlines():
        routes.append({"line": line})
    return {"routes": routes, "raw": raw}


def get_listening_ports_data():
    raw = run_cmd(["ss", "-tulpen"], timeout=4)
    ports = []
    for line in raw["stdout"].splitlines():
        if line.startswith(("Netid", "State")):
            continue
        parts = line.split()
        if len(parts) >= 5:
            ports.append({"raw": line, "proto": parts[0], "local": parts[4]})
    return {"ports": ports, "raw": raw}


def get_clients_data():
    lease_file = None
    for candidate in DNSMASQ_LEASE_FILES:
        if candidate.exists():
            lease_file = candidate
            break
    if lease_file is None:
        return {"lease_file": None, "clients": [], "warning": "No dnsmasq lease file found."}
    clients = []
    for line in lease_file.read_text(errors="ignore").splitlines():
        parts = line.split()
        if len(parts) >= 4:
            expires_raw = parts[0]
            hostname = parts[3]
            try:
                expires = datetime.fromtimestamp(int(expires_raw)).isoformat(timespec="seconds")
            except Exception:
                expires = expires_raw
            clients.append(
                {
                    "expires": expires,
                    "mac": parts[1],
                    "ip": parts[2],
                    "hostname": hostname if hostname != "*" else "unknown",
                    "raw": line,
                }
            )
    q = request.args.get("q", "").strip()
    if q:
        clients = [c for c in clients if any(contains_ci(v, q) for v in c.values())]
    return {"lease_file": str(lease_file), "clients": clients, "warning": None, "query": q}


def adguard_request(path, query=None):
    params = ""
    if query:
        params = "?" + urllib.parse.urlencode(query)
    url = ADGUARD_URL.rstrip("/") + path + params
    req = urllib.request.Request(url)
    if ADGUARD_USER and ADGUARD_PASSWORD:
        token = f"{ADGUARD_USER}:{ADGUARD_PASSWORD}".encode()
        req.add_header("Authorization", "Basic " + base64.b64encode(token).decode())
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            raw = resp.read().decode(errors="ignore")
            try:
                return {"ok": True, "url": url, "data": json.loads(raw), "raw": raw, "error": ""}
            except Exception:
                return {"ok": True, "url": url, "data": None, "raw": raw, "error": ""}
    except urllib.error.HTTPError as error:
        return {"ok": False, "url": url, "data": None, "raw": "", "error": f"HTTP {error.code}: {error.reason}"}
    except Exception as error:
        return {"ok": False, "url": url, "data": None, "raw": "", "error": str(error)}


def count_items_to_rows(value, limit=10):
    """Normalize AdGuard top_* values into [{name,count}] rows.

    AdGuard can return either dict-like counters or list-like values depending on
    version/config. This keeps the dashboard readable instead of dumping raw JSON.
    """
    rows = []
    if isinstance(value, dict):
        for name, count in sorted(value.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True)[:limit]:
            rows.append({"name": str(name), "count": count})
    elif isinstance(value, list):
        for item in value[:limit]:
            if isinstance(item, dict):
                name = item.get("name") or item.get("domain") or item.get("client") or item.get("ip") or json.dumps(item)
                count = item.get("count") or item.get("num") or item.get("queries") or ""
                rows.append({"name": str(name), "count": count})
            else:
                rows.append({"name": str(item), "count": ""})
    return rows


def normalize_dns_query(entry):
    question = entry.get("question") or {}
    domain = question.get("name") or entry.get("domain") or entry.get("host") or ""
    qtype = question.get("type") or entry.get("type") or ""
    client = entry.get("client") or entry.get("client_ip") or entry.get("client_proto") or ""
    reason = entry.get("reason") or entry.get("filterId") or entry.get("status") or "allowed"
    return {
        "time": entry.get("time") or entry.get("elapsedMs") or "",
        "client": client,
        "domain": domain,
        "type": qtype,
        "status": reason,
        "raw": entry,
    }


def get_dns_data():
    stats = adguard_request("/control/stats")
    status = adguard_request("/control/status")
    querylog = adguard_request("/control/querylog", {"limit": 100})
    s = stats.get("data") or {}
    qlog = querylog.get("data") or {}

    queries = s.get("num_dns_queries", 0) or s.get("dns_queries", 0) or 0
    blocked = s.get("num_blocked_filtering", 0) or s.get("blocked_filtering", 0) or 0
    try:
        blocked_percent = round((blocked / queries) * 100, 1) if queries else 0
    except Exception:
        blocked_percent = 0

    recent_raw = qlog.get("data", []) if isinstance(qlog, dict) else []
    recent_queries = [normalize_dns_query(x) for x in recent_raw[:100] if isinstance(x, dict)]

    return {
        "configured_url": ADGUARD_URL,
        "auth_configured": bool(ADGUARD_USER and ADGUARD_PASSWORD),
        "stats_ok": stats["ok"],
        "status_ok": status["ok"],
        "querylog_ok": querylog["ok"],
        "queries": queries,
        "blocked": blocked,
        "blocked_percent": blocked_percent,
        "top_blocked": count_items_to_rows(s.get("top_blocked_domains", []), 10),
        "top_queried": count_items_to_rows(s.get("top_queried_domains", []), 10),
        "top_clients": count_items_to_rows(s.get("top_clients", []), 10),
        "recent_queries": recent_queries,
        "raw": {"stats": stats, "status": status, "querylog": querylog},
    }

def read_firewall_table(name):
    if FIREWALL_READ_HELPER.exists():
        return run_cmd(["sudo", "-n", str(FIREWALL_READ_HELPER), name], timeout=4)
    if name == "input":
        return run_cmd(["sudo", "-n", "iptables", "-L", "INPUT", "-n", "-v", "--line-numbers"], timeout=4)
    if name == "forward":
        return run_cmd(["sudo", "-n", "iptables", "-L", "FORWARD", "-n", "-v", "--line-numbers"], timeout=4)
    if name == "nat":
        return run_cmd(["sudo", "-n", "iptables", "-t", "nat", "-L", "-n", "-v", "--line-numbers"], timeout=4)
    return {"ok": False, "stdout": "", "stderr": "unknown table", "returncode": -1}


def text_has(text, *needles):
    return all(needle in text for needle in needles)


def get_ip_forwarding_data():
    result = run_cmd(["sysctl", "-n", "net.ipv4.ip_forward"], timeout=2)
    enabled = result["stdout"].strip() == "1"
    return {"enabled": enabled, "state": "enabled" if enabled else "disabled", "raw": result}


def get_firewall_data():
    raw = {"input": read_firewall_table("input"), "forward": read_firewall_table("forward"), "nat": read_firewall_table("nat")}
    input_text = raw["input"]["stdout"] or ""
    forward_text = raw["forward"]["stdout"] or ""
    nat_text = raw["nat"]["stdout"] or ""
    ip_forwarding = get_ip_forwarding_data()
    input_final_drop = "DROP       all" in input_text
    nat_masquerade = "MASQUERADE" in nat_text and AP_LAN in nat_text
    nat_lan_exception = "RETURN" in nat_text and AP_LAN in nat_text and HOME_LAN in nat_text
    access_matrix = [
        {"category": "SSH Admin", "source": ADMIN_IP, "ports": "TCP 22", "purpose": "Admin SSH only", "ok": text_has(input_text, ADMIN_IP, "tcp dpt:22")},
        {"category": "DNS AP", "source": AP_LAN, "ports": "UDP/TCP 53", "purpose": "AP client DNS", "ok": text_has(input_text, AP_LAN, "udp dpt:53") and text_has(input_text, AP_LAN, "tcp dpt:53")},
        {"category": "DNS HOME", "source": HOME_LAN, "ports": "UDP/TCP 53", "purpose": "HOME LAN DNS", "ok": text_has(input_text, HOME_LAN, "udp dpt:53") and text_has(input_text, HOME_LAN, "tcp dpt:53")},
        {"category": "DHCP AP", "source": AP_INTERFACE, "ports": "UDP 67", "purpose": "DHCP for AP clients", "ok": text_has(input_text, AP_INTERFACE, "udp spt:68 dpt:67")},
        {"category": "Nginx HTTP", "source": f"{HOME_LAN} + {AP_LAN}", "ports": "TCP 80", "purpose": "Unified web app", "ok": text_has(input_text, HOME_LAN, "tcp dpt:80") and text_has(input_text, AP_LAN, "tcp dpt:80")},
        {"category": "Nginx HTTPS", "source": f"{HOME_LAN} + {AP_LAN}", "ports": "TCP 443", "purpose": "HTTPS frontend", "ok": text_has(input_text, HOME_LAN, "tcp dpt:443") and text_has(input_text, AP_LAN, "tcp dpt:443")},
        {"category": "Legacy Portal", "source": f"{HOME_LAN} + {AP_LAN}", "ports": "TCP 5500", "purpose": "Old portal during migration", "ok": text_has(input_text, HOME_LAN, "tcp dpt:5500") and text_has(input_text, AP_LAN, "tcp dpt:5500")},
        {"category": "Legacy Status API", "source": f"{HOME_LAN} + {AP_LAN}", "ports": "TCP 5051", "purpose": "Old status service during migration", "ok": text_has(input_text, HOME_LAN, "tcp dpt:5051") and text_has(input_text, AP_LAN, "tcp dpt:5051")},
        {"category": "Honeypot", "source": f"{HOME_LAN} + {AP_LAN}", "ports": "TCP 8082", "purpose": "Decoy service", "ok": text_has(input_text, HOME_LAN, "tcp dpt:8082") and text_has(input_text, AP_LAN, "tcp dpt:8082")},
        {"category": "Legacy IDS Dashboard", "source": ADMIN_IP, "ports": "TCP 5050", "purpose": "Old dashboard admin-only", "ok": text_has(input_text, ADMIN_IP, "tcp dpt:5050")},
        {"category": "AdGuard UI", "source": ADMIN_IP, "ports": "TCP 3001", "purpose": "AdGuard admin UI", "ok": text_has(input_text, ADMIN_IP, "tcp dpt:3001")},
        {"category": "HTTP Test", "source": ADMIN_IP, "ports": "TCP 8081", "purpose": "Snort HTTP tests", "ok": text_has(input_text, ADMIN_IP, "tcp dpt:8081")},
        {"category": "FTP", "source": ADMIN_IP, "ports": "TCP 21 + 40000:40100", "purpose": "Admin-only FTP", "ok": text_has(input_text, ADMIN_IP, "tcp dpt:21") and "tcp dpts:40000:40100" in input_text},
    ]
    policy = [
        {"name": "Established traffic", "description": "Replies to established connections are accepted.", "ok": "RELATED,ESTABLISHED" in input_text},
        {"name": "Invalid packets", "description": "Invalid conntrack packets are dropped.", "ok": "ctstate INVALID" in input_text and "DROP" in input_text},
        {"name": "Loopback", "description": "Localhost traffic is accepted.", "ok": "lo" in input_text and "ACCEPT" in input_text},
        {"name": "Final INPUT drop", "description": "Unknown input traffic is denied.", "ok": input_final_drop},
        {"name": "AP forwarding", "description": "AP clients can route through the gateway.", "ok": AP_LAN in forward_text and "ACCEPT" in forward_text},
        {"name": "Return forwarding", "description": "Established return traffic is allowed back to AP clients.", "ok": "RELATED,ESTABLISHED" in forward_text},
    ]
    q = request.args.get("q", "").strip()
    chain_filter = request.args.get("chain", "").strip().lower()
    filtered_raw = {}
    for key, item in raw.items():
        lines = item["stdout"].splitlines() if item["stdout"] else item["stderr"].splitlines()
        if q:
            lines = [line for line in lines if contains_ci(line, q)]
        filtered_raw[key] = "\n".join(lines)
    return {
        "ip_forwarding": ip_forwarding,
        "input_final_drop": input_final_drop,
        "nat": {"masquerade": nat_masquerade, "lan_exception": nat_lan_exception},
        "policy": policy,
        "access_matrix": access_matrix,
        "raw": raw,
        "filtered_raw": filtered_raw,
        "query": q,
        "chain_filter": chain_filter,
    }



def read_json_file(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(errors="ignore"))
    except Exception:
        return default


def alert_rev_info(value):
    try:
        rev = int(value)
    except Exception:
        rev = 0

    if rev >= 3:
        return rev, "high", "rev-high"
    if rev == 2:
        return rev, "medium", "rev-medium"
    if rev == 1:
        return rev, "low", "rev-low"
    return rev, "unknown", "rev-unknown"


def normalize_alert(alert):
    if "raw" in alert and len(alert) == 1:
        return {
            "time": "",
            "snort_time": "",
            "gid": "",
            "sid": "",
            "rev": "",
            "rev_int": 0,
            "severity": "unknown",
            "severity_class": "rev-unknown",
            "message": alert["raw"],
            "src": "",
            "src_port": "",
            "dst": "",
            "dst_port": "",
            "proto": "",
            "priority": "",
            "pcap_file": "",
            "pcap_name": "",
            "raw": alert["raw"],
        }

    rev, severity, severity_class = alert_rev_info(alert.get("rev"))

    pcap_file = alert.get("pcap_file") or alert.get("pcap") or ""
    pcap_name = Path(str(pcap_file)).name if pcap_file else ""

    return {
        "time": alert.get("timestamp") or alert.get("seen_at") or alert.get("received_at") or alert.get("time") or "",
        "snort_time": alert.get("snort_time") or alert.get("raw_time") or "",
        "gid": str(alert.get("gid") or "1"),
        "sid": str(alert.get("sid") or alert.get("gid_sid") or ""),
        "rev": str(rev) if rev else "",
        "rev_int": rev,
        "severity": alert.get("severity") or severity,
        "severity_class": severity_class,
        "message": alert.get("message") or alert.get("msg") or alert.get("alert") or "",
        "src": alert.get("src") or alert.get("src_ip") or alert.get("source") or "",
        "src_port": str(alert.get("src_port") or alert.get("sport") or ""),
        "dst": alert.get("dst") or alert.get("dst_ip") or alert.get("destination") or "",
        "dst_port": str(alert.get("dst_port") or alert.get("dport") or ""),
        "proto": str(alert.get("proto") or alert.get("protocol") or ""),
        "priority": str(alert.get("priority") or alert.get("prio") or ""),
        "pcap_file": str(pcap_file),
        "pcap_name": pcap_name,
        "raw": alert.get("raw") or json.dumps(alert, ensure_ascii=False),
    }



def parse_limit(default=1000, maximum=20000):
    raw = request.args.get("limit", str(default)).strip().lower()
    if raw == "all":
        return None
    try:
        value = int(raw)
    except Exception:
        return default
    return max(1, min(value, maximum))



def get_alerts_data(limit=None):
    if limit is None:
        limit = parse_limit(default=1000)

    latest_data = read_json_file(IDS_ALERTS_LATEST_JSON, default=[])
    use_latest = isinstance(latest_data, list) and latest_data and limit is not None and limit <= 1000

    if use_latest:
        raw_alerts = latest_data[-limit:]
        source = str(IDS_ALERTS_LATEST_JSON)
    else:
        raw_alerts = read_jsonl(IDS_ALERTS_JSONL, limit=limit)
        source = str(IDS_ALERTS_JSONL)

    alerts = [normalize_alert(a) for a in raw_alerts]

    src = request.args.get("src", "").strip()
    dst = request.args.get("dst", "").strip()
    sid = request.args.get("sid", "").strip()
    proto = request.args.get("proto", "").strip()
    rev = request.args.get("rev", "").strip()
    q = request.args.get("q", "").strip()

    filtered = alerts

    if src:
        filtered = [a for a in filtered if contains_ci(a["src"], src)]
    if dst:
        filtered = [a for a in filtered if contains_ci(a["dst"], dst)]
    if sid:
        filtered = [a for a in filtered if contains_ci(a["sid"], sid)]
    if proto:
        filtered = [a for a in filtered if contains_ci(a["proto"], proto)]
    if rev:
        filtered = [a for a in filtered if str(a["rev_int"]) == rev]
    if q:
        filtered = [a for a in filtered if any(contains_ci(v, q) for v in a.values())]

    latest_rev3_raw = read_json_file(IDS_LATEST_REV3_JSON, default={})
    latest_rev3 = normalize_alert(latest_rev3_raw) if isinstance(latest_rev3_raw, dict) and latest_rev3_raw else None

    if latest_rev3 is None:
        for item in reversed(alerts):
            if item.get("rev_int", 0) >= 3:
                latest_rev3 = item
                break

    stats = {
        "by_sid": Counter(a["sid"] or "unknown" for a in alerts).most_common(10),
        "by_source": Counter(a["src"] or "unknown" for a in alerts).most_common(10),
        "by_proto": Counter(a["proto"] or "unknown" for a in alerts).most_common(10),
        "by_rev": Counter(str(a["rev_int"] or "unknown") for a in alerts).most_common(10),
    }

    counts = {
        "rev1": sum(1 for a in alerts if a.get("rev_int") == 1),
        "rev2": sum(1 for a in alerts if a.get("rev_int") == 2),
        "rev3": sum(1 for a in alerts if a.get("rev_int", 0) >= 3),
    }

    return {
        "source": source,
        "jsonl_source": str(IDS_ALERTS_JSONL),
        "latest_source": str(IDS_ALERTS_LATEST_JSON),
        "latest_rev3_source": str(IDS_LATEST_REV3_JSON),
        "fast_source": str(ALERT_FAST),
        "alerts": filtered,
        "latest_rev3": latest_rev3,
        "total": len(alerts),
        "filtered_total": len(filtered),
        "counts": counts,
        "stats": stats,
        "limit": "all" if limit is None else limit,
        "filters": {"src": src, "dst": dst, "sid": sid, "proto": proto, "rev": rev, "q": q},
    }




def backup_and_clear_alerts():
    archive = BASE_DIR / "snort/alerts/archive"
    archive.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backups = []

    files_to_clear = [
        (IDS_ALERTS_JSONL, ""),
        (IDS_ALERTS_LATEST_JSON, "[]"),
        (IDS_LATEST_REV3_JSON, "{}"),
        (ALERT_FAST, ""),
    ]

    for path, empty_value in files_to_clear:
        if path.exists():
            backup = archive / f"{path.name}.{stamp}.bak"
            shutil.copy2(path, backup)
            path.write_text(empty_value)
            backups.append(str(backup))

    return backups



def summarize_log_entry(source, entry):
    if isinstance(entry, dict):
        body = json.dumps(entry, ensure_ascii=False)
        time_value = entry.get("time") or entry.get("timestamp") or entry.get("received_at") or entry.get("created_at") or ""
        src_ip = entry.get("ip") or entry.get("src") or entry.get("src_ip") or entry.get("client_ip") or entry.get("remote_addr") or ""
        username = entry.get("username") or entry.get("user") or entry.get("login") or ""
        password = entry.get("password") or entry.get("pass") or ""
        event = entry.get("event") or entry.get("message") or entry.get("path") or entry.get("method") or source
    else:
        body = str(entry)
        time_value = ""
        src_ip = ""
        username = ""
        password = ""
        event = body[:90]
    return {
        "source": source,
        "time": time_value,
        "src_ip": src_ip,
        "username": username,
        "password": password,
        "event": event,
        "body": body,
    }


def get_logs_data(limit=300):
    sources = {
        "honeypot": read_jsonl_tail(HONEYPOT_LOG, limit=limit),
        "http_test": read_jsonl_tail(HTTP_TEST_LOG, limit=limit),
        "portal_auth": read_jsonl_tail(PORTAL_AUTH_LOG, limit=limit),
        "portal_decoy": read_jsonl_tail(PORTAL_DECOY_LOG, limit=limit),
        "app": read_text_tail(APP_LOG, limit=limit),
        "agent": read_text_tail(AGENT_LOG, limit=limit),
        "snort_fast": read_text_tail(ALERT_FAST, limit=limit),
    }
    source_filter = request.args.get("source", "").strip()
    q = request.args.get("q", "").strip()
    rows = []
    counts = {}
    for source, entries in sources.items():
        counts[source] = len(entries)
        if source_filter and source != source_filter:
            continue
        for entry in entries:
            row = summarize_log_entry(source, entry)
            if q and not contains_ci(" ".join(str(v) for v in row.values()), q):
                continue
            rows.append(row)
    return {"rows": rows[-limit:], "counts": counts, "source_filter": source_filter, "query": q, "available_sources": list(sources.keys())}



def get_hardware_data():
    """Return static known hardware plus dynamic inxi output when available."""
    inxi = run_cmd(["inxi", "-Fxz"], timeout=8)
    return {
        "system": "HP Pro3500 Series desktop",
        "os": "Debian GNU/Linux 13 (trixie) / kernel 6.12.86+deb13-amd64",
        "cpu": "Intel Pentium G2030 dual-core, Ivy Bridge, 3 MB L3 cache",
        "memory": "4 GiB RAM installed / about 3.72 GiB available",
        "disk": "Western Digital WD5000AAKX 500 GB HDD, ext4 root partition",
        "wan_nic": "Realtek RTL8111/8168/8211/8411 PCIe Gigabit Ethernet on enp3s0",
        "ap_adapter": "Realtek RTL8188EUS 802.11n USB Wi-Fi adapter on wlx200db0220b9a",
        "graphics": "Intel HD Graphics 2500, headless server use",
        "dynamic_inxi": inxi,
    }

# ============================================================
# Public routes
# ============================================================

@app.route("/")
def public_home():
    return render_template("public/home.html", title="Home", subtitle="Public project landing page", status=get_public_status_data(), github_url=GITHUB_URL)


@app.route("/about")
def public_about():
    return render_template("public/about.html", title="About", subtitle="What NetSentry is", github_url=GITHUB_URL, project_owner=PROJECT_OWNER)


@app.route("/features")
def public_features():
    return render_template("public/features.html", title="Features", subtitle="Gateway security capabilities")


@app.route("/architecture")
def public_architecture():
    return render_template(
        "public/architecture.html",
        title="Architecture",
        subtitle="Web and network architecture",
        wan_interface=WAN_INTERFACE,
        ap_interface=AP_INTERFACE,
        home_lan=HOME_LAN,
        ap_lan=AP_LAN,
        home_ip=NETSENTRY_HOME_IP,
        ap_ip=NETSENTRY_AP_IP,
        ssid=SSID_NAME,
    )


@app.route("/status")
def public_status():
    return render_template("public/status.html", title="Status", subtitle="Public-safe gateway status", status=get_public_status_data())


@app.route("/docs")
def public_docs():
    docs_dir = BASE_DIR / "docs"
    docs = []
    selected = request.args.get("file", "").strip()
    selected_content = ""
    if docs_dir.exists():
        for doc in sorted(docs_dir.glob("*.md")):
            docs.append({"name": doc.name, "size": doc.stat().st_size})
            if selected and selected == doc.name:
                selected_content = doc.read_text(errors="ignore")[:50000]
    return render_template("public/docs.html", title="Docs", subtitle="Project documentation", docs=docs, selected=selected, selected_content=selected_content, github_url=GITHUB_URL)


@app.route("/hardware")
def public_hardware():
    return render_template(
        "public/hardware.html",
        title="Hardware",
        subtitle="Physical and network setup",
        wan_interface=WAN_INTERFACE,
        ap_interface=AP_INTERFACE,
        home_lan=HOME_LAN,
        ap_lan=AP_LAN,
        home_ip=NETSENTRY_HOME_IP,
        ap_ip=NETSENTRY_AP_IP,
        admin_ip=ADMIN_IP,
        ssid=SSID_NAME,
        hardware=get_hardware_data(),
    )


@app.route("/contact")
def public_contact():
    return render_template(
        "public/contact.html",
        title="Contact",
        subtitle="Project contact and disclosure note",
        github_url=GITHUB_URL,
        contact_email=CONTACT_EMAIL,
        contact_note=CONTACT_NOTE,
        project_owner=PROJECT_OWNER,
    )


# ============================================================
# Auth routes
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    ip = client_ip()
    if request.method == "GET" and is_logged_in():
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        if login_locked(ip):
            error = "Too many failed attempts. Wait and retry."
        elif not check_csrf():
            error = "Invalid CSRF token. Refresh and retry."
        else:
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            valid_username = hmac.compare_digest(username, ADMIN_USER)
            valid_password = verify_password(password)
            session.clear()
            if valid_username and valid_password:
                session["logged_in"] = True
                session["user"] = username
                session["role"] = "admin"
                session["login_time"] = datetime.now().timestamp()
                session["csrf_token"] = secrets.token_urlsafe(32)
                LOGIN_FAILURES.pop(ip, None)
                return redirect(request.args.get("next") or url_for("admin_dashboard"))
            record_login_failure(ip)
            error = "Invalid username or password."
    return render_template("admin/login.html", title="Login", subtitle="Admin authentication", error=error, csrf_token=csrf_token())


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("public_home"))


# ============================================================
# Admin routes
# ============================================================

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    status = get_full_status_data()
    clients = get_clients_data()
    alerts = get_alerts_data(limit=300)
    dns = get_dns_data()
    firewall = get_firewall_data()
    network = get_interfaces_data()
    return render_template("admin/dashboard.html", title="Admin Dashboard", subtitle="Read-only gateway overview", status=status, clients=clients, alerts=alerts, dns=dns, firewall=firewall, network=network, home_lan=HOME_LAN, ap_lan=AP_LAN, wan_interface=WAN_INTERFACE, ap_interface=AP_INTERFACE)


@app.route("/admin/clients")
@login_required
def admin_clients():
    return render_template("admin/clients.html", title="Clients", subtitle="DHCP client visibility", data=get_clients_data())


@app.route("/admin/dns")
@login_required
def admin_dns():
    return render_template("admin/dns.html", title="DNS", subtitle="AdGuard DNS filtering statistics", dns=get_dns_data())


@app.route("/admin/firewall")
@login_required
def admin_firewall():
    return render_template("admin/firewall.html", title="Firewall", subtitle="Human-readable read-only firewall policy", firewall=get_firewall_data())


@app.route("/admin/ids")
@login_required
def admin_ids():
    return render_template("admin/ids.html", title="IDS", subtitle="Snort alert visibility with filters", data=get_alerts_data(limit=None), csrf_token=csrf_token(), clear_message=session.pop("ids_clear_message", ""))




@app.route("/admin/ids/clear", methods=["POST"])
@login_required
def admin_ids_clear():
    if not check_csrf():
        abort(403)
    backups = backup_and_clear_alerts()
    session["ids_clear_message"] = "Alerts cleared. Backups: " + ", ".join(backups) if backups else "No alert files existed to clear."
    return redirect(url_for("admin_ids"))

@app.route("/admin/logs")
@login_required
def admin_logs():
    return render_template("admin/logs.html", title="Logs", subtitle="Gateway log visibility and filtering", data=get_logs_data(limit=300))


@app.route("/admin/network")
@login_required
def admin_network():
    return render_template("admin/network.html", title="Network", subtitle="Interfaces, routes, and listening services", interfaces=get_interfaces_data(), routes=get_routes_data(), ports=get_listening_ports_data(), status=get_full_status_data())


# ============================================================
# API routes
# ============================================================

@app.route("/api/status")
def api_status():
    # Public-safe API. Full data is available from admin pages after login.
    return jsonify(get_public_status_data())


@app.route("/api/clients")
@login_required
def api_clients():
    return jsonify(get_clients_data())


@app.route("/api/dns/stats")
@login_required
def api_dns_stats():
    return jsonify(get_dns_data())


@app.route("/api/network/interfaces")
@login_required
def api_network_interfaces():
    return jsonify(get_interfaces_data())


@app.route("/api/network/routes")
@login_required
def api_network_routes():
    return jsonify(get_routes_data())


@app.route("/api/ids/alerts")
@login_required
def api_ids_alerts():
    return jsonify(get_alerts_data(limit=None))


@app.route("/api/firewall/rules")
@login_required
def api_firewall_rules():
    return jsonify(get_firewall_data())


@app.route("/api/logs")
@login_required
def api_logs():
    return jsonify(get_logs_data(limit=300))


# ============================================================
# Error handlers
# ============================================================

@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", title="Forbidden", subtitle="Access denied", code=403, message="You do not have access to this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", title="Not Found", subtitle="Route not found", code=404, message="The requested NetSentry route does not exist."), 404


@app.errorhandler(500)
def server_error(_error):
    return render_template("error.html", title="Server Error", subtitle="Application error", code=500, message="The NetSentry web app hit an internal error. Check the Flask terminal or journal logs."), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
