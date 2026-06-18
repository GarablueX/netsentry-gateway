# NetSentry Gateway - Master Documentation

## 1. Project Overview

NetSentry is a Debian-based network security gateway project.

The goal is to turn a Debian machine into a security gateway that provides:

- Wi-Fi AP/client access
- DHCP for AP clients
- DNS filtering through AdGuard
- Firewalling and routing
- NAT/forwarding
- HTTPS web dashboard
- Snort IDS monitoring
- Structured IDS alert processing
- Dashboard visibility for services, firewall, DNS, clients, and IDS alerts

The project is designed as a gateway appliance, not only as a web dashboard.

**Current status:** NetSentry is functional as a gateway, AP, DNS filter, firewall, dashboard, and AP-side IDS system.

---

## 2. Hardware and Operating System

### Current Hardware

```
Machine: HP Pro3500 Series desktop
CPU: Intel Pentium G2030
RAM: 4 GiB
Disk: 500 GB HDD
OS: Debian GNU/Linux 13 trixie
Kernel: 6.12.x
```

### Network Adapters

| Interface | Role | Type |
|-----------|------|------|
| enp3s0 | HOME-WAN side | Ethernet |
| wlx200db0220b9a | AP/client side | Wi-Fi |

The Wi-Fi adapter is used as the AP interface for clients.

---

## 3. Network Layout

### HOME / Upstream Side

| Property | Value |
|----------|-------|
| Interface | enp3s0 |
| Network | 192.168.1.0/24 |
| NetSentry IP | 192.168.1.19 |
| Admin PC | 192.168.1.11 |

### AP / Client Side

| Property | Value |
|----------|-------|
| Interface | wlx200db0220b9a |
| Network | 10.10.10.0/24 |
| Gateway | 10.10.10.1 |
| SSID | NetSentry-Test |

### DHCP Range

```
10.10.10.50 - 10.10.10.150
```

### Important IPs

| Host | IP |
|------|-----|
| Admin laptop | 192.168.1.11 |
| NetSentry HOME IP | 192.168.1.19 |
| NetSentry AP IP | 10.10.10.1 |
| AP subnet | 10.10.10.0/24 |
| HOME subnet | 192.168.1.0/24 |

---

## 4. High-Level Architecture

### Traffic Flow

```
AP client
  ↓
NetSentry AP interface wlx200db0220b9a
  ↓
Debian routing/firewall/NAT
  ↓
HOME/WAN interface enp3s0
  ↓
ISP router / internet
```

### Web Dashboard Flow

```
Browser
  ↓
Nginx :80/:443
  ↓
Flask app on 127.0.0.1:5000
```

### Security Services

| Service | Role |
|---------|------|
| AdGuardHome | DNS filtering |
| dnsmasq | DHCP for AP clients |
| iptables | Firewall and NAT |
| Snort | AP-side IDS |
| Snort watcher | Alert parser and dashboard JSON writer |
| Nginx | HTTPS frontend |
| Flask | Dashboard backend |

---

## 5. Core Systemd Services

### Important Services

```
ssh.service
nginx.service
netsentry-web.service
netsentry-ap-interface.service
netsentry-firewall.service
netsentry-dnsmasq.service
hostapd.service
AdGuardHome.service
netsentry-snort-ap.service
netsentry-snort-watcher.service
```

The legacy `netsentry-server.service` is no longer used.

### Check Service Status

```bash
for s in ssh nginx netsentry-web netsentry-ap-interface hostapd AdGuardHome netsentry-firewall netsentry-dnsmasq netsentry-snort-ap netsentry-snort-watcher; do
  printf "%-32s enabled=%-12s active=%s\n" \
  "$s" \
  "$(systemctl is-enabled "$s" 2>/dev/null || echo not-found)" \
  "$(systemctl is-active "$s" 2>/dev/null || echo not-found)"
done
```

---

## 6. AP Interface Configuration

The AP interface is `wlx200db0220b9a` and is configured with `10.10.10.1/24`.

