# NetSentry Gateway

**NetSentry** is a Debian-based network security gateway project designed for a controlled lab environment. It combines access-point mode, DHCP, DNS filtering, NAT, firewalling, routing, IDS monitoring, honeypot logging, and a web portal into one security gateway platform.

Current version:

```text
NetSentry v1.5 — AP Gateway Mode
```

---

## Project Status

NetSentry has moved from a host-based monitoring lab into a real routed gateway design.

The system now separates two networks:

```text
HOME / ISP LAN:
  Interface: enp3s0
  NetSentry IP: 192.168.1.19/24
  Network: 192.168.1.0/24
  Admin PC: 192.168.1.11

AP / Client LAN:
  Interface: wlx200db0220b9a
  NetSentry IP: 10.10.10.1/24
  Network: 10.10.10.0/24
  SSID: NetSentry-Test
```

NetSentry acts as the bridge between the upstream home/ISP network and the isolated AP/client network.

---

## Main Components

NetSentry currently includes:

```text
Access Point       hostapd
DHCP Server        dnsmasq
DNS Filtering      AdGuard Home
Firewall/NAT       iptables
Routing            Linux IP forwarding
IDS                Snort 3
Alert Watcher      Python JSONL parser
Dashboard          Flask-based IDS dashboard
Status API         Flask-based system status API
Portal             Flask-based NetSentry portal
Honeypot           Lightweight fake login service
```

---

## Confirmed Working in v1.5

The following features are confirmed working:

```text
AP mode works on wlx200db0220b9a
AP clients connect successfully
AP clients receive DHCP leases from dnsmasq
AP clients use 10.10.10.1 as their gateway
AP clients use 10.10.10.1 as DNS
AdGuard remains responsible for DNS on port 53
NetSentry portal is reachable from the AP LAN
NetSentry portal is reachable from the HOME LAN
AP clients have internet through NAT
Firewall blocks AP clients from admin-only services
Firewall allows selected client-facing services
ISP router static route allows HOME LAN to reach AP LAN
LAN-to-LAN routing works
```

---

## Network Access

From the HOME / ISP LAN:

```text
http://192.168.1.19:5500
```

From the AP / Client LAN:

```text
http://10.10.10.1:5500
```

The portal listens on:

```text
0.0.0.0:5500
```

so it can be reached through both NetSentry interfaces.

---

## Services and Ports

|        Port | Service           | Access Policy                           |
| ----------: | ----------------- | --------------------------------------- |
|          22 | SSH               | Admin only                              |
|          53 | AdGuard DNS       | HOME LAN + AP LAN                       |
|          67 | DHCP              | AP LAN                                  |
|        3001 | AdGuard UI        | Admin only                              |
|        5050 | IDS Dashboard     | Admin only                              |
|        5051 | Status API        | HOME LAN + AP LAN                       |
|        5500 | NetSentry Portal  | HOME LAN + AP LAN                       |
|        8081 | HTTP Test Service | Admin only                              |
|        8082 | Honeypot          | HOME LAN + AP LAN or AP-focused testing |
|          21 | FTP               | Admin only                              |
| 40000-40100 | FTP Passive Range | Admin only                              |

---

## AP Mode

The AP interface is:

```text
wlx200db0220b9a
```

Static AP-side address:

```text
10.10.10.1/24
```

The AP interface is kept stable after reboot using:

```text
netsentry-ap-interface.service
```

This service handles:

```text
assigning 10.10.10.1/24
bringing the AP interface up
disabling Wi-Fi power saving
```

NetworkManager is configured to ignore the AP interface so it does not reset the static IP.

---

## AP Configuration

Real local AP configs are stored under:

```text
config/ap/hostapd-netsentry.conf
config/ap/dnsmasq-netsentry.conf
```

These files may contain local secrets and should not be committed.

Safe example configs should be committed instead:

```text
config/ap/hostapd-netsentry.example.conf
config/ap/dnsmasq-netsentry.example.conf
```

dnsmasq is used for DHCP only:

```text
port=0
```

This prevents dnsmasq from taking DNS port 53, leaving DNS to AdGuard.

---

## Gateway Firewall

