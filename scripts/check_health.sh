#!/usr/bin/env bash
set -euo pipefail 


echo "Checking services"
echo "[+][+][+][+][+][+][+][+][+][+][+][+]"
echo "[+] Checking Suricata, 3 Wazuh, Filebeat, Tailscale"

sudo systemctl is-active suricata 
sudo systemctl is-active wazuh-manager
sudo systemctl is-active wazuh-indexer
sudo systemctl is-active wazuh-dashboard
sudo systemctl is-active filebeat 
sudo systemctl is-active tailscaled

echo "[+][+][+][+][+][+][+][+][+][+][+][+]"
echo "[+] Checking netsentry services"

sudo systemctl is-active netsentry_dnsmasq.service
sudo systemctl is-active netsentry_firewall.service
sudo systemctl is-active netsentry_web.service
sudo systemctl is-active netsentry_hostapd.service

echo "[+][+][+][+][+][+][+][+][+][+][+][+]"
echo "[+] Hardware status "

sudo free -h 