The interface is managed by `netsentry-ap-interface.service`.

**Note:** NetworkManager should not manage the AP Wi-Fi interface.

### Unmanaged Configuration

File: `/etc/NetworkManager/conf.d/netsentry-ap-unmanaged.conf`

Expected content:

```ini
[keyfile]
unmanaged-devices=interface-name:wlx200db0220b9a
```

---

## 7. DHCP

NetSentry uses a dedicated dnsmasq service for AP DHCP.

The default Debian `dnsmasq.service` should stay disabled because AdGuard already uses DNS port 53.

### Expected Service State

| Service | State |
|---------|-------|
| dnsmasq.service | disabled / inactive |
| netsentry-dnsmasq.service | enabled / active |

### NetSentry DHCP Configuration

**Config file:** `config/ap/dnsmasq-netsentry.conf`

### Expected DHCP Behavior

| Property | Value |
|----------|-------|
| Interface | wlx200db0220b9a |
| DHCP range | 10.10.10.50 - 10.10.10.150 |
| Gateway option | 10.10.10.1 |
| DNS option | 10.10.10.1 |

---

## 8. DNS Filtering

AdGuardHome provides DNS filtering.

**Service:** `AdGuardHome.service`

AdGuard listens on DNS port 53 and provides a web/API interface on port 3001.

The dashboard connects to AdGuard through:

```
http://127.0.0.1:3001
```

### Credentials

AdGuard credentials are stored outside Git in:

```
/etc/netsentry/netsentry-web.env
```

**Important:** Secrets must never be committed.

---

## 9. Firewall and NAT

Firewall rules are applied by `netsentry-firewall.service`.

The service runs `scripts/apply_firewall.sh`.

### Firewall Controls

- INPUT access to NetSentry
- FORWARD traffic between AP and WAN/HOME
- NAT/MASQUERADE for AP clients
- Admin-only access to sensitive services
- DNS/DHCP/web access policy

### Important Variables

```bash
ADMIN_IP="192.168.1.11"
HOME_LAN="192.168.1.0/24"
AP_NET="10.10.10.0/24"
WAN_I="enp3s0"
AP_I="wlx200db0220b9a"
```

### Important Firewall Concepts

- ESTABLISHED,RELATED traffic is allowed
- INVALID packets are dropped
- Loopback is allowed
- AP clients can route through the gateway
- AP clients use NAT when going out through enp3s0
- Unknown INPUT traffic is dropped

### Apply Firewall Immediately

```bash
sudo systemctl restart netsentry-firewall
```

---

## 10. Web Dashboard

The dashboard is a Flask application behind Nginx.

### Key Files

| File | Purpose |
|------|---------|
| app/netsentry_app.py | Main Flask file |
| app/static/css/netsentry.css | Main CSS |
| app/templates/admin/ | Admin templates |
| app/templates/public/ | Public templates |

### Flask Service

**Service:** `netsentry-web.service`

**Listens on:** `127.0.0.1:5000`

---

## 11. Nginx and HTTPS

Nginx is the public web entry point.

**Config file:** `config/nginx/netsentry.conf` and `/etc/nginx/sites-available/netsentry`

Nginx proxies to Flask at `127.0.0.1:5000`.

### HTTPS Certificates

Self-signed certificates are stored outside Git:

```
/etc/netsentry/certs/netsentry.crt
/etc/netsentry/certs/netsentry.key
```

**Important:** Certificate private keys must never be committed.

Admin/API access is protected by Nginx allow/deny logic and Flask login.

---

## 12. Authentication and Secrets

### Web App Environment File

**Location:** `/etc/netsentry/netsentry-web.env`

### Contains

```
NETSENTRY_WEB_USER
NETSENTRY_WEB_PASSWORD or NETSENTRY_WEB_PASSWORD_HASH
NETSENTRY_WEB_SECRET
NETSENTRY_ADGUARD_URL
NETSENTRY_ADGUARD_USER
NETSENTRY_ADGUARD_PASSWORD
PROJECT/CONTACT settings
```

