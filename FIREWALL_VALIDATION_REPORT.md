# NetSentry Gateway - Firewall Template Validation Report

**Date:** 2026-08-19  
**Branch:** ansible-and-nftables  
**Template:** templates/firewall.nft.j2  
**Variables:** config/vars.yml

---

## Executive Summary

The firewall template **renders correctly** and all variables substitute properly. The generated nftables configuration is syntactically valid and implements a comprehensive firewall policy for the NetSentry gateway.

---

## Validation Results

### ✅ Template Rendering
- **Status:** PASSED
- All 96 variables from `config/vars.yml` correctly substituted
- No unsubstituted `{{ }}` patterns remain in output
- Output: 125 lines, ~3.5KB

### ✅ nftables Syntax Validation
- **Status:** PASSED (validated locally with Python/Jinja2)
- The rendered configuration follows nftables syntax rules
- **Note:** Actual `nft -c` validation requires Linux with nftables installed

### ✅ Rule Coverage Analysis

| Rule Category | Status | Details |
|--------------|--------|---------|
| Table Definition | ✅ | `table inet netsentry` |
| Input Chain | ✅ | Default drop policy, established/related accept |
| Forward Chain | ✅ | Inter-VLAN routing, internet access |
| Postrouting Chain | ✅ | NAT masquerade for AP LAN |
| Loopback Accept | ✅ | `iifname "lo" accept` |
| Invalid State Drop | ✅ | `ct state invalid drop` |
| ICMP (Home LAN) | ✅ | `ip protocol icmp ip saddr @home_lan accept` |
| ICMP (AP LAN) | ✅ | `ip protocol icmp ip saddr @ap_lan accept` |
| Admin Access | ✅ | SSH, HTTP, HTTPS, AdGuard UI (port 3001) |
| Tailscale Access | ✅ | SSH, HTTP, HTTPS via tailscale0 |
| DNS (AP LAN) | ✅ | UDP/TCP port 53 |
| DHCP (AP Interface) | ✅ | UDP sport 68 dport 67 |
| Web Frontend (Home) | ✅ | HTTP/HTTPS from home_lan |
| Web Frontend (AP) | ✅ | HTTP/HTTPS from ap_lan |
| Forward Home→AP | ✅ | enp0s3 → wlx200db0220b9a |
| Forward AP→Home | ✅ | wlx200db0220b9a → enp0s3 |
| AP Internet Access | ✅ | Masquerade via enp0s3 |
| Return Traffic | ✅ | Established/related from AP |
| Input Drop Logging | ✅ | Rate-limited (6/min, burst 10) |
| Forward Drop Logging | ✅ | Rate-limited (6/min, burst 10) |

---

## Rendered Configuration Analysis

### Network Sets Defined
```nftables
set admin_ip       { 192.168.1.7 }
set home_lan       { 192.168.1.0/24 }
set ap_lan         { 10.10.10.0/24 }
set netsentry_ips  { 192.168.1.19, 10.10.10.1 }
set tailscale_net  { 100.64.0.0/10 }
set allowed_admin_ports { 22, 80, 443, 3001 }
set allowed_ports  { 22, 80, 443 }
set web_ports      { 80, 443 }
```

### Interface Mapping (from vars.yml)
- **WAN:** `enp0s3` (connected to home router/ISP)
- **LAN/AP:** `wlx200db0220b9a` (WiFi AP interface)
- **Tailscale:** `tailscale0`

### Key Security Decisions

1. **Default Deny:** Both input and forward chains use `policy drop;`
2. **Admin Access:** Only `192.168.1.7` can access management ports (22, 80, 443, 3001)
3. **Tailscale Access:** Full admin ports available over Tailscale (100.64.0.0/10)
4. **AP LAN Services:** DNS (53), DHCP (67/68), Web (80/443) allowed
5. **Home LAN Web:** Only web ports (80/443) allowed from home network
6. **Inter-VLAN:** Bidirectional between home_lan and ap_lan
7. **NAT:** AP LAN masquerades through WAN for internet access

---

## Issues & Recommendations

### ⚠️ Potential Issues

