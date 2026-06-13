# NetSentry v1.5 — AP Gateway Mode

## Version Status

NetSentry is officially at **v1.5**.

This version marks the transition from a host-based monitoring/security lab into a real routed gateway with an access point, firewall rules, NAT, DHCP, DNS forwarding through AdGuard, and LAN-to-LAN routing.

---

## v1.5 Main Achievement

NetSentry now operates between two networks:

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

NetSentry now acts as:

```text
Access Point
DHCP gateway
DNS gateway through AdGuard
NAT gateway
Firewall
Router between HOME LAN and AP LAN
Security monitoring platform
```

---

## Confirmed Working

The following components are confirmed working in v1.5:

```text
AP mode works on wlx200db0220b9a
AP clients connect successfully
AP clients receive DHCP leases from dnsmasq
AP clients use 10.10.10.1 as gateway
AP clients use 10.10.10.1 as DNS
AdGuard remains responsible for DNS on port 53
NetSentry portal is reachable from AP LAN
NetSentry portal is reachable from HOME LAN
AP clients have internet through NAT
Firewall blocks AP clients from admin-only services
Firewall allows public/client-facing services
Static route on ISP router allows HOME LAN to reach AP LAN
LAN-to-LAN routing works
```

---

## Access Paths

From the HOME / ISP LAN:

```text
http://192.168.1.19:5500
```

From the AP / Client LAN:

```text
http://10.10.10.1:5500
```

This works because the portal listens on all interfaces:

```text
0.0.0.0:5500
```

---

## AP Interface Stability Fix

The AP interface was losing its IP address after a few minutes.

The fix was:

```text
Make NetworkManager ignore wlx200db0220b9a
Disable Wi-Fi power saving
Create a systemd service to assign 10.10.10.1/24 after reboot
```

The AP interface service is:

```text
netsentry-ap-interface.service
```

Expected state:

```text
wlx200db0220b9a = 10.10.10.1/24
NetworkManager = unmanaged
Power save = off
```

---

## AP Services

AP mode uses:

```text
hostapd = Wi-Fi access point
dnsmasq = DHCP only
AdGuard = DNS filtering/resolution
```

dnsmasq is configured with:

```text
port=0
```

This is important because dnsmasq must not fight AdGuard for port 53.

---

## Firewall Model

The v1.5 firewall separates client-facing services from admin-only services.

Allowed from AP clients:

```text
5500 = NetSentry Portal
5051 = Status API
8082 = Honeypot
53   = DNS
67   = DHCP
ICMP = ping
Internet through NAT
LAN-to-LAN routing
```

Blocked from AP clients:

```text
22   = SSH
3001 = AdGuard UI
5050 = IDS dashboard
8081 = HTTP test service
21   = FTP
40000-40100 = FTP passive range
```

Admin-only access is based on:

```text
Admin IP: 192.168.1.11
```

---

## NAT and Routing

AP clients reach the internet using NAT:

```text
10.10.10.0/24 → NetSentry → enp3s0 → ISP router → internet
```

LAN-to-LAN traffic does not use NAT.

A NAT exception is used for AP-to-HOME traffic:

```text
10.10.10.0/24 → 192.168.1.0/24 = no NAT
10.10.10.0/24 → internet = NAT
```

The ISP router has a static route:

```text
Destination: 10.10.10.0
Mask:        255.255.255.0
Gateway:     192.168.1.19
```

This allows HOME LAN devices to reach AP LAN clients.

---

## Important Scripts

Current important scripts:

```text
scripts/apply_gateway_firewall_test.sh
scripts/apply_gateway_firewall.sh
scripts/start_python_services.py
scripts/stop_python_services.py
scripts/start_ap.sh
scripts/stop_ap.sh
```

The test firewall script keeps rollback protection.

The final firewall script should not include rollback.

---

## Do Not Use Yet

These old scripts/services should not be used as the main startup path until rebuilt for v1.5:

```text
scripts/start_server.sh
scripts/apply_firewall.sh
netsentry-server.service
```

They belong to the older pre-gateway architecture.

---

## v1.5 Manual Startup Order

Current stable manual order:

```bash
cd ~/netsentry-gateway

ip -br addr show wlx200db0220b9a

sudo hostapd ~/netsentry-gateway/config/ap/hostapd-netsentry.conf

sudo dnsmasq --no-daemon --conf-file=/home/gbx/netsentry-gateway/config/ap/dnsmasq-netsentry.conf

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

## Security Notes

Do not commit:

```text
Real Wi-Fi passwords
Real hostapd config
Real dnsmasq config if local-only
Runtime logs
Snort alerts
JSONL logs
PCAP files
Evidence files
PID files
```

Safe example configs should be committed instead.

---

## Next Version Direction

The next major focus after v1.5 is IDS integration for the gateway architecture.

Traffic now enters through:

```text
wlx200db0220b9a
```

So Snort should be moved/tested on the AP-side interface first.

Planned v1.6 direction:

```text
Snort on AP-side traffic
Update local.rules for 10.10.10.0/24 clients
Update run_snort.sh for gateway mode
Connect Snort alerts to watcher
Display AP client alerts in dashboard
Separate admin traffic from AP client traffic
Prepare clean startup automation after manual layers are stable
```
