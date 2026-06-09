# iptables Host Firewall Test

## Debian NetSentry IP
192.168.1.17

## Admin PC IP
192.168.1.11

## Firewall policy
- Allow SSH only from admin PC.
- Allow AdGuard web UI only from admin PC.
- Allow DNS from LAN.
- Allow ping from LAN.
- Log and drop everything else.

## Confirmed rules
1. Loopback allowed.
2. Established/related traffic allowed.
3. SSH allowed from 192.168.1.11 only.
4. SSH dropped from all other sources.
5. AdGuard UI port 3001 allowed from 192.168.1.11 only.
6. AdGuard UI port 3001 dropped from all other sources.
7. UDP DNS port 53 allowed from 192.168.1.0/24.
8. TCP DNS port 53 allowed from 192.168.1.0/24.
9. ICMP allowed from 192.168.1.0/24.
10. Remaining traffic logged with prefix NETSENTRY_INPUT_DROP.
11. Remaining traffic dropped.

## Test results
- SSH from admin PC works.
- SSH from non-admin device fails.
- AdGuard UI from admin PC works.
- AdGuard UI from non-admin device fails.
- DNS queries from LAN work.
- Custom blocked domain still blocked by AdGuard.
- Ping from LAN works.
- Firewall logs show NETSENTRY_INPUT_DROP entries.

## Interpretation
The Debian machine now has a basic host firewall protecting exposed services. This is not yet gateway firewalling, but it successfully protects services running on the NetSentry V0 lab machine.
