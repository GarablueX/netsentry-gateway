# NetSentry Gateway

<p align="center">
  <img src="Pics/Logo.png" alt="NetSentry Logo" width="200">
</p>

<p align="center">
  <b>Debian-based homelab security gateway</b><br>
  AP + DHCP + DNS filtering + nftables firewall/NAT + HTTPS dashboard + Suricata IDS + Wazuh SIEM
</p>

<p align="center">
  <b>Current version: v2.6.0 — Stable</b>
</p>

---

## Overview

NetSentry turns a Debian machine into a security gateway between a home network and a Wi-Fi client subnet. It combines routing, DHCP, DNS filtering, native nftables firewall/NAT, network intrusion detection with Suricata, Wazuh SIEM, and a read-only operations dashboard.

> **Authoritative reference:** [`docs/NETSENTRY_MASTER_DOCUMENTATION.md`](docs/NETSENTRY_MASTER_DOCUMENTATION.md)

---

## Key Features

- **Wi-Fi Access Point** (`hostapd`) on `10.10.10.0/24`
- **DHCP Server** (`dnsmasq`) for AP clients
- **DNS Filtering** through AdGuard Home
- **Stateful Firewall/NAT** through native nftables, rendered and deployed with Ansible
- **Network IDS** (Suricata) with PCAP-based rule validation
- **SIEM** (Wazuh) for Suricata alerts, firewall logs, and system events
- **Read-Only Operations Dashboard** (Flask + Nginx)
- **Remote Administration** through Tailscale
- **Service Orchestration** with systemd

---

## Getting Started

> Adjust the interface names, networks, addresses, and SSID in `config/vars.yml` for the target gateway before deployment. The checked-in values are deployment-specific examples, not universal defaults.

### Prerequisites

- Debian or Ubuntu system using systemd and `apt`
- Python 3
- Ansible and the `ansible.posix` collection
- Root access through `sudo`
- Suricata for IDS and PCAP validation
- `tcpdump` for manual PCAP inspection

Install the Ansible collection if it is not already available:

```bash
ansible-galaxy collection install ansible.posix
```

### Setup

1. Clone the repository and review the master documentation:

   ```bash
   git clone https://github.com/your-username/netsentry-gateway.git
   cd netsentry-gateway
   less docs/NETSENTRY_MASTER_DOCUMENTATION.md
   ```

2. Review `config/vars.yml`, especially:

   - `network.wan_interface` and `network.ap_interface`
   - Home, AP, gateway, admin, and Tailscale addresses
   - DHCP range and SSID
   - Firewall management ports

3. Keep real credentials outside Git. Create `/etc/netsentry/netsentry-web.env`, install TLS certificates under `/etc/netsentry/certs/`, and replace example values before deployment.

4. Deploy the native nftables firewall from the repository root:

   ```bash
   ansible-playbook playbooks/firewall.yml --ask-become-pass
   ```

   The playbook installs nftables, persists IPv4 forwarding, validates the rendered ruleset with `nft --check`, installs `/etc/nftables.conf`, and enables `nftables.service`.

5. Because the ruleset begins with `flush ruleset`, reloads remove tables owned by other services. Restart Tailscale after applying the firewall so it recreates its `ts-*` compatibility chains:

   ```bash
   sudo systemctl restart tailscaled
   ```

6. Verify the firewall and routing state:

   ```bash
   sudo systemctl is-enabled nftables
   sudo systemctl status nftables --no-pager
   sudo nft list table inet netsentry
   sudo sysctl net.ipv4.ip_forward
   ```

7. Enable and start the remaining services required by your deployment, then connect a client to the configured SSID and verify dashboard, DNS, forwarding, IDS, and SIEM access.

---

## Firewall Architecture

The active NetSentry firewall is native nftables:

```text
config/vars.yml
    -> templates/firewall.nft.j2
    -> playbooks/firewall.yml
    -> /etc/nftables.conf
    -> nftables.service
```

It creates `table inet netsentry` with:

