# NetSentry v1.6 — Unified Web Foundation

## 1. Goal

The goal of this phase was to convert NetSentry from several separate Flask services into one unified web interface while preserving the real purpose of the server: a Debian-based secure gateway appliance.

The target flow is:

```text
Browser
  ↓
Nginx :80/:443
  ↓
Flask app on 127.0.0.1:5000 only
```

This keeps Flask hidden from the LAN and makes Nginx the only web entry point.

## 2. Current Gateway Context

NetSentry is not only a dashboard. It is a gateway system:

```text
Client device
  ↓ Wi-Fi
NetSentry AP interface
  ↓
Debian routing/firewall/DNS/IDS stack
  ↓
WAN/HOME interface
  ↓
ISP router / Internet
```

Current deployment values:

| Item | Value |
|---|---|
| WAN/HOME interface | `enp3s0` |
| WAN/HOME IP | `192.168.1.19` |
| AP interface | `wlx200db0220b9a` |
| AP gateway IP | `10.10.10.1` |
| AP LAN | `10.10.10.0/24` |
| HOME LAN | `192.168.1.0/24` |
| Admin PC | `192.168.1.11` |
| SSID | `NetSentry-Test` |

## 3. Implemented Web Routes

### Public routes

Public routes explain the project and must not expose private operational data.

- `/`
- `/about`
- `/features`
- `/architecture`
- `/status`
- `/docs`
- `/hardware`
- `/contact`

### Admin routes

Admin routes require login and are LAN-restricted by Nginx.

- `/admin/login`
- `/admin/logout`
- `/admin/dashboard`
- `/admin/clients`
- `/admin/dns`
- `/admin/firewall`
- `/admin/ids`
- `/admin/logs`
- `/admin/network`

### API routes

The API is read-only in v1.6.

- `/api/status`
- `/api/clients`
- `/api/dns/stats`
- `/api/network/interfaces`
- `/api/network/routes`
- `/api/ids/alerts`
- `/api/firewall/rules`
- `/api/logs`

## 4. Implemented Features

### Public website

The public website now includes:

- Project explanation
- Public-safe status
- Feature overview
- More detailed architecture explanation
- Documentation page with GitHub link
- Hardware setup page with dynamic `inxi` support
- Contact page

### Admin dashboard

The dashboard now shows:

- Internet status
- Uptime
- Connected clients
- IDS alert count
- DNS blocked count and block rate
- IPv4 forwarding state
- NAT state
- Service status
- Interface status
- Gateway overview

### DNS page

The DNS page reads from AdGuard Home and displays:

- API connection status
- Total DNS queries
- Blocked DNS queries
- Blocked percentage
- Top blocked domains
- Top queried domains
- Top clients
- Recent DNS queries
- Raw API debug section

Credentials are not stored in Git. They are configured in:

```text
/etc/netsentry/netsentry-web.env
```

### Firewall page

The firewall page uses a read-only helper:

```text
/usr/local/sbin/netsentry-read-firewall
```

It displays:

- IPv4 forwarding
- Final INPUT drop state
- NAT masquerade state
- LAN NAT exception state
- Human-readable access matrix
- Raw INPUT/FORWARD/NAT rules

The helper only reads firewall state. It does not modify rules.

### IDS page

The IDS page reads Snort alerts from:

```text
snort/alerts/alerts.jsonl
```

It includes filters for:

- source IP
- destination IP
- SID
- protocol
- keyword
- load limit

It also includes a button to back up and clear alert files. Before clearing, the files are copied to:

```text
snort/alerts/archive/
```

### Logs page

The logs page reads and normalizes several sources:

- honeypot logs
- HTTP test service logs
- portal auth logs
- portal decoy logs
- app logs
- agent logs
- Snort fast alerts

It includes filtering by source and keyword.

### Network page

The network page shows:

- hostname
- load
- memory use
- disk use
- interfaces
- routes
- listening ports

## 5. Security Decisions

- Flask binds only to `127.0.0.1:5000`.
- Nginx is the public/LAN-facing web entry point.
- Admin routes are protected by login.
- `/admin/*` and `/api/*` are restricted by Nginx LAN rules.
- Password and AdGuard credentials are stored outside Git.
- Firewall access from the web app is read-only.
- No block-IP button exists yet.
- No restart-service button exists yet.
- No tcpdump start button exists yet.
- Dangerous actions are reserved for a future privileged agent.

## 6. Authentication Fix

During testing, the login page appeared to accept wrong credentials because an already-valid browser session could redirect to the dashboard. This was fixed by ensuring POST login attempts always verify credentials and clear the session on failed login.

## 7. Hardware Setup

The hardware page was updated using the server inventory from `inxi -Fxz`.

Known hardware:

| Component | Value |
|---|---|
| System | HP Pro3500 Series desktop |
| OS | Debian GNU/Linux 13 trixie |
| Kernel | `6.12.86+deb13-amd64` |
| CPU | Intel Pentium G2030 dual-core Ivy Bridge |
| Memory | 4 GiB installed |
| Storage | Western Digital WD5000AAKX 500 GB HDD |
| WAN NIC | Realtek RTL8111/8168/8211/8411 PCIe Gigabit Ethernet |
| AP adapter | Realtek RTL8188EUS 802.11n USB Wi-Fi adapter |

The hardware page attempts to read live data using:

```bash
inxi -Fxz
```

If that command is unavailable, the static known hardware summary remains visible.

## 8. Frontend Assistance Disclosure

The HTML/CSS visual presentation and web layout were created with external help from a friend because the main project focus is cybersecurity, Linux networking, firewalling, IDS, DNS filtering, and gateway architecture. The friend’s identity will only be revealed after explicit consent.

The project owner integrated, configured, deployed, tested, and secured the web application inside the NetSentry gateway environment.

## 9. Validation Commands

```bash
sudo systemctl status netsentry-web.service --no-pager -l
sudo ss -tulpen | grep -E ':80|:443|:5000'
curl -I http://192.168.1.19/
curl -I http://192.168.1.19/admin/login
curl -s http://192.168.1.19/api/status | python3 -m json.tool
curl -s http://192.168.1.19/api/dns/stats | python3 -m json.tool
curl -s http://192.168.1.19/api/firewall/rules | python3 -m json.tool
curl -s http://192.168.1.19/api/ids/alerts | python3 -m json.tool
curl -s http://192.168.1.19/api/logs | python3 -m json.tool
```

Expected architecture:

```text
Nginx listens on 0.0.0.0:80
Flask listens only on 127.0.0.1:5000
```

## 10. Current Limitations

- HTTPS is not enabled yet.
- Role-based users are not fully implemented yet.
- Active response actions require the future privileged agent.
- Alert clearing is implemented with backup, but full audit logging is future work.
- IDS visibility depends on Snort and `snort_alert_watcher.py` producing `alerts.jsonl`.
- AdGuard statistics depend on valid local API credentials.

## 11. Next Work

- Add HTTPS with a self-signed certificate.
- Add screenshots to documentation.
- Improve role-based authorization.
- Add audit logging for clear-alert action.
- Later build the privileged agent for controlled firewall actions, service restarts, and tcpdump captures.
