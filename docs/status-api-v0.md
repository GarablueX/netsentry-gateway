# NetSentry Status API V0

## Goal

Create a separate local health and status service for NetSentry.

The IDS alert dashboard runs on port `5050`.

The status API runs separately on port `5051`.

This keeps alert monitoring and system health monitoring separated.

## Service File

```text
scripts/netsentry_status_api.py
```

## Web URL

```text
http://192.168.1.17:5051
```

## API URL

```text
http://192.168.1.17:5051/api/status
```

## Purpose

The status API shows useful admin information:

- hostname
- uptime
- load average
- memory usage
- disk usage
- IPv4 addresses per interface
- Snort process status
- watcher process status
- dashboard process status
- status API process status
- AdGuard process status
- alert file sizes
- total structured alert count

## Port Separation

| Service | Port | Purpose |
|---|---:|---|
| IDS Dashboard | `5050` | Shows Snort alerts |
| Status API | `5051` | Shows NetSentry system health |

## Run Command

```bash
cd ~/netsentry-gateway
python3 scripts/netsentry_status_api.py
```

## Running Dashboard and Status API Together

Both Flask apps can run in the same SSH session if they are launched as background processes.

```bash
cd ~/netsentry-gateway
mkdir -p logs

python3 scripts/netsentry_dashboard.py > logs/dashboard_runtime.log 2>&1 &
python3 scripts/netsentry_status_api.py > logs/status_api_runtime.log 2>&1 &
```

Check listening ports:

```bash
ss -tulpn | grep -E '5050|5051'
```

Stop both services:

```bash
pkill -f netsentry_dashboard.py
pkill -f netsentry_status_api.py
```

## Firewall Protection

The status API should only be accessible from the admin laptop.

Policy:

```text
Allow 192.168.1.11 to access port 5051.
Block everyone else from port 5051.
```

iptables rules used:

```bash
sudo iptables -I INPUT 9 -p tcp -s 192.168.1.11 --dport 5051 -j ACCEPT
sudo iptables -I INPUT 10 -p tcp --dport 5051 -j DROP
```

## Snort Detection

Snort detects non-admin access attempts to the status API.

Rule:

```snort
alert tcp !192.168.1.11 any -> 192.168.1.17 5051 (
msg:"NETSENTRY Status API access attempt from non-admin detected";
flags:S;
sid:10000008;
rev:1;
)
```

## Test Procedure

### Admin laptop test

From the admin laptop, open:

```text
http://192.168.1.17:5051
```

Expected result:

```text
The status API page loads successfully.
```

### Non-admin test

From a non-admin device, run:

```bash
curl http://192.168.1.17:5051
```

Expected result:

```text
iptables blocks the request.
Snort detects the attempt.
Python watcher parses the alert.
IDS dashboard shows the alert.
```

## Current Status

Status API V0 works.

Confirmed:

- Status API runs on port `5051`.
- IDS dashboard remains on port `5050`.
- Admin laptop can access the status API.
- Non-admin clients are blocked by iptables.
- Snort detects non-admin access attempts to port `5051`.
- Dashboard can show the status API access alert.
- Dashboard and status API can run at the same time using background processes.

## Notes

The status API is still a V0 admin tool.

It is not public.

It should remain restricted to the admin laptop or a private VPN in future versions.
