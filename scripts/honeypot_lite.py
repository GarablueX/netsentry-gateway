
#!/usr/bin/env python3

from flask import Flask, request, render_template_string, jsonify
from datetime import datetime
from pathlib import Path
import json

BASE_DIR = Path.home() / "netsentry-gateway"
LOG_FILE = BASE_DIR / "logs" / "honeypot_lite_attempts.jsonl"

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>NetSentry Admin Login</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #101014;
            color: #eeeeee;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
        }

        .login-box {
            background: #1b1b23;
            border: 1px solid #333342;
            border-radius: 10px;
            padding: 28px;
            width: 360px;
            box-shadow: 0 0 30px rgba(0,0,0,0.4);
        }

        h1 {
            margin-top: 0;
            font-size: 24px;
        }

        .subtitle {
            color: #aaaaaa;
            font-size: 13px;
            margin-bottom: 20px;
        }

        label {
            display: block;
            margin-bottom: 6px;
            color: #cccccc;
            font-size: 13px;
        }

        input {
            width: 100%;
            box-sizing: border-box;
            padding: 10px;
            margin-bottom: 14px;
            border-radius: 5px;
            border: 1px solid #444455;
            background: #111118;
            color: #eeeeee;
        }

        button {
            width: 100%;
            padding: 10px;
            background: #303044;
            color: #eeeeee;
            border: 1px solid #555566;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
        }

        button:hover {
            background: #3d3d55;
        }

        .warning {
            color: #ffcc66;
            font-size: 12px;
            margin-top: 15px;
        }

        .error {
            background: #3a1717;
            border: 1px solid #7a2c2c;
            color: #ffaaaa;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>NetSentry Admin</h1>
        <div class="subtitle">Management console</div>

        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}

        <form method="post" action="/login">
            <label>Username</label>
            <input name="username" autocomplete="off">

            <label>Password</label>
            <input name="password" type="password" autocomplete="off">

            <button type="submit">Sign in</button>
        </form>

        <div class="warning">
            Authorized access only.
        </div>
    </div>
</body>
</html>
"""


def log_attempt(username: str = "", password: str = "") -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "remote_addr": request.remote_addr,
        "method": request.method,
        "path": request.path,
        "username": username,
        "password": password,
        "user_agent": request.headers.get("User-Agent", ""),
    }

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@app.route("/", methods=["GET"])
def index():
    log_attempt()
    return render_template_string(HTML_TEMPLATE, error="")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")

    log_attempt(username=username, password=password)

    return render_template_string(
        HTML_TEMPLATE,
        error="Invalid username or password."
    ), 401


@app.route("/api/attempts")
def attempts():
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
    app.run(host="0.0.0.0", port=8082)
