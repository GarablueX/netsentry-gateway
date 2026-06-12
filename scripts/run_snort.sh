#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/home/gbx/netsentry-gateway"
INTERFACE="enp3s0"

SNORT_BIN="/usr/local/bin/snort"
SNORT_CONFIG="/usr/local/etc/snort/snort.lua"
SNORT_RULES="/home/gbx/netsentry-gateway/snort/rules/local.rules"
ALERT_DIR="/home/gbx/netsentry-gateway/snort/alerts"
ALERT_FILE="/home/gbx/netsentry-gateway/snort/alerts/alert_fast.txt"

mkdir -p "$ALERT_DIR"
touch "$ALERT_FILE"

echo "[+] Starting NetSentry Snort"
echo "[+] User: $(whoami)"
echo "[+] HOME: $HOME"
echo "[+] Base dir: $BASE_DIR"
echo "[+] Interface: $INTERFACE"
echo "[+] Snort binary: $SNORT_BIN"
echo "[+] Snort config: $SNORT_CONFIG"
echo "[+] Snort rules: $SNORT_RULES"
echo "[+] Alert file: $ALERT_FILE"

if [ ! -x "$SNORT_BIN" ]; then
    echo "[!] Snort binary not found or not executable: $SNORT_BIN"
    command -v snort || true
    exit 1
fi

if [ ! -f "$SNORT_CONFIG" ]; then
    echo "[!] Snort config not found: $SNORT_CONFIG"
    exit 1
fi

if [ ! -f "$SNORT_RULES" ]; then
    echo "[!] Snort rules file not found: $SNORT_RULES"
    exit 1
fi

exec stdbuf -oL -eL "$SNORT_BIN" \
-c "$SNORT_CONFIG" \
-R "$SNORT_RULES" \
-i "$INTERFACE" \
-A alert_fast | stdbuf -oL tee -a "$ALERT_FILE"
