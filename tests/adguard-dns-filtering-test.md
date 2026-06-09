# AdGuard DNS Filtering Test

## Target
Debian NetSentry V0 machine

## Debian IP
192.168.1.17

## Service tested
AdGuard Home DNS filtering

## Custom blocked domain
tiktok.com

## Result
TikTok DNS queries were blocked by AdGuard custom filtering rules.

## Evidence
AdGuard dashboard showed:
- DNS queries received
- Blocked queries
- Client IP: 192.168.1.11
- Request: tiktok.com
- Response: Blocked by custom filtering rules

## Port scan after AdGuard install
Open ports:
- 22/tcp SSH
- 53/tcp DNS
- 3001/tcp AdGuard web UI

## Interpretation
AdGuard DNS filtering is working. The Debian machine is now acting as a DNS filtering server for the test client. The system attack surface increased after installing AdGuard, so later firewall rules should restrict AdGuard web UI access to the admin PC only.


