# NetSentry v1.6 — Unified Web Foundation

## 1. Purpose of this Version

NetSentry v1.6 introduces the first complete web foundation for the NetSentry gateway project.

The goal of this version is not to replace the gateway itself. The gateway remains the core product. The web interface is only the visibility and presentation layer for the existing security gateway.

The final product is a Debian-based secure gateway where clients connect through a controlled Wi-Fi access point, receive DHCP, use filtered DNS, pass through firewall and NAT rules, and generate security visibility through IDS alerts, logs, and monitoring.

The web interface gives a clean way to observe that gateway.

## 2. Final Web Architecture

The web architecture follows this design:

```text
Browser
  ↓
Nginx :80 / :443
  ↓
Flask App :5000 localhost only
  ├── Public website
  ├── Admin dashboard
  └── Read-only API
```

The Flask application is not exposed directly to the network. It listens only on:

```text
127.0.0.1:5000
```

Nginx is the only LAN-facing web entry point.

This is important because Flask is an application server, not the secure front door. Nginx handles external access, route protection, and future HTTPS.

## 3. What NetSentry v1.6 Adds

This version adds:

* A unified Flask web application
* Nginx reverse proxy integration
* Public project pages
* Admin dashboard pages
* Read-only API endpoints
* Admin login
* Session-based authentication
* systemd service for automatic startup
* Environment-based secret configuration
* AdGuard API integration
* Snort alert visibility
* Firewall read-only visibility
* DHCP client visibility
* Logs visibility
* Network interface and route visibility
* Improved NetSentry visual design using HTML/CSS templates

## 4. Existing Gateway Foundation

Before v1.6, NetSentry already had a working gateway foundation.

Current gateway facts:

```text
Gateway OS: Debian
HOME / upstream interface: enp3s0
HOME / upstream IP: 192.168.1.19
AP interface: wlx200db0220b9a
AP-side gateway IP: 10.10.10.1
AP LAN: 10.10.10.0/24
Admin PC: 192.168.1.11
```

Core services already existed:

```text
hostapd            → Wi-Fi access point
dnsmasq            → DHCP for AP clients
AdGuard Home       → DNS filtering
iptables           → firewall, NAT, forwarding
Snort 3            → IDS alerts
snort watcher      → parsed JSONL alerts
honeypot_lite      → decoy login service
http_test_service  → HTTP testing service
```

v1.6 builds the web layer on top of these existing components.

## 5. Hardware Setup

The NetSentry server is currently running on an HP desktop machine.

Hardware summary:

```text
Machine: HP Pro3500 Series
Motherboard: Foxconn 2ABF
Firmware: AMI UEFI
CPU: Intel Pentium G2030, dual-core, Ivy Bridge
Memory: 4 GiB RAM
Disk: Western Digital 500 GB HDD
Graphics: Intel HD Graphics 2500
Network Ethernet: Realtek RTL8111/8168/8211/8411
Wi-Fi Adapter: Realtek RTL8188EUS 802.11n USB adapter
```

Network interfaces:

```text
enp3s0
  Role: HOME / upstream interface
  State: up
  Speed: 100 Mbps full duplex

wlx200db0220b9a
  Role: AP / client-side Wi-Fi interface
  State: up
```

Storage:

```text
Total disk: 465.76 GiB
Root filesystem: ext4
Swap: 1.89 GiB
```

The machine is used as a headless Debian gateway.

## 6. Public Web Routes

The public side explains the project. These pages do not expose sensitive data.

Implemented public routes:

```text
/
 /about
 /features
 /architecture
 /status
 /docs
 /hardware
 /contact
```

### `/`

The home page introduces NetSentry as a Debian-based secure gateway. It presents the project at a high level and links to the most important public pages.

It includes buttons to:

```text
/about
/features
/status
/architecture
/docs
```

### `/about`

The about page explains:

* What NetSentry is
* Why the project exists
* The motivation behind building a secure gateway
* The defensive purpose of the project
* The learning goals behind the system
* The GitHub/contact information

It also includes the NetSentry visual identity/logo style.

### `/features`

The features page explains the main capabilities:

* Wi-Fi AP
* DHCP client network
* DNS filtering
* Firewall and NAT
* LAN-to-LAN routing
* IDS monitoring
* Honeypot logging
* Admin dashboard
* Read-only API visibility

### `/architecture`

The architecture page explains both the web architecture and the network architecture.

It covers:

```text
Browser → Nginx → Flask
AP clients → Debian gateway → firewall/DNS/IDS → upstream network
```

It also explains the main data sources used by the dashboard:

```text
DHCP leases
AdGuard API
Snort alert files
Firewall rules
System logs
Linux network commands
```

### `/status`

The status page is public-safe.

It only shows:

* Gateway status
* Internet reachability
* Uptime
* Last update time

It does not show:

* Client IPs
* DNS logs
* Snort alerts
* Firewall rules
* Internal system details

### `/docs`

The docs page points users to project documentation and the GitHub repository for deeper technical details.

### `/hardware`

The hardware page describes the physical NetSentry machine, interfaces, storage, CPU, memory, and network role.

