# nftables as a Managed Service

## Goal

Manage the `netsentry` nftables firewall as a proper system service using an Ansible playbook, rather than ad-hoc shell scripts. The playbook in `playbooks/firewall.yml` loads `config/vars.yml`, installs nftables, renders the firewall template into `/etc/nftables.conf`, validates it before replacing the live file, enables the service at boot, reloads it on template changes, and persistently enables IPv4 forwarding so the gateway can route/AP traffic.

## Playbook

`playbooks/firewall.yml` is a single play targeting `localhost` with `become: true`. Run it with:

```bash
ansible-playbook playbooks/firewall.yml --ask-become-pass
```

### What it does, step by step

1. **Loads variables** from `../config/vars.yml` via `vars_files`. All firewall-relevant values — networks, interfaces, ports, and service addresses — come from this one file.
2. **Installs nftables** through the `apt` module (`nftables` package, `state: present`).
3. **Enables IPv4 forwarding persistently** using the `ansible.posix.sysctl` module — sets `net.ipv4.ip_forward=1` and writes it to `/etc/sysctl.d/99-netsentry.conf` so it survives reboots.
4. **Renders the template** — the `template` module renders `templates/firewall.nft.j2` into `/etc/nftables.conf` with `owner: root, group: root, mode: '0644'`. Critically, the task uses the `validate:` directive:

   ```yaml
   validate: "/usr/sbin/nft --check --file %s"
   ```

   This means Ansible substitutes `%s` with the rendered temp file and runs `nft --check --file <tempfile>` **before** replacing the live `/etc/nftables.conf`. If syntax is invalid, the deployment aborts and the running firewall is left untouched.
5. **Notifies the `Reload nftables` handler** whenever the rendered `/etc/nftables.conf` changes — the handler does `systemctl reload nftables`, which applies the new ruleset without a full down/up cycle.
6. **Enables and starts nftables** via the `systemd_service` module — `enabled: true`, `state: started`. nftables is enabled at boot and running after the play.

### Handler

```yaml
handlers:
  - name: Reload nftables
    ansible.builtin.systemd:
      name: nftables
      state: reloaded
```

`reloaded` (not `restarted`) so the service re-reads `/etc/nftables.conf` (`nft -f /etc/nftables.conf`) while minimizing disruption. This handler only fires when the template task reports `changed`, i.e. when the rendered ruleset actually differs from what's currently installed.

## Validation commands

After running the playbook, these commands confirm everything is wired up correctly:

```bash
sudo systemctl is-enabled nftables      # should print "enabled"
sudo systemctl status nftables --no-pager        # should show "active (running)" / loaded / enabled
sudo nft list table inet netsentry                # should show the full ruleset (sets, chains)
sudo sysctl net.ipv4.ip_forward                   # should print "net.ipv4.ip_forward = 1"
sudo iptables-save                                # empty or minimal (no legacy iptables rules)
sudo ip6tables-save                               # empty or minimal
```

### Expected results

- `systemctl is-enabled nftables` → **`enabled`**
- `systemctl status nftables --no-pager` → **`active (running)`**, service loaded and enabled, running on boot.
- `nft list table inet netsentry` → the rendered ruleset is present, including:
  - sets (`admin_ip`, `home_lan`, `ap_lan`, `netsentry_ips`, `tailscale_net`, `allowed_admin_ports`, `allowed_ports`, `web_ports`)
  - three chains: `input` (policy `drop`), `forward` (policy `drop`), `postrouting` (policy `accept`)
- `sysctl net.ipv4.ip_forward` → `net.ipv4.ip_forward = 1` (persisted to `/etc/sysctl.d/99-netsentry.conf`)
- `iptables-save` / `ip6tables-save` → empty or minimal. Because this system's iptables uses the **nf_tables backend**, there is no separate legacy iptables ruleset — Tailscale's rules live inside `nft list ruleset` as `iptables-nft`-managed tables alongside the `inet netsentry` table.

## Why this approach

- **Validation before apply** — the `validate:` directive means a broken template never reaches the live `/etc/nftables.conf`. A syntax error aborts the play; the running firewall is unaffected.
- **Idempotent** — Ansible only reloads when the rendered file changes, and the `Reload nftables` handler fires only on `changed`. Re-running the play on an unchanged config is a no-op.
- **Boot-safe** — `enabled: true` on the `nftables` service means the ruleset loads automatically at startup, and the `sysctl` module writes a persistent `/etc/sysctl.d/99-netsentry.conf` so forwarding survives reboots.
- **Service-oriented** — the firewall is now `systemctl status nftables` instead of a custom script, so boot, reload, and status all use standard systemd semantics.