- `input`: default-drop gateway protection, admin/Tailscale management access, AP DNS and DHCP, and web access
- `forward`: home-to-AP, AP-to-home, AP-to-internet, and established return traffic
- `postrouting`: AP internet masquerading while preserving AP source addresses for home-LAN traffic
- Rate-limited input and forwarding drop logs

`scripts/apply_firewall.sh` and `netsentry-firewall.service` belong to the retired iptables implementation and are not the active deployment path.

> **Security review:** The current forward policy lets AP clients initiate connections to all of `network.home_lan`. Restrict or remove that rule if the AP network should be isolated from home devices.

---

## Suricata PCAP Validation

Test fixtures use this convention:

```text
tests/cases/<SID>/<SID>.pcap
```

Run every case or one selected SID:

```bash
python3 tests/cases/validate.py
python3 tests/cases/validate.py 10000001
```

For each case, `validate.py`:

1. Runs Suricata against the PCAP with checksum validation disabled.
2. Writes output to a fresh temporary directory.
3. Parses newline-delimited `eve.json` events.
4. Passes only when the directory SID triggers at least once and no different SID triggers.
5. Deletes the temporary output after the case.

Exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | Every selected case passed |
| `1` | One or more alert-validation failures |
| `2` | Configuration, discovery, execution, or missing-output error |

The validator currently expects these paths:

```text
/home/gbx/netsentry-gateway/suricata/rules/local.rules
/etc/suricata/suricata.yaml
```

Update the constants in `tests/cases/validate.py` if the checkout or system configuration lives elsewhere. The command also uses `sudo suricata`.

Inspect all PCAPs or one fixture with tcpdump:

```bash
python3 tests/cases/run_pcaps.py
python3 tests/cases/run_pcaps.py 10000001
```

`run_pcaps.py` checks whether `sudo tcpdump -r` can process each capture; it does not validate Suricata alerts. `run_suricata.py` is a manual output-generation helper that writes logs into each case directory, while `validate.py` is the isolated correctness test.

---

## Security and Secrets Policy

Never commit real:

- Wi-Fi, AdGuard, dashboard, or other credentials
- `NETSENTRY_WEB_SECRET`
- Private TLS keys or `.env` files
- Operational captures or runtime alert/log files

Versioned files under `tests/cases/` are deliberate test fixtures. Review and sanitize any PCAP before adding it because captures may contain sensitive traffic.

Store runtime secrets outside Git:

```text
/etc/netsentry/netsentry-web.env
/etc/netsentry/certs/
```

The repository still contains placeholder-like values and historical scripts. Replace deployment-specific examples and review the complete policy in the master documentation before public or production use.

---

## Known Issues and Planned Work

- `templates/firewall.nft.j2` starts with `flush ruleset`; the playbook does not currently restart services such as Tailscale whose rules are removed by that command.
- AP-to-home forwarding currently permits AP clients to initiate connections to the complete home subnet.
- Suricata test scripts contain deployment-specific absolute rules/config paths.
- Network and admin values have drifted across historical files; use `config/vars.yml` for the nftables deployment and verify other live service configurations separately.
- Planned work includes the client actions dashboard, an HTTPS attack watcher, and architecture diagram updates.

---

## Validation

See Section 14 of the master documentation for firewall, routing, Suricata, Wazuh, dashboard, and reboot-persistence checks. Supporting test fixtures and utilities are under `tests/cases/`.

---

## License

This project is provided as-is for educational and personal use. No formal license is applied; assume all rights reserved unless explicitly stated otherwise. Contact the author before reusing significant portions.

---

## Acknowledgments

NetSentry builds on Debian, hostapd, dnsmasq, AdGuard Home, nftables, Nginx, Flask, Suricata, Wazuh, Filebeat, systemd, and Tailscale.

---

> NetSentry v2.6.0 demonstrates Linux networking, AP mode, DHCP, DNS filtering, native nftables firewalling, IDS/SIEM integration, service automation, private remote administration, and operational visibility in a continuously running homelab. It is a learning platform rather than an enterprise-ready product.
