# NetSentry Gateway — Master Documentation

**Version:** v2.6.0 — Stable
**Status:** Active homelab deployment
**Type:** Personal / student cybersecurity project

This is the authoritative technical reference for NetSentry. If the
top-level `README.md`, older files in `docs/`, or code comments ever
disagree with this document, **this document is correct** — update the
others to match rather than the other way around.

---

## Table of Contents

1. [Project Summary](#1-project-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Network Layout](#3-network-layout)
4. [Component Reference](#4-component-reference)
5. [Firewall / NAT](#5-firewall--nat)
6. [IDS: Suricata](#6-ids-suricata)
7. [SIEM: Wazuh](#7-siem-wazuh)
8. [Web Dashboard](#8-web-dashboard)
9. [Systemd Services](#9-systemd-services)
10. [Remote Administration: Tailscale](#10-remote-administration-tailscale)
11. [Secrets and Security Policy](#11-secrets-and-security-policy)
12. [Repository Structure](#12-repository-structure)
13. [Version History](#13-version-history)
14. [Testing and Validation](#14-testing-and-validation)
15. [Known Issues](#15-known-issues)
16. [Unfinished / Planned Work](#16-unfinished--planned-work)

---

## 1. Project Summary

NetSentry converts a Debian machine into a small security gateway appliance
sitting between a home ISP network and a set of Wi-Fi clients. It combines:

- Routing, DHCP, and DNS filtering for a separate AP client subnet
- Stateful firewall/NAT enforcement (iptables)
- Network-level intrusion detection (Suricata)
- Security event correlation and investigation (Wazuh SIEM)
- A read-only operational status dashboard (Flask + Nginx)
- Private remote administration (Tailscale)

It is explicitly **not** an enterprise product. It exists to demonstrate
real, working blue-team infrastructure skills in a lab that runs
continuously, not a one-off exercise that gets torn down.

---

## 2. Architecture Overview

```text
AP Client
   |
   | Wi-Fi / 10.10.10.0/24
   v
NetSentry AP Interface (wlx200db0220b9a / 10.10.10.1)
   |
   |-- Suricata IDS reads this interface (pre-NAT, real client IPs)
   |
   | iptables firewall / NAT / routing
   v
NetSentry HOME/WAN Interface (enp3s0 / 192.168.1.19)
   |
   v
Home Router / Internet
```

Dashboard architecture:

```text
Browser -> Nginx :80/:443 -> Flask 127.0.0.1:5000   (gateway operations)
Browser -> Nginx :8443     -> Wazuh dashboard        (SIEM / investigation)
```

IDS/SIEM data pipeline:

```text
Suricata on wlx200db0220b9a
   |
   v
/var/log/suricata/eve.json
   |
   v
Filebeat
   |
   v
Wazuh manager -> Wazuh indexer -> Wazuh dashboard (https://192.168.1.19:8443/)
```

Firewall log correlation pipeline:

```text
iptables LOG rules (rate-limited)
   |
   v
journald / kernel log
   |
   v
Wazuh (via ossec/journald monitoring) -> alerts.json
```

Design principle governing all of the above: **NetSentry handles gateway
operations. Wazuh handles security investigation.** The two are not meant to
duplicate each other's job — this is why the old built-in IDS dashboard was
removed in v2.2 (see [Version History](#13-version-history)).

---

## 3. Network Layout

### HOME / Upstream Side

| Field           | Value             |
| ---------------- | ----------------- |
| Interface         | `enp3s0`           |
| Network            | `192.168.1.0/24`   |
| NetSentry IP        | `192.168.1.19`     |
| Admin laptop IP     | `192.168.1.11`     |

### AP / Client Side

| Field           | Value             |
| ---------------- | ------------------ |
| Interface          | `wlx200db0220b9a`  |
| Network              | `10.10.10.0/24`   |
| Gateway IP           | `10.10.10.1`       |
| SSID                 | `NetSentry-Test`   |
| DHCP range            | `10.10.10.50 - 10.10.10.150` |

### Return Path

The ISP/HOME router has a static route sending `10.10.10.0/24` traffic back
through NetSentry (`192.168.1.19`), so devices on the HOME LAN can reach AP
clients directly and NetSentry does not need to NAT AP↔HOME traffic.

---

## 4. Component Reference

| Component    | Role                                                    |
| ------------ | -------------------------------------------------------- |
| Debian       | Base OS                                                    |
| hostapd      | Wi-Fi AP service on the AP interface                       |
| dnsmasq      | DHCP server for AP clients                                 |
| AdGuard Home | DNS filtering/resolution, exposed on `127.0.0.1:3001`      |
| iptables     | Firewall, NAT, forwarding policy                            |
| Nginx        | TLS termination + reverse proxy for Flask and Wazuh          |
| Flask        | Gateway operations dashboard backend (`app/netsentry_app.py`) |
| Suricata     | Network IDS, running on the AP interface                     |
| Wazuh        | SIEM: manager, indexer, dashboard, investigation UI          |
| Filebeat     | Ships Suricata `eve.json` and other logs into Wazuh           |
| Tailscale    | Private WireGuard-based remote admin overlay network          |
| systemd      | Boot-time service ordering and supervision                    |

---

## 5. Firewall / NAT

**Active script:** `scripts/apply_firewall.sh`
**Active service:** `netsentry-firewall.service` (oneshot, runs at boot
before `hostapd`, `dnsmasq`, and `nginx`)

### Design pattern

1. Set default policies to `ACCEPT` temporarily (so flushing doesn't lock
   out the current session).
2. Flush all chains in `filter`, `nat`, `mangle`, `raw` tables and delete
   user-defined chains.
3. Rebuild the ruleset explicitly, most specific rules first.
4. Add a rate-limited `LOG` rule immediately before the final `DROP`, so
   dropped packets are visible to Wazuh without flooding logs.
5. Set default policies to `DROP` (INPUT/FORWARD) as a second line of
   defense behind the explicit terminal DROP rules.

### NAT behavior

```bash
# AP -> HOME LAN: no NAT, real client IP stays visible
iptables -t nat -A POSTROUTING -s "$AP_NET" -d "$HOME_LAN" -j RETURN

# AP -> Internet: NAT through the WAN interface
iptables -t nat -A POSTROUTING -s "$AP_NET" -o "$WAN_I" -j MASQUERADE
```

This is deliberate: Suricata runs on the AP interface specifically so it
sees pre-NAT client IPs, and not masquerading AP→HOME traffic keeps that
visibility intact for traffic destined to the home network too.

### Access rules summary

| Source              | Destination port(s)      | Notes                                   |
| -------------------- | -------------------------- | ------------------------------------------ |
| `$ADMIN_IP`             | 22 (SSH), 3001 (AdGuard), 8443 (Wazuh), 21 + 40000–40100 (FTP) | Admin-only management access |
| `$AP_NET`, `$HOME_LAN`     | 53 (DNS, tcp+udp)             | DNS filtering for both subnets |
| `$AP_NET`, `$HOME_LAN`     | 80, 443                       | Dashboard access                 |
| `wlx200db0220b9a` (DHCP)    | udp 68→67                    | DHCP for AP clients               |
| `tailscale0` (100.64.0.0/10) | 22, 80, 443, 8443            | Remote admin over Tailscale       |
| any                        | (everything else)             | Dropped, rate-limited log, then default DROP |

**Note on FTP (port 21):** This is not a real FTP service exposed to
clients — it is restricted to `$ADMIN_IP` only and exists to give
`suricata/rules/local.rules` (SIDs `100000116`/`100000117`, anonymous-login
and generic FTP detection) something to validate against during manual
testing. It is a controlled detection-testing surface, not production FTP
access.

### Client-side forwarding rules

```bash
# HOME LAN <-> AP LAN, both directions, unrestricted (trusted relationship)
iptables -A FORWARD -i "$WAN_I" -o "$AP_I" -s "$HOME_LAN" -d "$AP_NET" -j ACCEPT
iptables -A FORWARD -i "$AP_I" -o "$WAN_I" -s "$AP_NET" -d "$HOME_LAN" -j ACCEPT

# AP -> Internet, and its established return traffic
iptables -A FORWARD -i "$AP_I" -o "$WAN_I" -s "$AP_NET" -j ACCEPT
iptables -A FORWARD -i "$WAN_I" -o "$AP_I" -d "$AP_NET" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
```

---

## 6. IDS: Suricata

**Active rules file:** `suricata/rules/local.rules`
**Active config:** `/etc/suricata/suricata.yaml` (repo copy: `config/suricata/suricata.yaml`)
**Capture interface:** `wlx200db0220b9a` (AP side, pre-NAT)

### Variables used in rules

```text
$AP_LAN              10.10.10.0/24
$HOME_LAN             192.168.1.0/24
$ADMIN_IP             192.168.1.11
$AP_GATEWAY           10.10.10.1
$HOME_GATEWAY         192.168.1.19
$NETSENTRY_GATEWAY    [10.10.10.1,192.168.1.19]
```

### Current rule categories

```text
ICMP echo from non-admin / oversized ICMP / ICMP sweep
SSH brute-force threshold / SSH protocol v1 detection
AdGuard UI access attempts from non-admin
Legacy service/API port probing (historical ports 5050/5051)
Non-admin requests containing /admin in the URI
TCP SYN burst / SYN flood
TCP NULL / FIN / XMAS / SYN-FIN scans
UDP flood / TCP RST flood
DNS bypass from AP clients (queries not going to NetSentry's resolver)
FTP anonymous login attempt (detection-testing surface, see Section 5)
AP client horizontal scanning (client-to-client)
SMB / RDP / Telnet access attempts
ICMP to admin host
Wazuh indexer access attempt from non-admin
```

### Rule quality notes

- Rules use `detection_filter` thresholds (count/seconds) rather than
  firing on every single packet, which keeps noisy behaviors like SYN
  bursts and ICMP sweeps from spamming one alert per packet.
- Several rules are commented out with `##` rather than deleted — these are
  earlier iterations kept for reference, not active rules.
- Legacy port rules (5050/5051) reference dashboard ports from earlier
  project stages (`netsentry_dashboard.py`, `netsentry_status_api.py`) and
  remain as detection coverage in case those old services are ever
  reactivated for testing.

### Rule validation

```bash
sudo suricata -T \
  -c /etc/suricata/suricata.yaml \
  -S /etc/suricata/rules/local.rules \
  -i wlx200db0220b9a \
  -l /tmp/suricata-rule-test
```

### Why Suricata replaced Snort

Snort was the original IDS engine (through v1.8). Running Snort and
Suricata side by side (v1.9–v2.1 transition period) produced duplicate
alerts for the same events and made investigation noisier, not clearer.
Snort was removed from the active stack in **v2.2**. All Snort rules,
configs, and the original alert-watcher/dashboard code remain in git
history and in the historical `docs/*.md` files for reference — they are
not deleted, just retired.

---

## 7. SIEM: Wazuh

Wazuh is the investigation layer. It ingests:

- Suricata `eve.json` alerts
- iptables firewall drop logs (`NETSENTRY_FW_INPUT_DROP`, `NETSENTRY_FW_FORWARD_DROP`)
- Nginx access/error logs
- Authentication logs
- System/journald/kernel events

**Wazuh dashboard:** `https://192.168.1.19:8443/`

Repository reference configs (not the live configs — copies for
documentation/version tracking):

```text
config/wazuh/ossec.conf.netsentry-reference
config/wazuh/local_rules.xml.netsentry-reference
config/wazuh/local_suricata_sids.xml
config/wazuh/jvm.options.netsentry-reference
```

### Performance tuning applied (v2.3)

Homelab hardware is resource-constrained, so:

| Setting                       | Action           |
| ------------------------------- | ------------------ |
| Wazuh indexer JVM heap             | Reduced to 512m    |
| Vulnerability detection module      | Disabled            |
| Syscheck scan-on-start               | Disabled            |
| Syscheck frequency                    | Reduced             |
| Swap                                    | Configured as a safety buffer only, not treated as usable RAM |
| Docker / containerd                      | Disabled when unused |

### Suricata rule tuning for Wazuh (v2.6)

Rules were tuned so each real-world behavior produces **one** meaningful
alert instead of several near-duplicates — e.g. one AdGuard-access alert
per attempt instead of one per packet, one SYN-burst alert per burst rather
than per SYN packet. This directly improves signal quality in Wazuh's
alert list.

---

## 8. Web Dashboard

**Backend:** `app/netsentry_app.py` (Flask, ~1100 lines)
**Frontend:** `app/templates/`, `app/static/`
**Reverse proxy:** Nginx (`config/nginx/netsentry.conf`)

### Design principle

The dashboard is explicitly **read-only**. It reports gateway state but
never modifies firewall rules, restarts services, or triggers packet
captures. Any privileged action (the planned Actions dashboard, see Section
16) is scoped as a deliberately separate, more carefully built component —
not bolted onto the existing read path.

### Routes

Public:

```text
/            /about        /features     /architecture
/status      /docs         /hardware      /contact
```

Admin (session-authenticated, login at `/admin/login`):

```text
/admin/dashboard   /admin/clients   /admin/dns
/admin/firewall    /admin/network
```

API (used by the dashboard's own JS, not documented as a public API):

```text
/api/status              /api/clients            /api/dns/stats
/api/network/interfaces  /api/network/routes      /api/firewall/rules
```

**Removed in v2.2** (moved to Wazuh): `/admin/ids`, `/admin/logs`,
`/api/ids/alerts`, `/api/logs`.

### Authentication

- Password is checked either against a hash (`NETSENTRY_WEB_PASSWORD_HASH`,
  via `werkzeug.security.check_password_hash`) or, if no hash is set,
  against a plaintext env value using `hmac.compare_digest` (constant-time
  comparison, not `==`).
- CSRF tokens are generated with `secrets.token_urlsafe(32)` and compared
  with `hmac.compare_digest`.
- Session cookies are `HttpOnly` and `SameSite=Strict`.
- Login lockout: configurable max failures and lockout window
  (`NETSENTRY_LOGIN_MAX_FAILURES`, `NETSENTRY_LOGIN_LOCKOUT`), default 5
  failures / 30 second lockout.
- Session timeout: `NETSENTRY_SESSION_TIMEOUT`, default 14400s (4 hours).

### Configuration

All operational values are read from environment variables with sane
defaults, loaded via `EnvironmentFile=/etc/netsentry/netsentry-web.env` in
the systemd unit — nothing sensitive is hardcoded in `netsentry_app.py`.

---

## 9. Systemd Services

### Active in v2.6

```text
ssh.service
nginx.service
netsentry-web.service
netsentry-ap-interface.service
netsentry-firewall.service
netsentry-dnsmasq.service
hostapd.service
AdGuardHome.service
tailscaled.service
suricata.service
wazuh-indexer.service
wazuh-manager.service
wazuh-dashboard.service
filebeat.service
```

### Explicitly disabled

```text
docker.service
docker.socket
containerd.service
```

(Disabled because they're unused and consume resources on constrained
hardware — see Section 7 performance tuning.)

### Retired (historical, do not re-enable without review)

```text
netsentry-snort-ap.service
netsentry-snort-watcher.service
```

### Boot ordering

`netsentry-ap-interface` → `netsentry-firewall` → `hostapd` / `dnsmasq` /
`nginx`. The firewall must apply before the AP and web-facing services come
up, so nothing is briefly exposed with a default-open ruleset.

### Full health check

```bash
for s in ssh nginx netsentry-web netsentry-ap-interface hostapd \
         AdGuardHome tailscaled netsentry-firewall netsentry-dnsmasq \
         suricata wazuh-indexer wazuh-manager wazuh-dashboard filebeat; do
  printf "%-32s enabled=%-12s active=%s\n" \
  "$s" \
  "$(systemctl is-enabled "$s" 2>/dev/null || echo not-found)" \
  "$(systemctl is-active "$s" 2>/dev/null || echo not-found)"
done
```

---

## 10. Remote Administration: Tailscale

```text
Interface:  tailscale0
Purpose:    Remote SSH + remote HTTPS dashboard access, without exposing
            NetSentry directly to the public Internet.
```

Explicitly **not** used as: an exit node, a subnet router, or a public VPN
gateway. Firewall rules only permit the Tailscale interface to reach SSH,
HTTP, HTTPS, and the Wazuh dashboard port on the NetSentry host itself —
nothing else, and no forwarding beyond the host.

---

## 11. Secrets and Security Policy

### Never commit

```text
Wi-Fi passphrases              AdGuard passwords
Web dashboard passwords         NETSENTRY_WEB_SECRET
Private TLS keys                .env files
Runtime alert/log files          Runtime JSON alert files
PCAP files                       Real credentials
```

### Secrets live outside git, at

```text
/etc/netsentry/netsentry-web.env
/etc/netsentry/certs/
```

### Pre-commit check

```bash
git diff --cached | grep -Ei 'wpa_passphrase=|NETSENTRY_WEB_PASSWORD=|NETSENTRY_WEB_SECRET=|-----BEGIN .*PRIVATE KEY-----|PUT_YOUR_REAL_PASSWORD|PUT_A_LONG_RANDOM_SECRET' \
&& echo "STOP: real secret pattern found" \
|| echo "OK: no real secret patterns found"
```

### .gitignore categories

```text
snort/alerts/*      snort/pcaps/*
data/ids/*.json      data/ids/*.jsonl
data/ids/rev3_flags/* *.pcap
*.bak*                *.key
*.crt
```

### Known placeholder secrets (not real, but should be cleaned up)

`scripts/netsentry_portal.py` (historical, superseded by `app/netsentry_app.py`)
contains hardcoded placeholder values:

```python
ADMIN_PASSWORD = "PASSWORDHERE"
PORTAL_SECRET = "change_this_secret_later_please"
```

These were never real credentials, but they read as real ones out of
context. Recommended fix: replace with `os.getenv(...)` calls matching the
pattern already used in `netsentry_app.py`, or delete the file if it's
fully superseded.

---

## 12. Repository Structure

```text
app/
  netsentry_app.py              Active Flask dashboard backend
  static/                       CSS/JS for the dashboard
  templates/                    Public + admin page templates

config/
  nginx/netsentry.conf           Active Nginx site config
  suricata/suricata.yaml         Repository copy of active Suricata config
  wazuh/                          Reference copies of Wazuh configs
  systemd/                        Repository copies of active systemd units
  ap/                              dnsmasq/hostapd config examples

docs/
  NETSENTRY_MASTER_DOCUMENTATION.md   This file
  releases/                            Dated release notes (v1.9 -> v2.6)
  *.md                                  Historical build-log docs

Pics/                             Screenshots, diagrams, logo

scripts/
  apply_firewall.sh              Active firewall/NAT script
  performance_check.sh            Active resource-usage check
  netsentry_dashboard.py          Historical, superseded
  netsentry_portal.py             Historical, superseded
  netsentry_status_api.py         Historical, superseded
  honeypot_lite.py                Historical decoy login service
  http_test_service.py            Historical test HTTP service
  start_python_services.py        Historical service launcher
  stop_python_services.py         Historical service stopper

suricata/rules/local.rules       Active AP-side Suricata rules

tests/                           Manual validation test notes (iptables,
                                  tcpdump, AdGuard DNS filtering)

NetSentry-Gateway-Architecture.pdf
```

---

## 13. Version History

| Version | Milestone                                                          |
| ------- | -------------------------------------------------------------------- |
| V0      | Early lab-over-Wi-Fi-SSH stage, no gateway function yet                |
| v1.5    | Early gateway/AP/DHCP foundation                                        |
| v1.6    | Web dashboard foundation                                                 |
| v1.8    | Stable homelab release: AP + DHCP + DNS filtering + firewall/NAT + HTTPS dashboard + **Snort** IDS + alert watcher |
| v1.9    | Suricata introduced alongside Snort                                      |
| v2.1    | Wazuh mini-SIEM integration added                                         |
| v2.2    | **Snort removed** — duplicate alerts with Suricata. Built-in IDS dashboard (`/admin/ids`, `/api/ids/alerts`) removed from Flask app; investigation moved fully to Wazuh |
| v2.3    | System performance tuning for Wazuh + Suricata on constrained hardware       |
| v2.6    | **Current stable release** — Suricata + Wazuh rule tuning, firewall log correlation, validated after reboot |

---

## 14. Testing and Validation

### Manual client-side tests (PowerShell)

```text
ping, large ping, TCP connection attempts, DNS queries, port probes
```

### Stronger tests (Ubuntu VM)

```text
nmap scans, hping3 SYN tests, NULL/FIN/XMAS scans, DNS bypass testing,
crafted traffic
```

### Confirmed working

```text
AP-side Suricata live capture and rule matching
Suricata -> eve.json -> Filebeat -> Wazuh pipeline
Firewall log correlation in Wazuh (NETSENTRY_FW_* prefixes)
AdGuard DNS API integration in the dashboard
iptables firewall dashboard visibility
Tailscale interface visibility and remote SSH/HTTPS access
Reboot persistence for all active services
```

### v2.6 validation checklist

```bash
# 1. Service status
for s in ssh nginx netsentry-web netsentry-ap-interface hostapd \
         AdGuardHome tailscaled netsentry-firewall netsentry-dnsmasq \
         suricata wazuh-indexer wazuh-manager wazuh-dashboard filebeat; do
  printf "%-32s enabled=%-12s active=%s\n" \
  "$s" \
  "$(systemctl is-enabled "$s" 2>/dev/null || echo not-found)" \
  "$(systemctl is-active "$s" 2>/dev/null || echo not-found)"
done

# 2. Performance
./scripts/performance_check.sh

# 3. Suricata rule validation
sudo suricata -T -c /etc/suricata/suricata.yaml \
  -S /etc/suricata/rules/local.rules -i wlx200db0220b9a \
  -l /tmp/suricata-rule-test

# 4. Wazuh manager check
sudo systemctl is-active wazuh-manager wazuh-indexer wazuh-dashboard filebeat

# 5. Firewall log check
journalctl -k -n 50 --no-pager | grep NETSENTRY_FW

# 6. Wazuh firewall alert check
sudo grep -i "NetSentry firewall" /var/ossec/logs/alerts/alerts.json | tail -5

# 7. Snort removal verification
systemctl list-units --type=service | grep -i snort || echo "OK: no Snort services"

# 8. Dashboard accessibility
#    NetSentry: https://192.168.1.19/       -> gateway status page loads
#    Wazuh:     https://192.168.1.19:8443/  -> SIEM dashboard loads

# 9. Disabled services
for s in docker.service docker.socket containerd.service; do
  printf "%-24s %s\n" "$s" "$(systemctl is-enabled "$s" 2>/dev/null || echo not-found)"
done
```

---

## 15. Known Issues

1. **Admin IP mismatch in `apply_firewall.sh`.** The script hardcodes
   `ADMIN_IP="192.168.1.10"`. Every other reference in the codebase — the
   Flask app, Nginx config, Suricata rules, and all documentation — uses
   `192.168.1.11`. This has already been the subject of two separate
   "adjusting admin ip" fixes in git history, meaning the drift keeps
   recurring rather than being permanently fixed. **Correct value:
   `192.168.1.11`.** Update the firewall script and re-run the validation
   checklist.
2. **Placeholder secrets in a superseded file.** `scripts/netsentry_portal.py`
   still contains `ADMIN_PASSWORD = "PASSWORDHERE"` and a placeholder
   `PORTAL_SECRET`. Not real credentials, but should be removed/parameterized
   before the repo is treated as fully public-facing (see Section 11).
3. **Three historical dashboard implementations remain in `scripts/`**
   (`netsentry_dashboard.py`, `netsentry_portal.py`, `netsentry_status_api.py`)
   alongside the current `app/netsentry_app.py`. They're clearly marked as
   historical in this document and the README, but anyone skimming the repo
   without reading docs first could reasonably mistake one of them for the
   active service.

---

## 16. Unfinished / Planned Work

### Actions dashboard (planned)

Route: `/admin/actions`

Planned client actions: **Watch**, **Restrict**, **Ban**, **Unblock**

Safe implementation order:

```text
1. UI only (no backend effect)
2. Persist state to a file, still no enforcement
3. Watch mode (logging only)
4. Restrict mode
5. Ban mode
6. Unblock mode
7. Firewall enforcement helper (the only step that touches iptables)
```

Persistent state file: `/var/lib/netsentry/client_actions.json`

**Hard safety constraints for this feature:**

Never allow automatic blocking of:

```text
192.168.1.11 (admin)   10.10.10.1 (AP gateway)
192.168.1.19 (home IP)  127.0.0.1 (loopback)
```

Never allow subnet-level blocking:

```text
10.10.10.0/24
192.168.1.0/24
```

### Other planned items

```text
Nginx/Flask HTTPS attack watcher (path/user-agent-level detection,
  since Suricata cannot see inside HTTPS)
Home-side Suricata sensor on enp3s0 (currently only AP-side coverage exists)
Final architecture diagram polish
```

### HTTPS visibility limitation (context for the above)

Suricata sees client IP, server IP, TCP port, TLS/HTTPS connection,
scan/flood/DNS-bypass behavior. It **cannot** see inside HTTPS: request
paths (`/admin/login`), headers, POST bodies, user-agents, or
username/password fields. That's why responsibility is split:

```text
Suricata     = network-level IDS
Nginx logs   = HTTPS request/path-level detection (planned)
Flask logs   = admin/auth-level detection (already partially covered by
               login lockout, see Section 8)
```