### `/contact`

The contact page provides project contact information and GitHub information.

## 7. Admin Web Routes

The admin side is for gateway monitoring.

Implemented admin routes:

```text
/admin/login
/admin/logout
/admin/dashboard
/admin/clients
/admin/dns
/admin/firewall
/admin/ids
/admin/logs
/admin/network
```

### `/admin/login`

The login page authenticates the administrator.

Authentication uses environment-configured credentials stored outside Git.

The login bug where an old session could make bad credentials appear accepted was fixed. Now a failed login clears the old session and rejects access.

### `/admin/dashboard`

The dashboard provides an overview of the gateway.

It shows:

* Internet status
* Uptime
* Known clients
* Recent IDS alert count
* DNS status
* Firewall status
* Gateway role and network summary

### `/admin/clients`

The clients page reads DHCP lease information and displays AP client visibility.

It shows:

* Client IP
* MAC address
* Hostname
* Lease expiry

### `/admin/dns`

The DNS page reads AdGuard Home API data.

It shows:

* API state
* Total DNS queries
* Blocked DNS queries
* Blocked percentage
* Top blocked domains
* Top clients
* Top queried domains
* Recent DNS queries when available

AdGuard credentials are stored outside Git in the environment file.

### `/admin/firewall`

The firewall page provides human-readable firewall visibility.

It shows:

* IPv4 forwarding state
* Final INPUT drop status
* NAT masquerade status
* LAN NAT exception status
* Human-readable access matrix
* Raw firewall rules for verification

This page is read-only.

### `/admin/ids`

The IDS page reads Snort alert data from the parsed alerts file.

It supports:

* Recent alert display
* Larger alert view limits
* Source IP filter
* Destination IP filter
* SID filter
* Protocol filter
* Keyword filter
* Backup and clear alert files action

The IDS data source is:

```text
snort/alerts/alerts.jsonl
```

### `/admin/logs`

The logs page displays available NetSentry logs.

It supports:

* Source filtering
* Keyword filtering
* Log source counts
* Honeypot logs
* Portal/auth logs when available
* Other gateway logs where available

### `/admin/network`

The network page displays Linux network state.

It shows:

* Interface status
* Routing table
* Listening ports
* Gateway network visibility

## 8. API Routes

Implemented API routes:

```text
/api/status
/api/clients
/api/dns/stats
/api/network/interfaces
/api/network/routes
/api/ids/alerts
/api/firewall/rules
/api/logs
```

The API is read-only in v1.6.

No active response actions are implemented in this version.

The API does not:

* Block IPs
* Restart services
* Start packet captures
* Modify firewall rules
* Change AdGuard filtering
* Modify Snort

Those actions are reserved for a future privileged agent.

## 9. Nginx Integration

Nginx is used as the web front door.

Nginx listens on:

```text
80
443 later
```

Flask listens only on:

```text
127.0.0.1:5000
```

Nginx proxies traffic to Flask.

Expected runtime layout:

```text
0.0.0.0:80        → nginx
127.0.0.1:5000   → Flask app
```

The Flask application should never bind to:

```text
0.0.0.0:5000
```

## 10. systemd Service

The Flask web application runs as a systemd service.

Service name:

```text
netsentry-web.service
```

Service file:

```text
/etc/systemd/system/netsentry-web.service
```

Repository copy:

```text
config/systemd/netsentry-web.service
```

The service starts the app from:

```text
/home/gbx/netsentry-gateway/app/netsentry_app.py
```

The service uses an environment file for secrets.

## 11. Secret Environment File

Secrets are stored outside Git.

Environment file:

```text
/etc/netsentry/netsentry-web.env
```

This file stores:

```text
NETSENTRY_WEB_USER
NETSENTRY_WEB_PASSWORD
NETSENTRY_WEB_SECRET

NETSENTRY_ADGUARD_URL
NETSENTRY_ADGUARD_USER
NETSENTRY_ADGUARD_PASSWORD

NETSENTRY_PROJECT_OWNER
NETSENTRY_GITHUB_URL
NETSENTRY_CONTACT_EMAIL
NETSENTRY_CONTACT_NOTE
```

This file must never be committed.

Correct permissions:

```text
-rw------- root root /etc/netsentry/netsentry-web.env
```

## 12. Firewall Read-Only Helper

The web app needs to display firewall state, but Flask should not have general root permissions.

A read-only helper was created:

```text
/usr/local/sbin/netsentry-read-firewall
```

Repository copy:

```text
scripts/netsentry-read-firewall
```

The helper supports:

```text
input
forward
nat
all
```

It only reads iptables rules.

It does not modify firewall rules.

A sudoers rule allows the web service user to run only this helper without password.

## 13. Security Decisions

Security decisions in v1.6:

* Flask is localhost-only
* Nginx is the web entry point
* Secrets are outside Git
* AdGuard credentials are outside Git
* Firewall helper is read-only
* Dashboard is read-only
* No block-IP button yet
* No service restart button yet
* No tcpdump control yet
* No direct privileged subprocess actions from Flask
* Active control is postponed until a privileged agent exists

## 14. Why There Is No Active Control Yet

