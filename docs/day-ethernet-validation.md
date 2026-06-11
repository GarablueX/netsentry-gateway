# NetSentry V0 — Ethernet Migration and Service Validation

## Goal

Move NetSentry from Wi-Fi testing to Ethernet-based testing and validate the current protected services using a non-admin VM.

The goal was not to take over the full home network yet. This phase only validates that NetSentry works correctly on the Ethernet interface as a host-facing IDS/security lab.

## Network State

| Role | IP Address |
|---|---|
| Admin laptop | `192.168.1.11` |
| Non-admin VM | `192.168.1.18` |
| NetSentry Ethernet | `192.168.1.19` |

## Interface Migration

Before Ethernet migration, NetSentry was mainly tested through the Wi-Fi adapter.

Previous state:

```text
Wi-Fi interface: wlx200db0220b9a
Wi-Fi IP: 192.168.1.17
```

After connecting Ethernet:

```text
Ethernet interface: enp3s0
Ethernet IP: 192.168.1.19
```

Snort was moved to the Ethernet interface:

```bash
-i enp3s0
```

## Routing Observation

After Ethernet was connected, Debian had both Wi-Fi and Ethernet interfaces active.

Observed state:

```text
enp3s0          Ethernet   192.168.1.19
wlx200db0220b9a Wi-Fi      192.168.1.17
```

Ethernet was selected for local LAN traffic because it had the lower route metric.

Wi-Fi was kept temporarily as a safety fallback during migration.

## Services Tested

| Service | Port | Policy |
|---|---:|---|
| SSH / SFTP | `22` | Admin only |
| AdGuard UI | `3001` | Admin only |
| IDS Dashboard | `5050` | Admin only |
| Status API | `5051` | Admin only |
| HTTP Test Service | `8081` | Admin only |
| Honeypot-lite | `8082` | LAN reachable and monitored |

## Service Roles

### SSH / SFTP

Used for administration and secure file transfer.

Expected behavior:

```text
Admin laptop can connect.
Non-admin clients are blocked and detected.
```

### AdGuard UI

AdGuard management interface.

Expected behavior:

```text
Admin laptop can access.
Non-admin clients are blocked and detected.
```

### IDS Dashboard

Main NetSentry alert dashboard.

Expected behavior:

```text
Admin laptop can access.
Non-admin clients are blocked and detected.
```

### Status API

Separate health/status service on port `5051`.

Expected behavior:

```text
Admin laptop can access.
Non-admin clients are blocked and detected.
```

### HTTP Test Service

Controlled HTTP service on port `8081`.

Purpose:

```text
Test HTTP service protection and suspicious URI detection.
```

Suspicious paths:

```text
/admin
/login
/.env
/wp-login.php
/phpmyadmin
```

Expected behavior:

```text
Admin/test-allowed clients can trigger URI rules.
Non-admin clients are blocked and trigger access-attempt detection.
```

### Honeypot-lite

Fake admin login service on port `8082`.

Purpose:

```text
Allow interaction from LAN clients.
Log suspicious login attempts.
Detect non-admin access with Snort.
Display attempts in the IDS dashboard.
```

Expected behavior:

```text
LAN clients can reach the honeypot.
Honeypot logs GET and POST attempts.
Snort detects non-admin access.
Dashboard displays both IDS alerts and honeypot attempts.
```

## Snort Ethernet Run Command

Snort was run on the Ethernet interface:

```bash
cd ~/netsentry-gateway

sudo stdbuf -oL -eL snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i enp3s0 \
-A alert_fast | stdbuf -oL tee -a ~/netsentry-gateway/snort/alerts/alert_fast.txt
```

The `stdbuf` command is required to avoid partial-line buffering issues when the Python watcher reads `alert_fast.txt`.

## Python Services

The Python services were started together using:

```text
scripts/start_python_services.py
```

Services started:

```text
http_test_service.py
honeypot_lite.py
netsentry_dashboard.py
netsentry_status_api.py
snort_alert_watcher.py
```

The backup file below is not a service and should not be run:

```text
netsentry_dashboard.py.bak
```

Stopping all Python services is handled by:

```text
scripts/stop_python_services.py
```

## VM Test Source

Tests were run from the non-admin VM:

```text
192.168.1.18
```

Target:

```text
192.168.1.19
```

## VM Test Suite

A VM-side test script was used to validate firewall and Snort behavior.

The test generated:

```text
ICMP ping
TCP connection attempts to protected services
Honeypot GET request
Honeypot fake login POST attempts
Repeated SSH connection attempts
HTTP test service requests
```

## Confirmed IDS Detections

The following detections were confirmed:

| Detection | Status |
|---|---|
| ICMP ping from VM | Worked |
| SSH SYN probe from VM | Worked |
| Repeated SSH / brute-force threshold | Worked |
| AdGuard UI access attempt | Worked |
| IDS Dashboard access attempt | Worked |
| HTTP Test Service access attempt | Worked |
| Honeypot-lite access attempt | Worked |
| Honeypot fake credential logging | Worked |

## Honeypot Validation

The honeypot logged fake credential attempts from the VM.

Example usernames tested:

```text
admin
root
john
```

Example passwords tested:

```text
admin
toor
password123
```

The honeypot attempts appeared in the dashboard Honeypot Attempts panel.

## Important Firewall and Snort Finding

For services blocked by iptables, Snort can detect the TCP access attempt, but may not see HTTP URI payloads if the TCP connection never completes.

Example:

```text
Non-admin VM -> 8081
iptables blocks the connection
Snort detects the SYN/access attempt
HTTP URI rules may not trigger because no HTTP GET reaches the service
```

For allowed HTTP traffic, URI rules can detect suspicious paths.

Example allowed URI detections:

```text
/admin
/login
/.env
/wp-login.php
/phpmyadmin
```

This behavior is correct.

## Dashboard Validation

The dashboard successfully displayed:

```text
total IDS alert count
matching filter count
honeypot attempt count
latest source IP
latest destination port
latest SID
alert summary by SID
honeypot attempts table
IDS alert table
source IP and port
destination IP and port
raw Snort alert
```

The dashboard correctly showed alerts from:

```text
192.168.1.18 -> 192.168.1.19
```

## Current Working Service Map

| Port | Service | Current Policy |
|---:|---|---|
| `22` | SSH / SFTP | Admin only |
| `53` | AdGuard DNS | LAN allowed |
| `3001` | AdGuard UI | Admin only |
| `5050` | IDS Dashboard | Admin only |
| `5051` | Status API | Admin only |
| `8081` | HTTP Test Service | Admin only |
| `8082` | Honeypot-lite | LAN reachable and monitored |

## Current Status

NetSentry V0 now works on Ethernet:

```text
192.168.1.19
```

Snort works on:

```text
enp3s0
```

The VM test suite successfully validated:

```text
firewall behavior
Snort detection
Python alert parsing
dashboard display
honeypot logging
Ethernet migration
```

## 19. GitHub Commit Attribution Fix

A GitHub contribution-counting issue was investigated.

The repository was updating correctly after pushes from Debian, but the commits were not appearing correctly on the GitHub contribution dashboard.

The cause was a Git email mismatch.




This is still a host-facing lab.

NetSentry is not yet acting as a full gateway.

No NAT, DHCP, or home network takeover was performed in this phase.
