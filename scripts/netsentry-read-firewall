#!/bin/sh
set -eu
IPTABLES="/usr/sbin/iptables"
case "${1:-}" in
  input) "$IPTABLES" -L INPUT -n -v --line-numbers ;;
  forward) "$IPTABLES" -L FORWARD -n -v --line-numbers ;;
  nat) "$IPTABLES" -t nat -L -n -v --line-numbers ;;
  all)
    echo "===== INPUT ====="; "$IPTABLES" -L INPUT -n -v --line-numbers
    echo; echo "===== FORWARD ====="; "$IPTABLES" -L FORWARD -n -v --line-numbers
    echo; echo "===== NAT ====="; "$IPTABLES" -t nat -L -n -v --line-numbers
    ;;
  *) echo "Usage: netsentry-read-firewall {input|forward|nat|all}" >&2; exit 1 ;;
esac
