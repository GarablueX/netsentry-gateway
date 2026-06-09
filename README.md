# NetSentry Gateway

NetSentry is a Linux-based home network security gateway project.

## Current Stage

V0 learning lab.

The Debian machine is currently running as a protected LAN host, not yet as a full gateway.

## Current IPs

- Debian NetSentry: `192.168.1.17`
- Admin PC: `192.168.1.11`
- LAN: `192.168.1.0/24`

## Completed

- Debian installation
- SSH access from admin PC
- AdGuard Home DNS filtering
- Custom DNS blocking test
- iptables host firewall
- Firewall logging with `NETSENTRY_INPUT_DROP`
- tcpdump packet capture and `.pcap` validation

## Current Services

- SSH: `22/tcp`
- DNS: `53/tcp`, `53/udp`
- AdGuard UI: `3001/tcp`

## Current Firewall Policy

- SSH allowed only from admin PC
- AdGuard UI allowed only from admin PC
- DNS allowed from LAN
- ICMP allowed from LAN
- Everything else logged and dropped

## Next Phase

Snort 3 IDS validation.