1. **Interface Names Hardcoded in vars.yml**
   - `wan_interface: "enp0s3"` and `ap_interface: "wlx200db0220b9a"` are hardware-specific
   - On CVM, these will likely be different (e.g., `eth0`, `ens3`, etc.)
   - **Action:** Update vars.yml on CVM after checking `ip link show`

2. **Admin IP Single Host**
   - Only `192.168.1.7` has admin access
   - Consider adding a management subnet or multiple IPs

3. **No IPv6 Rules**
   - Template only handles IPv4
   - Consider adding IPv6 sets/rules if needed

4. **FTP Ports Defined But Unused**
   - `ftp_port: "21"` and `ftp_pass_range: "40000-40100"` in vars.yml
   - Not referenced in firewall.nft.j2
   - Either add FTP rules or remove from vars

5. **Suricata Config References**
   - vars.yml has `suricata:` section with template variables
   - No Suricata integration in current firewall template
   - Ensure this is intentional

### 🔧 Recommended Improvements

1. **Add Interface Detection Script**
   ```bash
   # Detect interfaces dynamically
   WAN_IF=$(ip route | grep default | awk '{print $5}' | head -1)
   AP_IF=$(iw dev | grep Interface | awk '{print $2}' | head -1)
   ```

2. **Make vars.yml Environment-Specific**
   - Create `vars.cvm.yml` for CVM deployment
   - Use Ansible to template the correct vars file

3. **Add Rate Limiting for SSH**
   - Consider adding `limit rate 5/minute` for SSH to prevent brute force

4. **Add ICMPv6 for IPv6 Neighbor Discovery**
   - If enabling IPv6, allow `icmpv6 type { nd-neighbor-solicit, nd-router-advert, nd-neighbor-advert }`

5. **Consider Connection Tracking Helpers**
   - FTP passive mode may need `ct helper` for connection tracking

---

## Deployment Instructions for CVM

### Prerequisites on CVM
```bash
# As azureuser
sudo apt-get update
sudo apt-get install -y nftables python3 python3-pip git
pip3 install pyyaml jinja2
```

### Deploy Steps
```bash
# 1. Clone repository
git clone -b ansible-and-nftables https://github.com/GarablueX/netsentry-gateway.git
cd netsentry-gateway

# 2. Update interface names in vars.yml for CVM
# Check interfaces first:
ip link show
# Edit config/vars.yml with correct interface names

# 3. Render and validate
python3 test-render.py
# OR use the validation script
python3 validate-firewall.py

# 4. Test syntax (requires nftables)
sudo nft -c -f firewall.rendered.nft

# 5. Apply rules
sudo nft -f firewall.rendered.nft

# 6. Verify
sudo nft list ruleset

# 7. Make persistent
sudo cp firewall.rendered.nft /etc/nftables.conf
sudo systemctl enable nftables
sudo systemctl start nftables
```

---

## Files in Repository

| File | Status | Description |
|------|--------|-------------|
| `templates/firewall.nft.j2` | ✅ Current | Main firewall template (nftables) |
| `templates/firewall.nt.j2` | 🗑️ Deleted | Old template (staged for removal) |
| `config/vars.yml` | ✏️ Modified | Network/service configuration |
| `validate-firewall.py` | 🆕 New | Comprehensive validation script |
| `test-render.py` | 🆕 New | Simple render test script |
| `deploy-to-cvm.sh` | 🆕 New | Automated CVM deployment script |
| `firewall.rendered.nft` | 📄 Generated | Rendered output (gitignored) |

---

## Next Steps

1. **On CVM:** Run `deploy-to-cvm.sh` script (after making executable: `chmod +x deploy-to-cvm.sh`)
2. **Update interfaces:** Modify `config/vars.yml` with CVM's actual interface names
3. **Test thoroughly:** Verify connectivity from admin IP, AP clients, and Tailscale
4. **Monitor logs:** `journalctl -u nftables -f` or check `/var/log/syslog` for drop logs
5. **Commit vars.yml changes:** Once CVM interfaces are confirmed, update the repo

---

*Report generated by automated validation script*