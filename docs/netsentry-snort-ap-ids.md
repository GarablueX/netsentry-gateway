# NetSentry AP-Side Snort IDS Progress

## Purpose

This document records the current AP-side Snort IDS work for NetSentry.

The AP-side Snort sensor monitors traffic on:

```text
wlx200db0220b9a
```

This interface represents the NetSentry Wi-Fi/client side. It sees AP client traffic before NAT, which means alerts can still identify real client IP addresses from the `10.10.10.0/24` network.

## Current Snort files

Current AP rules file:

```text
snort/rules/local_ap.rules
```

Current Snort configuration:

```text
/usr/local/etc/snort/snort.lua
```

Repository copy of Snort configuration:

```text
config/snort/snort.lua
```

## Important network variables

The Snort rules use NetSentry variables instead of hardcoded IPs:

```text
$AP_LAN              10.10.10.0/24
$HOME_LAN            192.168.1.0/24
$ADMIN_IP            192.168.1.11
$AP_GATEWAY          10.10.10.1
$HOME_GATEWAY        192.168.1.19
$NETSENTRY_GATEWAY   [10.10.10.1,192.168.1.19]
```

These variables allow the rules to stay readable and easier to maintain.

## Snort latency fix

Snort alerting was delayed because packets/events were being batched before alert output.

The working fast configuration is:

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

`daq.batch_size = 1` makes Snort process packets with minimal batching delay.

`event_queue.log = 16` allows multiple matching alerts per packet. This is important because `log = 1` caused some alerts to be hidden when one packet matched multiple rules.

## Current working Snort command

The tested AP-side command is:

```bash
sudo stdbuf -oL -eL snort \
  -c /usr/local/etc/snort/snort.lua \
  -R /home/gbx/netsentry-gateway/snort/rules/local_ap.rules \
  -i wlx200db0220b9a \
  -A alert_fast \
  -k none \
| stdbuf -oL tee -a /home/gbx/netsentry-gateway/snort/alerts/alert_fast.txt
```

Alerts are written to:

```text
snort/alerts/alert_fast.txt
```

Runtime alert files are not committed to Git.

## Rule categories currently covered

The AP-side Snort rules currently focus on high-value network IDS detections:

```text
ICMP ping from non-admin clients
Oversized ICMP payloads
ICMP sweep behavior
SSH connection attempts
SSH repeated connection attempts
AdGuard UI access attempts
Old dashboard/API/test service probing
TCP SYN burst detection
TCP NULL scan detection
TCP FIN scan detection
TCP XMAS scan detection
TCP SYN/FIN scan detection
TCP SYN flood detection
UDP flood detection
TCP reset flood detection
DNS bypass attempts from AP clients
FTP access attempts
FTP anonymous login attempts
AP client scanning behavior
AP client probing sensitive gateway ports
SMB/RDP/Telnet style access attempts
```

## Testing status

The following tests were confirmed working:

```text
Basic TCP/ICMP rules
Snort variables
Live capture on wlx200db0220b9a
Fast alert output after DAQ/event_queue tuning
detection_filter rules
AP client rules
Crafted scan rules using Ubuntu VM tools
```

PowerShell can test normal TCP, UDP, ICMP, DNS, RDP, SMB, FTP, and HTTP behavior.

Ubuntu VM is used for crafted scan testing with tools such as:

```text
nmap
hping3
dig
curl
netcat
```

## HTTPS limitation

Snort can detect HTTPS connections to the gateway, but it cannot inspect encrypted HTTPS paths.

Snort can detect:

```text
client IP
server IP
TCP port 443
TLS connection behavior
```

Snort cannot detect inside HTTPS:

```text
/admin/login
/admin/dashboard
HTTP headers
POST body
username/password fields
User-Agent strings
```

Therefore, NetSentry should use:

```text
Snort       for network-level IDS
Nginx logs  for HTTPS path and request detection
Flask logs  for admin/login/authentication detection
```

## Current conclusion

AP-side Snort is now functional and useful for network IDS detection.

The next step is not to add random rules, but to stabilize the system around the working rule set, add service automation, and connect alerts to the NetSentry dashboard.