The current firewall model separates AP clients from admin-only services.

AP clients are allowed to access:

```text
5500  NetSentry Portal
5051  Status API
8082  Honeypot
53    DNS
67    DHCP
ICMP  Ping
Internet through NAT
LAN-to-LAN routing
```

AP clients are blocked from:

```text
22             SSH
3001           AdGuard UI
5050           IDS Dashboard
8081           HTTP Test Service
21             FTP
40000-40100    FTP Passive Range
```

Admin-only access is based on:

```text
Admin IP: 192.168.1.11
```

---

## NAT and LAN-to-LAN Routing

AP clients reach the internet through NAT:

```text
10.10.10.0/24 → NetSentry → enp3s0 → ISP router → internet
```

LAN-to-LAN traffic is routed without NAT.

The ISP router contains a static route:

```text
Destination: 10.10.10.0
Mask:        255.255.255.0
Gateway:     192.168.1.19
```

This allows HOME LAN devices to reach AP LAN clients.

A NAT exception is used so AP-to-HOME traffic is not masqueraded:

```text
10.10.10.0/24 → 192.168.1.0/24 = no NAT
10.10.10.0/24 → internet = NAT
```

---

## Important Scripts

Current relevant scripts:

```text
scripts/start_ap.sh
scripts/stop_ap.sh
scripts/apply_gateway_firewall_test.sh
scripts/apply_gateway_firewall.sh
scripts/start_python_services.py
scripts/stop_python_services.py
scripts/run_snort.sh
scripts/snort_alert_watcher.py
```

Firewall scripts:

```text
apply_gateway_firewall_test.sh = test version with rollback
apply_gateway_firewall.sh      = final version without rollback
```

Old pre-gateway scripts should not be used as the main startup path until rebuilt:

```text
scripts/start_server.sh
scripts/apply_firewall.sh
netsentry-server.service
```

---

## Manual Startup Order

Current stable manual startup order:

```bash
cd ~/netsentry-gateway

ip -br addr show wlx200db0220b9a

sudo hostapd ~/netsentry-gateway/config/ap/hostapd-netsentry.conf
```

In another terminal:

```bash
sudo dnsmasq --no-daemon --conf-file=/home/gbx/netsentry-gateway/config/ap/dnsmasq-netsentry.conf
```

Then:

```bash
python3 scripts/start_python_services.py
./scripts/apply_gateway_firewall.sh
```

If AP scripts are used:

```bash
cd ~/netsentry-gateway

./scripts/start_ap.sh
python3 scripts/start_python_services.py
./scripts/apply_gateway_firewall.sh
```

---

## IDS Direction

The next major technical step is moving IDS monitoring into the new gateway architecture.

Traffic now enters NetSentry through:

```text
wlx200db0220b9a
```

So Snort should be tested on the AP-side interface first:

```bash
sudo snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i wlx200db0220b9a \
-A alert_fast
```

Planned IDS work:

```text
Update Snort interface to AP side
Update local.rules for 10.10.10.0/24 traffic
Keep alert watcher compatible with new traffic direction
Show AP client alerts clearly in the dashboard
Separate admin traffic from client traffic
```

---

## Documentation

Detailed progress docs:

```text
docs/netsentry-v1.5.md
docs/gateway-ap-routing-progress.md
docs/ap-gateway-progress.md
```

---

## Do Not Commit

Do not commit:

```text
Real Wi-Fi passwords
Real hostapd config
Runtime logs
Snort alert files
JSONL logs
PCAP files
Evidence files
PID files
```

Recommended `.gitignore` entries:

```text
config/ap/hostapd-netsentry.conf
config/ap/dnsmasq-netsentry.conf
logs/
snort/alerts/
evidence/
*.pcap
*.jsonl
*.log
*.pid
```

---

## Roadmap

Near-term roadmap:

```text
v1.5  AP gateway mode, NAT, firewall, routing
v1.6  Snort on AP-side traffic
v1.7  Dashboard improvements for AP client visibility
v1.8  Evidence capture and alert timeline
v2.0  Clean full startup automation
```

NetSentry v1.5 is the first version where the project behaves like a real network gateway rather than only a local monitoring host.
