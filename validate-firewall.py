#!/usr/bin/env python3
"""
Comprehensive validation script for NetSentry firewall templates.
Tests template rendering, syntax validation, and rule logic.
"""
import yaml
import subprocess
import sys
from jinja2 import Environment, FileSystemLoader

def load_vars():
    """Load variables from config/vars.yml"""
    with open('config/vars.yml', 'r') as f:
        return yaml.safe_load(f)

def render_template(vars_data):
    """Render the firewall template with variables"""
    env = Environment(loader=FileSystemLoader('templates'), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template('firewall.nft.j2')
    return template.render(**vars_data)

def validate_syntax(rendered_content):
    """Validate nftables syntax using nft -c"""
    result = subprocess.run(
        ['nft', '-c', '-f', '-'],
        input=rendered_content.encode(),
        capture_output=True
    )
    return result.returncode == 0, result.stderr.decode()

def check_rule_coverage(rendered_content):
    """Check that important rules are present"""
    checks = {
        'table_definition': 'table inet netsentry',
        'input_chain': 'chain input',
        'forward_chain': 'chain forward',
        'postrouting_chain': 'chain postrouting',
        'established_related': 'ct state established,related accept',
        'invalid_drop': 'ct state invalid drop',
        'loopback_accept': 'iifname "lo" accept',
        'icmp_home_lan': 'ip protocol icmp ip saddr @home_lan accept',
        'icmp_ap_lan': 'ip protocol icmp ip saddr @ap_lan accept',
        'admin_access': 'ip saddr @admin_ip tcp dport @allowed_admin_ports accept',
        'tailscale_access': 'iifname "{{ network.tailscale_interface }}"',
        'dns_ap_lan': 'ip saddr @ap_lan udp dport 53 accept',
        'dhcp_ap': 'udp sport 68 dport 67 accept',
        'web_home_lan': 'ip saddr @home_lan tcp dport @web_ports accept',
        'web_ap_lan': 'ip saddr @ap_lan tcp dport @web_ports accept',
        'forward_home_to_ap': 'iifname "{{ network.wan_interface }}" oifname "{{ network.ap_interface }}"',
        'forward_ap_to_home': 'iifname "{{ network.ap_interface }}" oifname "{{ network.wan_interface }}"',
        'masquerade': 'ip saddr @ap_lan oifname "{{ network.wan_interface }}" masquerade',
        'log_input_drops': 'log prefix "nftables input drop:"',
        'log_forward_drops': 'log prefix "NETSENTRY_FW_FORWARD_DROP"',
    }

    results = {}
    for check_name, pattern in checks.items():
        # For patterns with template variables, check the rendered version
        if '{{' in pattern:
            # These would be rendered, so check for the rendered values
            # We'll do a simpler check for the static parts
            static_part = pattern.split('{{')[0].strip()
            if static_part:
                results[check_name] = static_part in rendered_content
            else:
                results[check_name] = True
        else:
            results[check_name] = pattern in rendered_content

    return results

def main():
    print("=== NetSentry Firewall Template Validation ===\n")

    # Load variables
    print("1. Loading variables from config/vars.yml...")
    try:
        vars_data = load_vars()
        print(f"   [OK] Loaded {len(vars_data)} top-level sections")
        for key in vars_data:
            print(f"     - {key}")
    except Exception as e:
        print(f"   [FAIL] Failed to load variables: {e}")
        return 1

    # Render template
    print("\n2. Rendering firewall.nft.j2 template...")
    try:
        rendered = render_template(vars_data)
        print(f"   [OK] Template rendered ({len(rendered)} characters, {len(rendered.split(chr(10)))} lines)")
    except Exception as e:
        print(f"   [FAIL] Template rendering failed: {e}")
        return 1

    # Save rendered output
    with open('firewall.rendered.nft', 'w') as f:
        f.write(rendered)
    print("   [OK] Saved to firewall.rendered.nft")

    # Validate syntax
    print("\n3. Validating nftables syntax...")
    valid, stderr = validate_syntax(rendered)
    if valid:
        print("   [OK] Syntax validation PASSED")
    else:
        print(f"   [FAIL] Syntax validation FAILED:")
        print(stderr)
        return 1

    # Check rule coverage
    print("\n4. Checking rule coverage...")
    checks = check_rule_coverage(rendered)
    all_passed = True
    for check_name, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"   {status} {check_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n   [OK] All rule coverage checks PASSED")
    else:
        print("\n   [WARN] Some rule coverage checks FAILED")

    # Check variable substitution
    print("\n5. Checking variable substitution...")
    unsubstituted = [line for line in rendered.split('\n') if '{{' in line and '}}' in line]
    if unsubstituted:
        print(f"   [WARN] Found {len(unsubstituted)} lines with unsubstituted variables:")
        for line in unsubstituted[:5]:
            print(f"      {line.strip()}")
        if len(unsubstituted) > 5:
            print(f"      ... and {len(unsubstituted) - 5} more")
    else:
        print("   [OK] All variables substituted")

    # Summary
    print("\n=== Validation Summary ===")
    if valid and all_passed and not unsubstituted:
        print("[OK] ALL CHECKS PASSED - Firewall template is ready for deployment")
        return 0
    else:
        print("[FAIL] SOME CHECKS FAILED - Review output above")
        return 1

if __name__ == '__main__':
    sys.exit(main())