### File Permissions

```bash
sudo chown root:root /etc/netsentry/netsentry-web.env
sudo chmod 600 /etc/netsentry/netsentry-web.env
```

### Never Commit

- passwords
- hash secrets
- Wi-Fi passphrases
- private keys
- runtime alert logs
- pcap files
- .env files

---

## 13. Snort AP-Side IDS

Snort is used as an AP-side IDS sensor.

### Configuration

| Property | Value |
|----------|-------|
| Capture interface | wlx200db0220b9a |
| Rules file | snort/rules/local_ap.rules |
| Snort config | /usr/local/etc/snort/snort.lua |
| Repo copy | config/snort/snort.lua |

### Working Snort Command

```bash
sudo stdbuf -oL -eL snort -c /usr/local/etc/snort/snort.lua \
  -R ~/netsentry-gateway/snort/rules/local_ap.rules \
  -i wlx200db0220b9a \
  -A alert_fast | stdbuf -oL tee -a ~/netsentry-gateway/snort/alerts/alert_fast.txt
```

### Service

**Service:** `netsentry-snort-ap.service`

**Repo service copy:** `config/systemd/netsentry-snort-ap.service`

---

## 14. Snort Variables

NetSentry Snort rules use variables instead of hardcoded IPs.

### Important Variables

```
$AP_LAN              10.10.10.0/24
$HOME_LAN            192.168.1.0/24
$ADMIN_IP            192.168.1.11
$AP_GATEWAY          10.10.10.1
$HOME_GATEWAY        192.168.1.19
$NETSENTRY_GATEWAY   [10.10.10.1,192.168.1.19]
```

These variables are defined in Snort Lua config and used by `local_ap.rules`.

---

## 15. Snort Alert Delay Fix

Snort initially detected alerts with delay because packet/event batching was active.

### Working Fast Config

```lua
daq = {
    batch_size = 1
}

event_queue = {
    max_queue = 16,
    log = 16,
    order_events = 'priority'
}
```

### Important Lessons

- `daq.batch_size = 1` reduces alert delay
- `event_queue.log = 1` was too aggressive and hid alerts
- `event_queue.log = 16` allows multiple matching alerts to appear

---

## 16. Snort Rule Severity Convention

NetSentry currently uses Snort rev as a project severity convention.

| Rev | Severity |
|-----|----------|
| 1 | Low |
| 2 | Medium |
| 3 | High / Critical |

**Note:** This is a NetSentry convention. In standard Snort, rev normally means rule revision. In this project, it is intentionally used to drive dashboard severity colors and Rev 3 handling.

---

## 17. Current Snort Rule Categories

Current AP-side rules cover:

- ICMP ping from non-admin
- Oversized ICMP payload
- ICMP sweep
- SSH SYN attempts
- SSH repeated connection attempts
- AdGuard UI access attempts
- Old dashboard/API/test port probing
- TCP SYN burst
- TCP NULL scan
- TCP FIN scan
- TCP XMAS scan
- TCP SYN/FIN scan
- TCP SYN flood
- UDP flood
- TCP reset flood
- DNS bypass attempts
- FTP access attempts
- FTP anonymous login attempts
- AP client scanning AP clients
- AP client probing sensitive gateway ports
- SMB/RDP/Telnet style access attempts

### HTTPS Limitation

Rules that rely on HTTP paths only work on plain HTTP, not HTTPS.

---

## 18. HTTPS Limitation

Snort can detect HTTPS traffic at the network level, but it cannot inspect encrypted web paths.

### Snort Can Detect

- client IP
- server IP
- TCP port
- TLS/HTTPS connection
- scan behavior
- DNS bypass
- SSH attempts
- gateway probing
- flood behavior

### Snort Cannot See Inside HTTPS

- /admin/login
- /admin/dashboard
- HTTP headers
- POST body
- User-Agent
- username/password fields

### Implication

- **Snort** = network IDS
- **Nginx logs** = HTTPS request/path detection
- **Flask logs** = admin/auth detection

---

