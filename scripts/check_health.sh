#!/usr/bin/env bash
set -euo pipefail

echo "┏━━━━━━━━━━━━━━━━━━━━"
echo "┃ Checking services"
echo "┣━━━━━━━━━━━━━━━━━━━━"

for svc in suricata wazuh-manager wazuh-indexer wazuh-dashboard filebeat tailscaled \
           netsentry_dnsmasq.service netsentry_firewall.service netsentry_web.service netsentry_hostapd.service
do
    echo -n "┃ $svc … "
    sudo systemctl is-active --quiet "$svc" && echo "active" || echo "inactive"
done

echo "┗━━━━━━━━━━━━━━━━━━━━"
echo "× Hardware status"
sudo free -h
