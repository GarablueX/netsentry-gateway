# nftables Firewall — Ansible Template Pipeline

## Goal

Replace `scripts/apply_firewall.sh` with a Jinja2 template rendered from `config/vars.yml`, so the nftables ruleset is version-controlled as data-driven infrastructure rather than a static shell script.

## Overview

The firewall is now defined as a single Jinja2 template (`templates/firewall.nft.j2`) that references variables stored in `config/vars.yml`. Ansible renders the template into `/tmp/firewall.nft`, `nft --check` validates the rendered syntax without applying it, and the validated ruleset is installed as `/etc/nftables.conf` and activated through systemd.

## How it works

### 1. Variable source — `config/vars.yml`

`config/vars.yml` is the single source of truth for all firewall-relevant values. It stores:

- **Network addresses** — `home_lan` (`192.168.1.0/24`), `ap_lan` (`10.10.10.0/24`), `admin_ip`, `netsentry_home_ip`, `netsentry_ap_ip`, and the Tailscale range `tailscale_net` (`100.64.0.0/10`).
- **Network interfaces** — `wan_interface` (`enp3s0`), `ap_interface` (`wlx200db0220b9a`), and `tailscale_interface` (`tailscale0`).
- **Ports** — SSH (`22`), HTTP (`80`), HTTPS (`443`), and the AdGuard UI port (`3001`) under the `firewall:` key.

### 2. The template — `templates/firewall.nft.j2`

The template is a Jinja2 file containing native nftables syntax with `{{ }}` references into the `config/vars.yml` variables. It defines the `inet netsentry` table with three chains:

- **`input`** — traffic destined for the gateway itself. Accepts established/related connections, ICMP from the LANs, admin SSH/HTTP/HTTPS from `admin_ip`, web ports from `home_lan`/`ap_lan`, DNS from the AP LAN, DHCP relay on the AP interface, and Tailscale-sourced admin access. All other input is logged and dropped.
- **`forward`** — traffic transiting the gateway. Permits inter-VLAN flow home↔AP, AP→WAN internet access, and return traffic. Drops everything else with a `NETSENTRY_FW_FORWARD_DROP` log prefix.
- **`postrouting`** — NAT/masquerading so AP clients (`ap_lan`) can egress to the internet through `wan_interface`. Traffic from `ap_lan` to `home_lan` returns un-NATted (`return`) so local services stay reachable by their real addresses.

The rendered file begins with `flush ruleset`, which clears every active nftables table before the `netsentry` table is loaded.

### 3. Rendering with Ansible

Render the template locally:

```bash
ansible localhost \
  --connection=local \
  --module-name=template \
  --args="src=templates/firewall.nft.j2 dest=/tmp/firewall.nft mode=0600" \
  --extra-vars="@config/vars.yml"
```

### 4. Validation

Validate the rendered nftables syntax without applying it:

```bash
sudo nft --check --file /tmp/firewall.nft
```

### 5. Installation

Install the validated ruleset as the system nftables config:

```bash
sudo install -o root -g root -m 0644 /tmp/firewall.nft /etc/nftables.conf
```

### 6. Activation

The `nftables.service` systemd unit executes `nft -f /etc/nftables.conf` on start/restart. Reload and restart the service, then restart `tailscaled`:

```bash
sudo systemctl restart nftables
sudo systemctl restart tailscaled
```

## Tailscale interaction

Because this system's iptables uses the **nf_tables backend**, Tailscale's iptables rules appear inside `nft list ruleset` as tables marked as managed by `iptables-nft` rather than as a separate `iptables` legacy ruleset. This means Tailscale coexists with the `inet netsentry` table inside the same nftables ruleset — the `flush ruleset` directive at the top of the rendered file clears all tables including Tailscale-managed ones, so the ordering matters: render and reload the firewall first, then restart `tailscaled` so it can re-inject its rules into the freshly loaded ruleset.

## Testing performed

The full pipeline was executed end-to-end:

1. Rendered `templates/firewall.nft.j2` → `/tmp/firewall.nft` via the Ansible `template` module with `config/vars.yml`.
2. `sudo nft --check --file /tmp/firewall.nft` — passed.
3. Installed to `/etc/nftables.conf`.
4. `sudo systemctl restart nftables` — applied.
5. `sudo systemctl restart tailscaled` — re-injected its nf_tables backend rules.
6. Verified SSH and all gateway services from both the **admin** host and the **client**, all reachable and functioning.

## File map

| Path | Role |
|------|------|
| `templates/firewall.nft.j2` | Jinja2 nftables template |
| `config/vars.yml` | Variable source (addresses, interfaces, ports) |
| `/tmp/firewall.nft` | Rendered ruleset (intermediate) |
| `/etc/nftables.conf` | Installed system nftables config |
| `playbooks/firewall.yml` | Ansible playbook driving the render + deploy |
