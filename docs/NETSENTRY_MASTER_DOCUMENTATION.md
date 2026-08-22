# NetSentry Gateway — Master Documentation

**Version:** v2.6.0 — Stable

**Status:** Active homelab deployment

**Type:** Personal / student cybersecurity project

This is the authoritative technical reference for NetSentry. If the top-level `README.md`, older files under `docs/`, or code comments disagree with this document, verify the active implementation and update the stale documentation.

---

## Table of Contents

1. [Project Summary](#1-project-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Network Layout](#3-network-layout)
4. [Component Reference](#4-component-reference)
5. [Firewall / NAT](#5-firewall--nat)
6. [IDS: Suricata](#6-ids-suricata)
7. [SIEM: Wazuh](#7-siem-wazuh)
8. [Web Dashboard](#8-web-dashboard)
9. [Systemd Services](#9-systemd-services)
10. [Remote Administration: Tailscale](#10-remote-administration-tailscale)
11. [Secrets and Security Policy](#11-secrets-and-security-policy)
12. [Repository Structure](#12-repository-structure)
13. [Version History](#13-version-history)
14. [Testing and Validation](#14-testing-and-validation)
15. [Known Issues](#15-known-issues)
16. [Unfinished / Planned Work](#16-unfinished--planned-work)

---

## 1. Project Summary

NetSentry converts a Debian machine into a small security gateway between a home network and a Wi-Fi client subnet. It combines:

- Routing, DHCP, and DNS filtering for the AP subnet
- Stateful firewall, forwarding, and NAT through native nftables
- Ansible-managed firewall deployment and persistent IPv4 forwarding
- Network intrusion detection with Suricata
- Security event correlation and investigation with Wazuh
- A read-only Flask and Nginx operations dashboard
- Private remote administration through Tailscale

NetSentry is not an enterprise product. It demonstrates practical blue-team infrastructure in a continuously running homelab.

---

## 2. Architecture Overview

```text
AP Client
   |
   | Wi-Fi / 10.10.10.0/24
   v
NetSentry AP Interface (wlx200db0220b9a / 10.10.10.1)
   |
   |-- Suricata IDS observes AP-side traffic
   |
   | native nftables firewall / routing / NAT
   v
NetSentry HOME/WAN Interface (enp3s0 / 192.168.1.19)
   |
   v
Home Router / Internet
```

Firewall configuration pipeline:

```text
config/vars.yml
   |
   v
templates/firewall.nft.j2
   |
   v
playbooks/firewall.yml -- validates with nft --check
   |
   v
/etc/nftables.conf -> nftables.service -> table inet netsentry
```

Dashboard architecture:

```text
Browser -> Nginx :80/:443 -> Flask 127.0.0.1:5000   (gateway operations)
Browser -> Nginx :8443     -> Wazuh dashboard        (SIEM investigation)
```

IDS/SIEM data pipeline:

```text
Suricata
   |
   v
/var/log/suricata/eve.json
   |
   v
Filebeat -> Wazuh manager -> Wazuh indexer -> Wazuh dashboard
```

Firewall log correlation pipeline:

```text
nftables rate-limited log rules
   |
   v
journald / kernel log
   |
   v
Wazuh monitoring and correlation
```

Design principle: **NetSentry handles gateway operations; Wazuh handles security investigation.** The retired built-in IDS dashboard was removed in v2.2 to avoid duplicating Wazuh.

---

## 3. Network Layout

The values below come from the current `config/vars.yml`. Other historical files may contain older values and must not be assumed to be synchronized.

### HOME / Upstream Side

| Field | Value |
| --- | --- |
| Interface | `enp3s0` |
| Network | `192.168.1.0/24` |
| NetSentry IP | `192.168.1.19` |
| nftables admin IP | `192.168.1.50` |

### AP / Client Side

| Field | Value |
| --- | --- |
| Interface | `wlx200db0220b9a` |
| Network | `10.10.10.0/24` |
| Gateway IP | `10.10.10.1` |
| SSID | `NetSentry_AP` |
| DHCP range | `10.10.10.50`–`10.10.10.150` |

### Return Path

The home router requires a route for `10.10.10.0/24` through NetSentry (`192.168.1.19`) if home hosts must initiate connections to AP clients. The nftables rules do not masquerade AP-to-home traffic, preserving AP source addresses. AP-to-internet traffic is masqueraded through the WAN interface.

---

## 4. Component Reference

| Component | Role |
| --- | --- |
| Debian | Base operating system |
| hostapd | Wi-Fi access point |
| dnsmasq | DHCP for AP clients |
| AdGuard Home | DNS filtering and resolution |
| nftables | Native firewall, forwarding, logging, and NAT |
| Ansible | Firewall template rendering, validation, installation, and service setup |
| Nginx | TLS termination and reverse proxy |
| Flask | Read-only gateway operations dashboard |
| Suricata | Network intrusion detection |
| Wazuh | SIEM manager, indexer, dashboard, and investigation UI |
| Filebeat | Ships Suricata and other events to Wazuh |
| Tailscale | Private remote administration overlay |
| systemd | Service startup and supervision |

---

## 5. Firewall / NAT

### Active implementation

| Path | Purpose |
| --- | --- |
| `config/vars.yml` | Interface, address, subnet, and port variables |
| `templates/firewall.nft.j2` | Native nftables Jinja template |
| `playbooks/firewall.yml` | Local privileged deployment playbook |
| `/etc/nftables.conf` | Rendered system configuration |
| `nftables.service` | Applies the ruleset and loads it after reboot |

`scripts/apply_firewall.sh` and the custom `netsentry-firewall.service` are remnants of the retired iptables implementation, not the current deployment path.

### Prerequisites

- Debian or Ubuntu with systemd and `apt`
- Ansible
- `ansible.posix` collection for `ansible.posix.sysctl`
- Privilege escalation through `sudo`
- `/usr/sbin/nft`

Install the required collection when needed:

```bash
ansible-galaxy collection install ansible.posix
```

### Deployment

Review `config/vars.yml`, then run from the repository root:

```bash
ansible-playbook playbooks/firewall.yml --check --diff --ask-become-pass
ansible-playbook playbooks/firewall.yml --ask-become-pass
```

The playbook:

1. Targets `localhost` with `connection: local` and `become: true`.
2. Installs the `nftables` package.
3. Sets `net.ipv4.ip_forward=1` and persists it in `/etc/sysctl.d/99-netsentry.conf`.
4. Renders `templates/firewall.nft.j2` to an Ansible temporary file.
5. Runs `/usr/sbin/nft --check --file <temporary-file>` before replacing `/etc/nftables.conf`.
6. Installs the configuration as `root:root` with mode `0644`.
7. Enables and starts `nftables.service`.
8. Reloads nftables through a handler when the rendered template changes.

Syntax validation protects the live configuration from an invalid rendered file. It does not prove that the policy, interface names, or management addresses are safe for the target host.

### Active ruleset

The template creates `table inet netsentry` with three chains.

#### Input

The `input` chain has policy `drop` and permits:

- Established and related connections
- Loopback traffic
- ICMP from the home and AP networks
- TCP ports `22`, `80`, `443`, `3001`, and `8443` from `network.admin_ip`
- TCP ports `22`, `80`, and `443` from `tailscale0` addresses in `100.64.0.0/10`
- TCP and UDP DNS on port `53` from the AP network
- DHCP traffic on the AP interface from UDP source port `68` to destination port `67`
- HTTP and HTTPS from the home and AP networks

Invalid state is dropped. Remaining input is rate-limited and logged with the prefix `nftables input drop:` before the chain policy drops it.

#### Forwarding

The `forward` chain has policy `drop` and permits:

- Home-to-AP traffic on the configured WAN-to-AP interface direction
- AP-to-home traffic on the configured AP-to-WAN direction
- AP traffic leaving through the WAN interface
- Established and related return traffic from WAN to AP when addressed to the AP network

Other forwarded traffic is rate-limited and logged with `NETSENTRY_FW_FORWARD_DROP` before the chain policy drops it.

> The current AP-to-home rule permits AP clients to initiate connections to the entire home subnet. Remove or constrain it if AP isolation is required.

#### NAT

The `postrouting` chain:

- Returns without NAT for AP traffic destined for the home LAN
- Masquerades AP traffic leaving through the WAN interface

### Tailscale and full-ruleset flushing

The template begins with:

```nft
flush ruleset
```

This clears every nftables table, not only `table inet netsentry`. It can remove Tailscale compatibility tables and rules owned by containers or other firewall managers. The current playbook does not restart those services.

After applying the firewall, restart Tailscale so it recreates its `ts-*` rules:

```bash
sudo systemctl restart tailscaled
```

The resulting ownership is:

```text
NetSentry -> native table inet netsentry
Tailscale -> iptables-nft compatibility tables containing ts-* chains
```

The `ts-*` chains belong to Tailscale and are not evidence that the old NetSentry iptables firewall returned.

### Post-deployment checks

```bash
sudo systemctl is-enabled nftables
sudo systemctl status nftables --no-pager
sudo nft list table inet netsentry
sudo nft list ruleset
sudo sysctl net.ipv4.ip_forward
sudo iptables-save
sudo ip6tables-save
```

Expected NetSentry state:

- `nftables.service` is enabled and active.
- `table inet netsentry` contains `input`, `forward`, and `postrouting`.
- Input and forwarding policies are `drop`.
- IPv4 forwarding equals `1`.
- No retired NetSentry iptables chains are present.
- Any `ts-*` chains are Tailscale-owned compatibility rules.

Reboot testing has confirmed that nftables and IPv4 forwarding persist, AP forwarding/NAT continue to work, and Tailscale recreates its own rules.

---

## 6. IDS: Suricata

**Active rules file:** `suricata/rules/local.rules`

**System config used by test scripts:** `/etc/suricata/suricata.yaml`

**Repository config currently present:** `config/suricata/suriata.yml`

The tracked repository filename differs from older documentation and from the system path used by the scripts. Verify that the deployed `/etc/suricata/suricata.yaml` contains the intended variables and EVE output configuration.

### Current rule categories

```text
ICMP anomaly and sweep detection
SSH brute-force and legacy protocol detection
AdGuard and admin-path access attempts
TCP scan and flood patterns
UDP and TCP RST floods
DNS bypass detection
FTP detection test cases
AP client horizontal scanning
SMB, RDP, and Telnet access attempts
Admin-host and Wazuh service access attempts
```

### Rule syntax validation

```bash
sudo suricata -T \
  -c /etc/suricata/suricata.yaml \
  -S /home/gbx/netsentry-gateway/suricata/rules/local.rules \
  -i wlx200db0220b9a \
  -l /tmp/suricata-rule-test
```

Adjust the absolute rules path when the repository is checked out elsewhere.

### Automated PCAP validation

There are 27 versioned fixtures following this layout:

```text
tests/cases/<SID>/<SID>.pcap
```

Run all cases or one selected SID:

```bash
python3 tests/cases/validate.py
python3 tests/cases/validate.py 10000001
```

For each case, the validator runs:

```bash
sudo suricata \
  -r tests/cases/<SID>/<SID>.pcap \
  -S /home/gbx/netsentry-gateway/suricata/rules/local.rules \
  -c /etc/suricata/suricata.yaml \
  -k none \
  -l <fresh-temporary-directory>
```

It parses `eve.json` as newline-delimited JSON. A case passes only when:

1. `alert.signature_id` contains the numeric SID represented by the directory name at least once.
2. No alert with a different integer SID appears.

Multiple alerts for the expected SID are allowed. Non-alert EVE events are ignored. The temporary directory is deleted after each case, including failures.

The validator does not compare `eve.json` against a checked-in baseline and does not read the `expected.json` files currently present in case directories.

Exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | Every selected case passed |
| `1` | At least one SID/EVE semantic validation failure and no execution error |
| `2` | Missing configuration, no matching cases, Suricata failure, or missing EVE output |

An execution error takes precedence over semantic failures in the final exit code.

### Supporting PCAP utilities

Inspect all captures or one selected case with tcpdump:

```bash
python3 tests/cases/run_pcaps.py
python3 tests/cases/run_pcaps.py 10000001
```

This executes `sudo tcpdump -r <pcap>` and returns `0` only when every selected invocation succeeds. It checks capture readability, not Suricata alert correctness.

Generate Suricata output directly inside each case directory:

```bash
python3 tests/cases/run_suricata.py
python3 tests/cases/run_suricata.py 10000001
```

`run_suricata.py` does not parse or validate EVE. It writes output beside the PCAP, and configured append-mode logs may retain output from earlier runs. Use `validate.py` for isolated correctness testing.

### Why Suricata replaced Snort

Snort was the original IDS. Running Snort and Suricata together produced duplicate alerts and noisier investigations. Snort and the built-in IDS dashboard were retired in v2.2; Wazuh is now the investigation interface.

---

## 7. SIEM: Wazuh

Wazuh ingests and investigates:

- Suricata `eve.json` alerts
- nftables drop logs, including `NETSENTRY_FW_FORWARD_DROP`
- Nginx access and error logs
- Authentication logs
- System, journald, and kernel events

**Wazuh dashboard:** `https://192.168.1.19:8443/`

Repository reference configurations:

```text
config/wazuh/ossec.conf.netsentry-reference
config/wazuh/local_rules.xml.netsentry-reference
config/wazuh/local_suricata_sids.xml
config/wazuh/jvm.options.netsentry-reference
```

### Performance tuning

The deployment runs on constrained homelab hardware. Wazuh indexer heap was reduced, vulnerability detection and startup syscheck were disabled, scan frequency was reduced, and unused container services were disabled.

Suricata thresholds are tuned to produce meaningful behavioral alerts rather than one alert per packet.

---

## 8. Web Dashboard

**Backend:** `app/netsentry_app.py`

**Frontend:** `app/templates/`, `app/static/`

**Reverse proxy:** `config/nginx/netsentry.conf`

The dashboard is read-only. It reports gateway state but does not apply firewall rules, restart services, or trigger captures. Privileged client actions remain planned as a separate component.

### Main routes

Public:

```text
/  /about  /features  /architecture  /status  /docs  /hardware  /contact
```

Authenticated admin:

```text
/admin/dashboard  /admin/clients  /admin/dns
/admin/firewall   /admin/network
```

Internal dashboard API:

```text
/api/status
/api/clients
/api/dns/stats
/api/network/interfaces
/api/network/routes
/api/firewall/rules
```

Removed in v2.2: `/admin/ids`, `/admin/logs`, `/api/ids/alerts`, and `/api/logs`.

### Authentication

- Supports a password hash or constant-time plaintext environment comparison
- Uses CSRF tokens generated with `secrets.token_urlsafe`
- Uses `HttpOnly` and `SameSite=Strict` session cookies
- Applies configurable login failure lockout and session timeout
- Loads sensitive values through `/etc/netsentry/netsentry-web.env`

---

## 9. Systemd Services

### Active service set

```text
ssh.service
nginx.service
netsentry-web.service
netsentry-ap-interface.service
nftables.service
netsentry-dnsmasq.service
hostapd.service
AdGuardHome.service
tailscaled.service
suricata.service
wazuh-indexer.service
wazuh-manager.service
wazuh-dashboard.service
filebeat.service
```

The retired `netsentry-firewall.service` must not be treated as the active firewall service.

### Explicitly disabled when unused

```text
docker.service
docker.socket
containerd.service
```

### Retired

```text
netsentry-firewall.service
netsentry-snort-ap.service
netsentry-snort-watcher.service
```

### Health check

```bash
for s in ssh nginx netsentry-web netsentry-ap-interface nftables \
         netsentry-dnsmasq hostapd AdGuardHome tailscaled suricata \
         wazuh-indexer wazuh-manager wazuh-dashboard filebeat; do
  printf "%-32s enabled=%-12s active=%s\n" \
    "$s" \
    "$(systemctl is-enabled "$s" 2>/dev/null || echo not-found)" \
    "$(systemctl is-active "$s" 2>/dev/null || echo not-found)"
done
```

The nftables configuration should load before AP clients depend on forwarding. Because the configuration flushes the complete ruleset, Tailscale must load or be restarted afterward.

---

## 10. Remote Administration: Tailscale

```text
Interface: tailscale0
Purpose:   private SSH and web administration without public exposure
```

The nftables template permits Tailscale-interface TCP access to ports `22`, `80`, and `443`. It does not currently permit port `8443` through that rule and does not forward Tailscale traffic beyond the host.

Tailscale uses the host's iptables-nft compatibility backend and creates `ts-*` chains. These coexist with native `table inet netsentry` but are removed by `flush ruleset`; restart `tailscaled` after firewall application.

---

## 11. Secrets and Security Policy

Never commit real:

```text
Wi-Fi passphrases
AdGuard or dashboard credentials
NETSENTRY_WEB_SECRET
Private TLS keys
.env files
Operational PCAP captures
Runtime alert and log files
```

Store runtime secrets outside Git:

```text
/etc/netsentry/netsentry-web.env
/etc/netsentry/certs/
```

The PCAPs under `tests/cases/` are deliberate test fixtures. Sanitize every fixture before committing it because captures may expose traffic contents or addressing information.

`config/vars.yml` and historical scripts contain placeholder-like values. They must be replaced or moved to an external secret source before treating the repository as a production-ready or public deployment bundle.

Pre-commit secret scan:

```bash
git diff --cached | grep -Ei 'wpa_passphrase=|NETSENTRY_WEB_PASSWORD=|NETSENTRY_WEB_SECRET=|-----BEGIN .*PRIVATE KEY-----|PUT_YOUR_REAL_PASSWORD|PUT_A_LONG_RANDOM_SECRET' \
  && echo "STOP: real secret pattern found" \
  || echo "OK: no real secret patterns found"
```

---

## 12. Repository Structure

```text
app/
  netsentry_app.py                   Active Flask dashboard backend
  static/                            Dashboard CSS and JavaScript
  templates/                         Public and admin templates

config/
  vars.yml                           Shared deployment variables
  nginx/netsentry.conf               Nginx reference configuration
  suricata/suriata.yml               Tracked Suricata configuration copy
  systemd/                           Systemd unit copies
  wazuh/                             Wazuh reference configurations

templates/
  firewall.nft.j2                    Native nftables Jinja template

playbooks/
  firewall.yml                       nftables and IPv4-forwarding deployment

docs/
  NETSENTRY_MASTER_DOCUMENTATION.md  This document
  nftables-ansible.md                Manual template pipeline notes
  nftables_service.md                Playbook and service notes
  releases/                          Dated release notes

scripts/
  apply_firewall.sh                  Retired iptables implementation
  performance_check.sh               Resource usage check
  netsentry_dashboard.py             Historical dashboard
  netsentry_portal.py                Historical portal
  netsentry_status_api.py            Historical status API

suricata/rules/local.rules            Active local IDS rules

tests/cases/
  validate.py                         Isolated SID-based Suricata validator
  run_pcaps.py                        tcpdump capture inspection helper
  run_suricata.py                     Manual case-output generator
  <SID>/<SID>.pcap                    Versioned rule test fixtures
```

---

## 13. Version History

| Version | Milestone |
| --- | --- |
| V0 | Early Wi-Fi/SSH lab stage |
| v1.5 | Gateway, AP, and DHCP foundation |
| v1.6 | Web dashboard foundation |
| v1.8 | Stable AP, DHCP, DNS, firewall/NAT, dashboard, and Snort release |
| v1.9 | Suricata introduced alongside Snort |
| v2.1 | Wazuh mini-SIEM integration |
| v2.2 | Snort and the duplicate built-in IDS dashboard retired |
| v2.3 | Wazuh and Suricata performance tuning |
| v2.6 | Suricata/Wazuh tuning, native nftables migration, Ansible firewall deployment, PCAP rule validation, and reboot persistence verification |

---

## 14. Testing and Validation

### Automated Suricata cases

```bash
python3 tests/cases/validate.py
python3 tests/cases/validate.py 10000001
```

Expected result: each selected directory SID is the only Suricata alert SID generated. See Section 6 for prerequisites, semantics, and exit codes.

### PCAP readability

```bash
python3 tests/cases/run_pcaps.py
python3 tests/cases/run_pcaps.py 10000001
```

### Firewall deployment and syntax

```bash
ansible-playbook playbooks/firewall.yml --check --diff --ask-become-pass
ansible-playbook playbooks/firewall.yml --ask-become-pass
sudo systemctl restart tailscaled
```

### Full operational checklist

```bash
# 1. Firewall service and rules
sudo systemctl is-enabled nftables
sudo systemctl status nftables --no-pager
sudo nft list table inet netsentry
sudo sysctl net.ipv4.ip_forward

# 2. Confirm no retired NetSentry iptables rules returned
sudo iptables-save
sudo ip6tables-save

# 3. Service status
for s in ssh nginx netsentry-web netsentry-ap-interface nftables \
         netsentry-dnsmasq hostapd AdGuardHome tailscaled suricata \
         wazuh-indexer wazuh-manager wazuh-dashboard filebeat; do
  printf "%-32s enabled=%-12s active=%s\n" \
    "$s" \
    "$(systemctl is-enabled "$s" 2>/dev/null || echo not-found)" \
    "$(systemctl is-active "$s" 2>/dev/null || echo not-found)"
done

# 4. Suricata syntax and PCAP tests
sudo suricata -T -c /etc/suricata/suricata.yaml \
  -S /home/gbx/netsentry-gateway/suricata/rules/local.rules \
  -i wlx200db0220b9a -l /tmp/suricata-rule-test
python3 tests/cases/validate.py

# 5. Firewall logs
journalctl -k -n 100 --no-pager | grep -E 'nftables input drop|NETSENTRY_FW_FORWARD_DROP'

# 6. Wazuh services
sudo systemctl is-active wazuh-manager wazuh-indexer wazuh-dashboard filebeat

# 7. Snort retirement
systemctl list-units --type=service | grep -i snort || echo "OK: no Snort services"

# 8. Dashboard access
# NetSentry: https://192.168.1.19/
# Wazuh:     https://192.168.1.19:8443/
```

### Network behavior to verify

- AP client obtains a DHCP lease and uses the gateway DNS service.
- DNS filtering works.
- AP-to-internet forwarding and masquerading work.
- Established return traffic reaches AP clients.
- Home-to-AP and AP-to-home behavior matches the intended trust boundary.
- Admin and Tailscale management ports match the nftables template.
- Suricata alerts reach EVE and Wazuh.
- nftables, forwarding, AP connectivity, and Tailscale survive or recover after reboot.

---

## 15. Known Issues

1. **The nftables template flushes the complete ruleset.** Applying it removes tables owned by Tailscale, containers, and other firewall managers. The playbook does not restart those services; restart `tailscaled` after application and review other rule owners before deployment.
2. **AP clients can initiate connections to the full home subnet.** This is broader than an isolated guest/AP policy and should be restricted if not intentional.
3. **Administrative values have drifted across historical files.** The nftables deployment uses `config/vars.yml`, currently with admin IP `192.168.1.50`. Verify Nginx, Suricata, Flask, and system service configurations separately before assuming agreement.
4. **Suricata test paths are deployment-specific.** `validate.py` and `run_suricata.py` hardcode `/home/gbx/netsentry-gateway/suricata/rules/local.rules` and `/etc/suricata/suricata.yaml`.
5. **The tracked Suricata config filename is inconsistent.** The repository contains `config/suricata/suriata.yml`, while older documentation refers to `config/suricata/suricata.yaml`.
6. **`run_suricata.py` writes into fixture directories.** Append-mode logs can include earlier output; use `validate.py` for clean, temporary execution.
7. **Placeholder-like credentials remain in tracked examples and historical scripts.** They should be externalized or removed before public or production use.
8. **Historical implementations remain in the repository.** Retired firewall and dashboard files can be mistaken for active components without reading this document.

---

## 16. Unfinished / Planned Work

### Actions dashboard

Planned actions: **Watch**, **Restrict**, **Ban**, and **Unblock**.

Safe delivery order:

```text
1. UI only
2. Persist state without enforcement
3. Watch/logging mode
4. Restrict mode
5. Ban mode
6. Unblock mode
7. A narrowly scoped nftables enforcement helper
```

Any enforcement component must protect gateway, loopback, admin, and complete subnet addresses from accidental broad blocking. It must use native nftables rather than restoring the retired iptables path.

### Firewall hardening

- Decide whether AP-to-home initiation is intentional; otherwise restrict it to explicit destinations and ports.
- Replace global `flush ruleset` with ownership-scoped table replacement or explicitly coordinate all services whose tables are removed.
- Bind source-address trust to expected ingress interfaces where appropriate.
- Add a deployment rollback or out-of-band recovery procedure for remote administration lockout.
- Consider enforcing gateway-only DNS rather than only detecting external DNS use.

### Test portability

- Make Suricata rules and config paths command-line options or derive them from the repository and deployment configuration.
- Decide whether empty `expected.json` fixtures should be removed or incorporated into validation.
- Prevent manual output generation from contaminating tracked fixture directories.

### Other planned items

- Nginx/Flask HTTPS attack watcher for request-path and authentication visibility
- Review whether a second Suricata capture interface is required and document the deployed configuration
- Final architecture diagram update

Suricata provides network and TLS metadata but cannot inspect encrypted HTTP paths, headers, POST bodies, or credentials. Nginx and Flask logs remain the appropriate sources for HTTPS request and authentication monitoring.
