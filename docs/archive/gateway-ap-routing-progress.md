# NetSentry AP / Gateway / Routing Progress

## Current Goal

NetSentry is now moving from a simple monitoring host into a real gateway device.

The target architecture is:

```text
HOME / ISP LAN:
  Interface: enp3s0
  NetSentry IP: 192.168.1.19/24
  Home LAN: 192.168.1.0/24
  Admin PC: 192.168.1.11

AP / Client LAN:
  Interface: wlx200db0220b9a
  NetSentry AP IP: 10.10.10.1/24
  AP client LAN: 10.10.10.0/24
  SSID: NetSentry-Test
```

NetSentry now acts as the middle router/firewall between the home LAN and the AP client LAN.

---

## 1. AP Interface Static IP

The AP interface is:

```text
wlx200db0220b9a
```

It was configured to keep this static address even after reboot:

```text
10.10.10.1/24
```

This is important because AP clients use NetSentry as their default gateway.

A systemd service was created for the AP interface:

```text
netsentry-ap-interface.service
```

Its job is only to:

```text
assign 10.10.10.1/24 to wlx200db0220b9a
bring the interface up
disable Wi-Fi power saving
```

Check commands:

```bash
ip -br addr show wlx200db0220b9a
nmcli dev status | grep wlx
iw dev wlx200db0220b9a get power_save
sudo systemctl status netsentry-ap-interface.service --no-pager -l
```

Expected:

```text
wlx200db0220b9a has 10.10.10.1/24
NetworkManager shows it as unmanaged
Power save is off
netsentry-ap-interface.service is active/exited
```

---

## 2. NetworkManager Fix

The AP interface was losing its IP after a few minutes. The fix was to stop NetworkManager from managing it.

Permanent config:

```text
/etc/NetworkManager/conf.d/netsentry-ap-unmanaged.conf
```

Content:

```ini
[keyfile]
unmanaged-devices=interface-name:wlx200db0220b9a
```

This prevents NetworkManager from resetting the AP interface.

Power saving was also disabled:

```bash
sudo iw dev wlx200db0220b9a set power_save off
```

---

## 3. AP Services

Two services are used for AP mode:

```text
hostapd = creates the Wi-Fi access point
dnsmasq = gives AP clients DHCP addresses
```

Real local configs:

```text
config/ap/hostapd-netsentry.conf
config/ap/dnsmasq-netsentry.conf
```

The real `hostapd` config contains the Wi-Fi password and must not be committed.

The safe GitHub example should be:

```text
config/ap/hostapd-netsentry.example.conf
```

The dnsmasq config uses DHCP only:

```ini
interface=wlx200db0220b9a
bind-interfaces

port=0

dhcp-range=10.10.10.50,10.10.10.150,255.255.255.0,12h
dhcp-option=3,10.10.10.1
dhcp-option=6,10.10.10.1

log-dhcp
```

Important:

```text
port=0 means dnsmasq does not run DNS.
AdGuard keeps DNS on port 53.
```

Manual AP start commands:

```bash
sudo hostapd ~/netsentry-gateway/config/ap/hostapd-netsentry.conf
sudo dnsmasq --no-daemon --conf-file=/home/gbx/netsentry-gateway/config/ap/dnsmasq-netsentry.conf
```

Manual AP stop commands:

```bash
sudo pkill hostapd
sudo pkill dnsmasq
```

---

## 4. Dual Access to NetSentry Services

NetSentry can now be reached from two networks.

From the home/ISP LAN:

```text
http://192.168.1.19:5500
```

From the AP/client LAN:

```text
http://10.10.10.1:5500
```

This works because the portal listens on:

```text
0.0.0.0:5500
```

If a service only listens on `192.168.1.19`, AP clients cannot access it through `10.10.10.1`.

Check listening ports:

```bash
sudo ss -ltnp | grep ':5500'
```

Good result:

```text
0.0.0.0:5500
```

---

## 5. Firewall Reset and Old Rules

