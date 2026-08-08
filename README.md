# NetSentry Gateway

<p align="center">
  <img src="Pics/Logo.png" alt="NetSentry Logo" width="200">
</p>

<p align="center">
  <b>Debian-based homelab security gateway</b><br>
  AP + DHCP + DNS filtering + firewall/NAT + HTTPS dashboard + Suricata IDS + Wazuh SIEM
</p>

<p align="center">
  <b>Current version: v2.6.0 — Stable</b>
</p>

---

## Overview

NetSentry is a **personal homelab / student cybersecurity project** that transforms a Debian machine into a fully functional security gateway appliance. It integrates wireless access point, DHCP, DNS filtering, stateful firewall/NAT, network intrusion detection, security information and event management, and a read-only operations dashboard—all orchestrated via systemd for continuous operation.

This repository serves as a chronological build log, preserving the evolution from early prototypes (V0–v1.9) to the current stable release (v2.6). The authoritative technical reference is [`docs/NETSENTRY_MASTER_DOCUMENTATION.md`](docs/NETSENTRY_MASTER_DOCUMENTATION.md).

---

## Features

- **Wi‑Fi Access Point** (`hostapd`) on isolated client subnet (`10.10.10.0/24`)
- **DHCP Server** (`dnsmasq`) for dynamic client addressing
- **DNS Filtering** via AdGuard Home (blocklists, safe search, parental controls)
- **Stateful Firewall/NAT** (`iptables`) with separate policies for LAN ↔ LAN and LAN ↔ Internet traffic
- **Network IDS** (Suricata) monitoring AP‑side traffic pre‑NAT for real client visibility
- **SIEM** (Wazuh) correlating Suricata alerts, firewall logs, and system events for investigation
- **Read‑Only Operations Dashboard** (Flask + Nginx) displaying gateway status, clients, DNS stats, firewall rules, and service health
- **Remote Administration** via Tailscale (encrypted overlay for SSH/HTTPS access)
- **Service Orchestration** with systemd (boot‑ordered, logging, auto‑restart)
- **Security‑First Design**: Dashboard never modifies firewall or services; privileged actions are isolated in separate agents
- **Transparent Documentation**: Full architecture, configuration, validation checklist, and version history

---

## Architecture

```text
AP Client
   |
   | Wi-Fi / 10.10.10.0/24
   v
NetSentry AP Interface
wlx200db0220b9a / 10.10.10.1
   |
   | Debian firewall / NAT / routing / Suricata IDS
   v
NetSentry HOME/WAN Interface
enp3s0 / 192.168.1.19
   |
   v
Home Router / Internet
```

### Data Flows

- **IDS/SIEM Pipeline**:  
  `Suricata (AP interface) → eve.json → Filebeat → Wazuh manager/indexer → Wazuh dashboard`

- **Dashboard Access**:  
  `Browser → Nginx (:80/:443) → Flask (127.0.0.1:5000) → Gateway operations`  
  `Browser → Nginx (:8443) → Wazuh dashboard → Security investigation`

Full component responsibilities, ports, routes, and rules are detailed in the master documentation.

---

## Getting Started

> **Note**: This project assumes a Debian‑based system with administrative access. Adjust interface names (`wlx200db0220b9a`, `enp3s0`) and IP schemes to match your hardware.

1. **Clone the repository**  
   ```bash
   git clone https://github.com/your-username/netsentry-gateway.git
   cd netsentry-gateway
   ```

2. **Review the master documentation**  
   ```bash
   less docs/NETSENTRY_MASTER_DOCUMENTATION.md
   ```

3. **Install dependencies** (refer to documentation for package lists)

