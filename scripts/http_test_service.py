#!/usr/bin/env python3

from flask import Flask, request, render_template_string, jsonify
from datetime import datetime
from pathlib import Path
import json

BASE_DIR = Path.home() / "netsentry-gateway"
LOG_FILE = BASE_DIR / "logs" / "http_test_service_access.jsonl"

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>NetSentry HTTP Test Service</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #101014;
            color: #eeeeee;
            padding: 30px;
        }
        .card {
            background: #1b1b23;
            border: 1px solid #333342;
            border-radius: 8px;
            padding: 20px;
            max-width: 750px;
        }
        code {
            color: #ffcc66;
        }
        a {
            color: #8dd7ff;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>NetSentry HTTP Test Service</h1>
        <p>This is a controlled local HTTP service for testing Snort HTTP detection.</p>

        <h3>Useful test paths</h3>
        <ul>
            <li><code>/</code> normal page</li>
            <li><code>/admin</code> suspicious admin path</li>
            <li><code>/login</code> suspicious login path</li>
            <li><code>/.env</code> sensitive file probe</li>
            <li><code>/wp-login.php</code> WordPress login probe</li>
            <li><code>/phpmyadmin</code> phpMyAdmin probe</li>
            <li><code>/api/access-log</code> JSON access log</li>
        </ul>
    </div>
</body>
</html>
"""


def log_request(path: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "remote_addr": request.remote_addr,
        "method": request.method,
        "path": path,
        "user_agent": request.headers.get("User-Agent", ""),
    }

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@app.before_request
def before_request():
    log_request(request.path)


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/admin")
def admin():
    return "NetSentry test admin path reached. This is not a real admin panel.\n", 200


@app.route("/login")
def login():
    return "NetSentry test login path reached. No authentication exists here.\n", 200


@app.route("/.env")
def env_probe():
    return "Fake .env probe response. No secrets here.\n", 200


@app.route("/wp-login.php")
def wp_login():
    return "Fake WordPress login probe response. WordPress is not installed.\n", 200


@app.route("/phpmyadmin")
def phpmyadmin():
    return "Fake phpMyAdmin probe response. phpMyAdmin is not installed.\n", 200


@app.route("/api/access-log")
def access_log():
    if not LOG_FILE.exists():
        return jsonify([])

    entries = []
    with LOG_FILE.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return jsonify(entries[-100:])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