## 19. Snort Alert Watcher

The alert watcher parses raw Snort alerts and creates structured JSON.

### Script

**File:** `scripts/snort_alert_watcher.py`

**Input:** `snort/alerts/alert_fast.txt`

### Outputs

```
data/ids/alerts.jsonl
data/ids/alerts_latest.json
data/ids/latest_rev3.json
```

### Extracted Data

- timestamp
- Snort time
- GID
- SID
- REV
- severity
- message
- protocol
- source IP
- source port
- destination IP
- destination port
- priority
- raw alert line

### Watcher Service

**Service:** `netsentry-snort-watcher.service`

**Repo service copy:** `config/systemd/netsentry-snort-watcher.service`

**Note:** Runtime JSON files are ignored by Git.

---

## 20. IDS Dashboard

### Admin IDS Page

**URL:** `/admin/ids`

**API:** `/api/ids/alerts`

### Dashboard Display

The dashboard now shows:

- Total alerts
- Filtered alerts
- Rev 1 / low count
- Rev 2 / medium count
- Rev 3 / high count
- Latest Rev 3 detection
- Top source IPs
- Top SIDs
- Top protocols
- Rev filter
- Source/destination/SID/protocol/keyword filters
- Alert table with rev colors
- PCAP/evidence filename when available

### Color Logic

| Rev | Color |
|-----|-------|
| 1 | green |
| 2 | yellow |
| 3 | red |

---

## 21. Dashboard Service Visibility

The main dashboard status was updated to include IDS-related services.

Now included:

- netsentry-snort-ap
- netsentry-snort-watcher
- snort process
- snort watcher process

This helps verify from the web dashboard whether IDS is alive.

---

## 22. Rev 3 Evidence Capture

The intended Rev 3 behavior is:

1. Rev 3 alert detected
2. Watcher identifies source IP
3. tcpdump captures traffic for 10 seconds
4. PCAP is saved
5. Dashboard displays PCAP filename

### PCAP Files

**Important:** PCAP files are runtime evidence and must not be committed.

**Expected folder:** `snort/pcaps/`

### Read a PCAP

```bash
sudo tcpdump -nn -r file.pcap
```

**Note:** Opening a .pcap directly as text will show binary garbage. That is normal.

---

## 23. Testing Performed

### PowerShell Tests

Simple client tests:

- ping
- large ping
- TCP connection attempts
- DNS queries
- port probes

### Ubuntu VM Tests

Stronger tests:

- nmap scans
- hping3 SYN tests
- NULL/FIN/XMAS scans
- DNS bypass testing
- crafted traffic

### Confirmed Working

- Snort live capture
- Snort variables
- detection_filter
- fast alerting
- Snort AP service
- Snort watcher
- structured JSON
- IDS dashboard Rev filters
- Latest Rev 3 display
- dashboard service checks

---

## 24. Git and Runtime Ignore Policy

Commit source/config/documentation.

Do not commit runtime output.

### Ignore

```
snort/alerts/*
snort/pcaps/*
data/ids/*.json
data/ids/*.jsonl
data/ids/rev3_flags/*
*.pcap
*.bak*
*.key
*.crt
```

### Pre-commit Secret Check

Before committing, run:

```bash
git diff --cached | grep -Ei 'wpa_passphrase=|NETSENTRY_WEB_PASSWORD=|NETSENTRY_WEB_SECRET=|-----BEGIN .*PRIVATE KEY-----|PUT_YOUR_REAL_PASSWORD|PUT_A_LONG_RANDOM_SECRET' \
&& echo "STOP: real secret pattern found" \
|| echo "OK: no real secret patterns found"
```

---

## 25. Current Stable State

### Stable Components

- Debian gateway
- AP interface
- DHCP
- DNS filtering
- firewall/NAT
- HTTPS dashboard
- Snort AP IDS
- Snort AP service
- Snort alert watcher
- IDS structured JSON
- IDS Rev dashboard
- dashboard service checks

**Status:** NetSentry is now close to a complete v1 security gateway.
