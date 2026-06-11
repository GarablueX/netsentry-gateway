#!/usr/bin/env bash

set -e

ADMIN_IP="192.168.1.11"
LAN_NET="192.168.1.0/24"

echo "[+] Applying NetSentry temporary lab firewall policy"
echo "[+] Admin IP: $ADMIN_IP"
echo "[+] LAN:      $LAN_NET"

echo "[!] Safety note: this script flushes INPUT and rebuilds lab rules."
read -rp "Continue? Type YES: " CONFIRM

if [ "$CONFIRM" != "YES" ]; then
    echo "[!] Aborted."
    exit 1
fi

echo "[+] Installing 120-second emergency rollback..."
sudo sh -c 'sleep 120; iptables -F INPUT; iptables -P INPUT ACCEPT' &
ROLLBACK_PID=$!

echo "[+] Flushing INPUT chain..."
sudo iptables -F INPUT
sudo iptables -P INPUT ACCEPT

echo "[+] Base rules..."
sudo iptables -A INPUT -i lo -j ACCEPT
sudo iptables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

echo "[+] SSH/SFTP admin only..."
sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 22 -j DROP

echo "[+] AdGuard UI admin only..."
sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 3001 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 3001 -j DROP

echo "[+] DNS from LAN..."
sudo iptables -A INPUT -p udp -s "$LAN_NET" --dport 53 -j ACCEPT
sudo iptables -A INPUT -p tcp -s "$LAN_NET" --dport 53 -j ACCEPT

echo "[+] ICMP from LAN..."
sudo iptables -A INPUT -p icmp -s "$LAN_NET" -j ACCEPT

echo "[+] IDS dashboard admin only..."
sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 5050 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 5050 -j DROP

echo "[+] Status API admin only..."
sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 5051 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 5051 -j DROP

echo "[+] HTTP test service admin only..."
sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 8081 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8081 -j DROP

echo "[+] Honeypot-lite LAN reachable..."
sudo iptables -A INPUT -p tcp -s "$LAN_NET" --dport 8082 -j ACCEPT

echo "[+] FTP ACCESS PORTS ADMIN ONLY ..."
sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 21 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 21 -j DROP

echo "[+] FTP PASSIVE PORTS ADMIN ONLY ..."
sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 40000:40100 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 40000:40100 -j DROP

echo "[+] Log and drop everything else..."
sudo iptables -A INPUT -m limit --limit 5/min -j LOG --log-prefix "NETSENTRY_INPUT_DROP: " --log-level 4
sudo iptables -A INPUT -j DROP

echo "[+] Firewall applied."
echo "[+] Testing SSH is still your responsibility before closing this session."
echo "[+] Canceling rollback in 5 seconds if script reached the end..."
sleep 5
kill "$ROLLBACK_PID" 2>/dev/null || true

sudo iptables -L INPUT -n -v --line-numbers
