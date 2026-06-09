# Current Hardware / Network State

## Working interfaces

wlx200db0220b9a
- USB Wi-Fi adapter
- Connected to home Wi-Fi
- Current SSH access path
- IP: 192.168.1.17

enp3s0
- Ethernet port
- Not used yet
- Future LAN side for NetSentry tests

wlx6070726769ad
- USB Wi-Fi adapter with antenna
- Detected by Debian
- Supports managed and monitor mode
- Does NOT support AP mode with current driver
- Not suitable as NetSentry AP

## Current decision

For now, NetSentry V0 will continue as a learning lab over Wi-Fi SSH.

Future full gateway testing should use:
- Wi-Fi adapter as WAN/client side
- Ethernet port as LAN side to one test client
or
- Ethernet LAN to old router/AP if available later
