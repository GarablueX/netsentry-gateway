#!/usr/bin/env bash

echo "[+] NetSentry INPUT firewall rules"
sudo iptables -L INPUT -n -v --line-numbers