Actions such as blocking an IP, restarting services, or starting tcpdump require root-level privileges.

Doing this directly from Flask would be dangerous.

The future design is:

```text
Admin browser
  ↓
Nginx
  ↓
Flask
  ↓
Privileged agent over UNIX socket
  ↓
nftables / tcpdump / systemctl
```

The agent will have a strict command whitelist and audit logging.

Until then, v1.6 remains read-only.

## 15. Development Note About HTML/CSS

The HTML and CSS frontend presentation for this web foundation was created with help from a friend because the project owner is focused on cybersecurity, Linux networking, and gateway architecture rather than frontend web development.

The friend’s identity will only be revealed after receiving their consent.

The cybersecurity-relevant parts of this work are:

* System architecture
* Route separation
* Public vs admin boundaries
* Nginx reverse proxy
* Flask localhost-only deployment
* Environment-based secret handling
* Firewall visibility
* AdGuard API integration
* Snort alert integration
* Logs and network monitoring
* Secure future agent design

## 16. Testing and Validation

Syntax validation:

```bash
python3 -m py_compile app/netsentry_app.py
```

Service validation:

```bash
sudo systemctl status netsentry-web.service --no-pager -l
```

Port validation:

```bash
sudo ss -tulpen | grep -E ':80|:443|:5000'
```

Expected:

```text
nginx on :80
Flask on 127.0.0.1:5000
```

Public route tests:

```bash
curl -I http://192.168.1.19/
curl -I http://192.168.1.19/about
curl -I http://192.168.1.19/features
curl -I http://192.168.1.19/architecture
curl -I http://192.168.1.19/status
curl -I http://192.168.1.19/docs
curl -I http://192.168.1.19/hardware
curl -I http://192.168.1.19/contact
```

Admin routes redirect to login when unauthenticated:

```bash
curl -I http://192.168.1.19/admin/dashboard
curl -I http://192.168.1.19/admin/firewall
```

Expected:

```text
302 FOUND
Location: /admin/login?next=...
```

API tests:

```bash
curl -s http://192.168.1.19/api/status | python3 -m json.tool
curl -s http://192.168.1.19/api/clients | python3 -m json.tool
curl -s http://192.168.1.19/api/dns/stats | python3 -m json.tool
curl -s http://192.168.1.19/api/network/interfaces | python3 -m json.tool
curl -s http://192.168.1.19/api/network/routes | python3 -m json.tool
curl -s http://192.168.1.19/api/ids/alerts | python3 -m json.tool
curl -s http://192.168.1.19/api/firewall/rules | python3 -m json.tool
curl -s http://192.168.1.19/api/logs | python3 -m json.tool
```

## 17. Problems Fixed During v1.6

### Login accepted bad credentials

Cause:

An existing session could make it look like wrong credentials were accepted.

Fix:

The login handler was changed so that POST login always checks credentials and clears old sessions on failed login.

### AdGuard API showed error

Cause:

AdGuard credentials were not configured or were not loaded from the environment file.

Fix:

Added:

```text
NETSENTRY_ADGUARD_URL
NETSENTRY_ADGUARD_USER
NETSENTRY_ADGUARD_PASSWORD
```

to `/etc/netsentry/netsentry-web.env`.

### Environment file parsing error

Cause:

Values containing spaces were not quoted.

Example of bad syntax:

```text
NETSENTRY_PROJECT_OWNER=Saif / GarablueX
```

Correct syntax:

```text
NETSENTRY_PROJECT_OWNER="Saif / GarablueX"
```

### Firewall page showed missing rules

Cause:

The web app could not read iptables state correctly.

Fix:

A read-only helper was created and allowed through a narrow sudoers rule.

### Nginx showed 502 Bad Gateway

Cause:

Nginx was running, but Flask was not reachable on `127.0.0.1:5000`.

Fix:

Checked the systemd service, restored needed templates, restarted the web service, and confirmed Flask was listening locally.

## 18. Current Limitations

v1.6 is not the final NetSentry product.

Current limitations:

* HTTPS is not fully configured yet
* Role-based users are not complete yet
* Admin login is basic but functional
* No privileged agent yet
* No active blocking from dashboard yet
* No service restart from dashboard yet
* No packet capture control yet
* IDS depends on Snort watcher output
* DNS stats depend on AdGuard API availability
* Some log sources depend on runtime log files existing

## 19. Next Work

Recommended next steps:

1. Add HTTPS with self-signed certificate
2. Harden Nginx security headers
3. Improve IDS alert visualization
4. Improve log parsing consistency
5. Add screenshots to documentation
6. Add a proper installation guide
7. Build the privileged agent
8. Add audit logging
9. Add controlled block-IP functionality
10. Add timed packet capture through the agent

## 20. Summary

NetSentry v1.6 successfully turns the project from a collection of gateway services into a unified, professional, web-visible security gateway.

The key result is:

```text
The gateway remains the core product.
The web interface becomes the visibility layer.
Nginx protects access.
Flask stays hidden on localhost.
Secrets stay outside Git.
The dashboard is read-only until a privileged agent exists.
```