4. **Configure secrets**  
   - Create `/etc/netsentry/netsentry-web.env` with Flask secret and credentials  
   - Place TLS certificates in `/etc/netsentry/certs/`  
   - Never commit real secrets; see [Security and Secrets Policy](#security-and-secrets-policy)

5. **Enable services**  
   ```bash
   sudo systemctl enable nginx netsentry-web netsentry-ap-interface \
                     netsentry-firewall netsentry-dnsmasq hostapd \
                     AdGuardHome tailscaled suricata \
                     wazuh-indexer wazuh-manager wazuh-dashboard filebeat
   sudo systemctl start nginx netsentry-web netsentry-ap-interface \
                     netsentry-firewall netsentry-dnsmasq hostapd \
                     AdGuardHome tailscaled suricata \
                     wazuh-indexer wazuh-manager wazuh-dashboard filebeat
   ```

6. **Verify operation**  
   - Connect a client to the `NetSentry-Test` SSID  
   - Access the dashboard at `http://<netsentry-home-ip>` or `https://<netsentry-home-ip>`  
   - Monitor Wazuh at `https://<netsentry-home-ip>:8443`

---

## Repository Structure

```text
app/
  netsentry_app.py          # Flask dashboard backend (read‑only)
  static/                   # Dashboard CSS/JS
  templates/                # Jinja2 templates (public + admin)

config/
  nginx/                    # Nginx site configuration
  suricata/                 # suricata.yaml reference
  wazuh/                    # Wazuh configuration references
  systemd/                  # Active systemd unit files
  ap/                       # AP/DHCP config examples

docs/
  NETSENTRY_MASTER_DOCUMENTATION.md   # Full technical reference (current)
  releases/                           # Dated release notes (v1.9 → v2.6)
  *.md                                # Historical build‑log docs

Pics/                         # Screenshots and diagrams

scripts/
  apply_firewall.sh         # Active firewall/NAT script
  performance_check.sh      # Resource usage validation
  # Historical/superseded scripts retained for reference:
  # netsentry_dashboard.py, netsentry_portal.py, netsentry_status_api.py,
  # honeypot_lite.py, http_test_service.py, start/stop_python_services.py

suricata/
  rules/local.rules         # Active AP‑side Suricata rules

tests/
  *.md                      # Manual validation test notes
```

---

## Dashboard

The Flask‑based operations dashboard is **intentionally read‑only**—it never modifies firewall rules, restarts services, or triggers packet captures.

### Public Routes

- `/` – Home / landing page  
- `/about` – Project overview  
- `/features` – Component breakdown  
- `/architecture` – Network diagrams  
- `/status` – JSON health endpoint  
- `/docs` – Link to master documentation  
- `/hardware` – Detected system info  
- `/contact` – Contact information

### Admin Routes (session‑authenticated)

- `/admin/dashboard` – Gateway overview (uptime, clients, DNS block rate, etc.)  
- `/admin/clients` – DHCP lease table with MAC/IP/hostname  
- `/admin/dns` – AdGuard Home statistics (queries, blocks, top domains)  
- `/admin/firewall` – Human‑readable iptables policy view  
- `/admin/network` – Interfaces, routes, listening ports, Tailscale status

Authentication uses environment‑based credentials with HMAC comparison, session timeout, login lockout, and CSRF protection.

> **Note**: IDS/log investigation is handled exclusively by Wazuh as of v2.2 to avoid maintaining a duplicate alert viewer.

---

## Security and Secrets Policy

Never commit the following to the repository:

- Wi‑Fi passphrases  
- AdGuard passwords  
- Web dashboard passwords  
- `NETSENTRY_WEB_SECRET`  
- Private TLS keys  
- `.env` files  
- Runtime alert/log files  
- PCAP captures  
- Real credentials  

Secrets are stored outside Git:

```text
/etc/netsentry/netsentry-web.env
/etc/netsentry/certs/
```

A pre‑commit helper script checks for accidental secret leaks:

```bash
git diff --cached | grep -Ei 'wpa_passphrase=|NETSENTRY_WEB_PASSWORD=|NETSENTRY_WEB_SECRET=|-----BEGIN .*PRIVATE KEY-----|PUT_YOUR_REAL_PASSWORD|PUT_A_LONG_RANDOM_SECRET' \
  && echo "STOP: real secret pattern found" \
  || echo "OK: no real secret patterns found"
```

> **Historical note**: `scripts/netsentry_portal.py` contains placeholder credentials (`ADMIN_PASSWORD = "PASSWORDHERE"`, `PORTAL_SECRET = "change_this_secret_later_please"`). These are unused and should be removed or replaced before treating the repository as public‑facing.

---

## Known Issues & Todo

- **Admin IP mismatch**: `apply_firewall.sh` hardcodes `ADMIN_IP="192.168.1.10"` while the rest of the repo uses `192.168.1.11`. Use `192.168.1.11` as the correct value and update the firewall script accordingly.
- **Optional features** (see master documentation for safe implementation order):
  - Actions dashboard (watch/restrict/ban/unblock clients)
  - Safe firewall enforcement helper
  - Nginx/Flask HTTPS attack watcher
  - Home‑side Suricata sensor on `enp3s0`
  - Final architecture diagram polish

---

## Validation

See `docs/NETSENTRY_MASTER_DOCUMENTATION.md`, Section 14 for a step‑by‑step validation checklist covering:
- IP connectivity and DHCP
- DNS filtering effectiveness
- Firewall rule correctness
- IDS alert generation
- Log forwarding to Wazuh
- Dashboard authentication and responsiveness
- Service persistence across reboots

Manual test notes are also available in the `tests/` directory.

---

## License

This project is provided as‑is for educational and personal use. No formal license is applied; assume all rights reserved unless explicitly stated otherwise. If you wish to reuse significant portions, please contact the author.

---

## Acknowledgments

Special thanks to the open‑source projects that make NetSentry possible:

- [Debian](https://www.debian.org/)
- [hostapd](https://w1.fi/hostapd/)
- [dnsmasq](http://www.thekelleys.org.uk/dnsmasq/doc.html)
- [AdGuard Home](https://github.com/AdguardTeam/AdGuardHome)
- [netfilter/iptables](https://wiki.nftables.org/wiki-nftables/index.php/Netfilter_)
- [Nginx](https://nginx.org/)
- [Flask](https://flask.palletsprojects.com/)
- [Suricata](https://suricata.io/)
- [Wazuh](https://wazuh.com/)
- [Filebeat](https://www.elastic.co/beats/filebeat)
- [Tailscale](https://tailscale.com/)

---

> **Final note**: NetSentry v2.6.0 demonstrates practical implementation of Linux networking, AP mode, DHCP, DNS filtering, firewalling, IDS/SIEM integration, service automation, remote private administration, and operational dashboard visibility in a real, continuously running environment. It is not an enterprise‑ready product but serves as a comprehensive learning platform for students, hobbyists, and aspiring cybersecurity professionals.