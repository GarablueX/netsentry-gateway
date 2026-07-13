#!/usr/bin/env bash
set -euo pipefail

echo "== Memory =="
free -h

echo
echo "== Swap =="
swapon --show || true

echo
echo "== Swappiness =="
cat /proc/sys/vm/swappiness

echo
echo "== Top RAM processes =="
ps -eo pid,comm,%cpu,%mem,rss,args --sort=-rss | head -20

echo
echo "== Active NetSentry/Wazuh services =="
systemctl list-units --type=service --state=running | grep -Ei 'wazuh|suricata|adguard|nginx|netsentry|tailscale|hostapd' || true

echo
echo "== Disabled unused services =="
for s in docker.service docker.socket containerd.service; do
  printf "%-24s enabled=%-12s active=%s\n" "$s" "$(systemctl is-enabled "$s" 2>/dev/null || echo not-found)" "$(systemctl is-active "$s" 2>/dev/null || echo not-found)"
done
