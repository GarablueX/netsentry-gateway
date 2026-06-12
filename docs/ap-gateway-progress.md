# NetSentry AP / Gateway Progress

## Current Milestone

NetSentry AP mode is now working.

The project has moved from a host-facing IDS/security lab toward a real gateway architecture.

Current working AP-side architecture:

```text
Upstream / ISP LAN:
  Interface: enp3s0
  NetSentry IP: 192.168.1.19/24

AP / Client LAN:
  Interface: wlx200db0220b9a
  NetSentry AP IP: 10.10.10.1/24
  Client subnet: 10.10.10.0/24
  SSID: NetSentry-Test
Access works from both sides:

From ISP/home LAN:
  http://192.168.1.19:5500

From AP/client LAN:
  http://10.10.10.1:5500
Confirmed Working
AP mode works on wlx200db0220b9a
SSID is visible
Clients can connect to NetSentry-Test
AP clients receive 10.10.10.x addresses through dnsmasq DHCP
NetSentry is reachable from AP clients at 10.10.10.1
Portal is reachable from AP clients at http://10.10.10.1:5500
Honeypot can be reached from AP clients
IP forwarding and NAT were tested successfully
AP clients can reach the internet through enp3s0




Important Networking Concept

NetSentry now has two network sides:

enp3s0            = upstream / ISP LAN side
wlx200db0220b9a   = AP / client LAN side

Traffic flow for AP clients:

AP client 10.10.10.x
→ NetSentry 10.10.10.1
→ NAT out through enp3s0
→ ISP router
→ internet