Old iptables rules were being restored after reboot. Those automatic old rules were disabled so the new gateway firewall could be built cleanly.

Current clean baseline:

```text
old NetSentry firewall auto-loading disabled
iptables starts mostly open/empty
AP interface service remains enabled
```

Important service to keep enabled:

```text
netsentry-ap-interface.service
```

Important old services/scripts to avoid for now:

```text
netsentry-server.service
scripts/apply_firewall.sh
scripts/start_server.sh
```

The new firewall work is now based on:

```text
scripts/apply_gateway_firewall_test.sh
scripts/apply_gateway_firewall.sh
```

---

## 6. Gateway NAT

AP clients can reach the internet through NetSentry.

Traffic path:

```text
AP client 10.10.10.x
→ NetSentry 10.10.10.1
→ enp3s0 / 192.168.1.19
→ ISP router
→ internet
```

IPv4 forwarding must be enabled:

```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

Check:

```bash
cat /proc/sys/net/ipv4/ip_forward
```

Expected:

```text
1
```

NAT rule:

```bash
sudo iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o enp3s0 -j MASQUERADE
```

Forward rules:

```bash
sudo iptables -A FORWARD -i wlx200db0220b9a -o enp3s0 -s 10.10.10.0/24 -j ACCEPT
sudo iptables -A FORWARD -i enp3s0 -o wlx200db0220b9a -d 10.10.10.0/24 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
```

Client tests:

```text
ping 10.10.10.1
ping 8.8.8.8
ping google.com
```

Meaning:

```text
10.10.10.1 works = AP LAN works
8.8.8.8 works = NAT/routing works
google.com works = DNS works
```

---

## 7. Gateway Firewall

The firewall now separates public/client services from admin-only services.

Allowed from AP clients:

```text
5500 = NetSentry Portal
5051 = Status API
8082 = Honeypot
53   = DNS / AdGuard
67   = DHCP
ICMP = ping
internet access through NAT
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

Allowed from admin PC:

```text
Admin IP: 192.168.1.11
Allowed admin services:
  22
  3001
  5050
  5051
  8081
  21
  40000-40100
```

The test firewall script includes rollback:

```text
scripts/apply_gateway_firewall_test.sh
```

The final firewall script should not include rollback:

```text
scripts/apply_gateway_firewall.sh
```

Rollback is useful while testing, but should not remain in the final script because it reopens the firewall after the timer expires.

---

## 8. Important Firewall Lesson

The firewall script must flush old rules before adding new rules.

Without flushing first, old ACCEPT or DROP rules may stay above the new rules and cause confusing behavior.

Correct beginning behavior:

```bash
sudo iptables -P INPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
sudo iptables -P OUTPUT ACCEPT

sudo iptables -F
sudo iptables -t nat -F
sudo iptables -t mangle -F
sudo iptables -t raw -F

sudo iptables -X
sudo iptables -t nat -X
sudo iptables -t mangle -X
sudo iptables -t raw -X
```

Also, the INPUT chain must include this near the top:

```bash
sudo iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
```

Reason:

```text
NetSentry itself needs to receive replies for outbound traffic.
Without this, commands like apt update may hang.
```

---

## 9. Debian apt update Issue

`apt update` appeared stuck after applying firewall rules.

Likely causes:

```text
firewall blocking reply traffic
IPv6 causing apt delay
```

Useful commands:

```bash
sudo iptables -I INPUT 1 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
sudo iptables -I INPUT 2 -m conntrack --ctstate INVALID -j DROP
```

IPv4-only apt test:

```bash
sudo apt -o Acquire::ForceIPv4=true update
```

Make IPv4 permanent for apt if needed:

```bash
echo 'Acquire::ForceIPv4 "true";' | sudo tee /etc/apt/apt.conf.d/99force-ipv4
```

---

## 10. Admin PC Ping Issue

Debian could not ping the admin PC.

The reason was not necessarily Debian routing. The likely reason was the admin PC firewall blocking ICMP echo requests.

Debug command on Debian:

```bash
sudo tcpdump -ni enp3s0 icmp and host 192.168.1.11
```

If Debian sends ICMP echo requests but receives no echo replies, the admin PC firewall is blocking ping.

On Windows admin PC, allow ICMPv4 ping:

```powershell
netsh advfirewall firewall add rule name="Allow ICMPv4 Ping" protocol=icmpv4:8,any dir=in action=allow
```

---

## 11. LAN-to-LAN Routing

The goal was to make both LANs talk to each other:

```text
192.168.1.0/24 ↔ 10.10.10.0/24
```

This is routing, not VLAN tagging.

The ISP router was given a static route:

```text
Destination: 10.10.10.0
Mask:        255.255.255.0
Gateway:     192.168.1.19
```

Meaning:

```text
If the home LAN wants to reach 10.10.10.0/24,
send that traffic to NetSentry at 192.168.1.19.
```

Debian/NetSentry then forwards it to:

```text
wlx200db0220b9a / 10.10.10.1
```

---

## 12. NAT Exception for LAN-to-LAN

AP clients should be NATed when going to the internet, but not when talking to the home LAN.

Correct NAT order:

```bash
sudo iptables -t nat -A POSTROUTING -s "$AP_NET" -d "$HOME_LAN" -j RETURN
sudo iptables -t nat -A POSTROUTING -s "$AP_NET" -o "$WAN_I" -j MASQUERADE
```

Expected NAT table order:

```text
1 RETURN       10.10.10.0/24 -> 192.168.1.0/24
2 MASQUERADE   10.10.10.0/24 -> anywhere out enp3s0
```

Meaning:

```text
AP → HOME LAN = no NAT
AP → internet = NAT
```

LAN-to-LAN FORWARD rules:

```bash
sudo iptables -A FORWARD -i "$WAN_I" -o "$AP_I" -s "$HOME_LAN" -d "$AP_NET" -j ACCEPT
sudo iptables -A FORWARD -i "$AP_I" -o "$WAN_I" -s "$AP_NET" -d "$HOME_LAN" -j ACCEPT
```

---

## 13. Confirmed Working

Confirmed working today:

```text
AP interface keeps static 10.10.10.1/24 after reboot
NetworkManager no longer resets AP interface
Power saving disabled on AP interface
hostapd AP works
dnsmasq DHCP works
AP clients get 10.10.10.x addresses
AP clients reach NetSentry at 10.10.10.1
AP clients have internet through NAT
Firewall blocks admin-only services from AP clients
Firewall allows selected public/client services
ISP router static route allows home LAN to reach AP LAN
LAN-to-LAN routing works
```

---

## 14. Current Startup Order

Current manual working order:

```bash
cd ~/netsentry-gateway

# AP interface should already be static after reboot
ip -br addr show wlx200db0220b9a

# Start AP
sudo hostapd ~/netsentry-gateway/config/ap/hostapd-netsentry.conf

# Start DHCP in another terminal
sudo dnsmasq --no-daemon --conf-file=/home/gbx/netsentry-gateway/config/ap/dnsmasq-netsentry.conf

# Start NetSentry Python services
python3 scripts/start_python_services.py

# Apply firewall/NAT/routing
./scripts/apply_gateway_firewall.sh
```

If using AP scripts:

```bash
cd ~/netsentry-gateway
./scripts/start_ap.sh
python3 scripts/start_python_services.py
./scripts/apply_gateway_firewall.sh
```

---

## 15. Next Step

Next major step:

```text
Snort on the AP side
```

Traffic to monitor now enters through:

```text
wlx200db0220b9a
```

So Snort should be tested on:

```bash
sudo snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i wlx200db0220b9a \
-A alert_fast
```

After manual Snort testing works, update:

```text
scripts/run_snort.sh
scripts/snort_alert_watcher.py
dashboard alert flow
```

The new IDS focus should be AP/client traffic on `10.10.10.0/24`.
