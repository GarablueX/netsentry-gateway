#!/usr/bin/env bash
set -euo pipefail 

TAILSCALE_I="tailscale0"
TAILSCALE_NET="100.64.0.0/10"
ADMIN_IP="192.168.1.8"
HOME_LAN="192.168.1.0/24"
AP_NET="10.10.10.0/24"
WAN_I="enp3s0"
AP_I="wlx200db0220b9a"

ROLLBACK_PID_FILE="/tmp/netsentry-fw-rollback.pid"



echo "[+] Applying NetSentry gateway firewall test rules"
echo "[+] Admin IP: $ADMIN_IP"
echo "[+] Home LAN: $HOME_LAN"
echo "[+] AP LAN:   $AP_NET"
echo "[+] WAN F:   $WAN_I"
echo "[+] AP I:    $AP_I"





sudo iptables -P INPUT ACCEPT 
sudo iptables -P FORWARD ACCEPT 
sudo iptables -P OUTPUT ACCEPT

sudo iptables -F
sudo iptables -t nat -F
sudo iptables -t mangle -F
sudo iptables -t raw -F

sudo iptables -X
sudo iptables -t nat -X
sudo iptables -t mangle -X
sudo iptables -t raw -X



sudo iptables -A INPUT  -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A INPUT  -m conntrack --ctstate INVALID -j DROP


# NAT TRASLATIONS 
sudo sysctl -w net.ipv4.ip_forward=1

#disable NAT  if communication with home lan 

sudo iptables -t nat -A POSTROUTING -s "$AP_NET" -d "$HOME_LAN" -j RETURN 

# nat if packet is going to the internet 

sudo iptables -t nat -A POSTROUTING -s "$AP_NET" -o "$WAN_I" -j MASQUERADE 

sudo iptables -A INPUT -i lo -j ACCEPT 

# ALLOW PINGS FROM BOTH LANS 

sudo iptables -A INPUT -p icmp -s "$HOME_LAN" -j ACCEPT

sudo iptables -A INPUT -p icmp -s "$AP_NET" -j ACCEPT

#




#SSH ONLY FOR ADMIN 

sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 22  -j ACCEPT

#ALLOW AD GUARD DNS FOR AP NET AND HOME LAN "

sudo iptables -A INPUT -p udp -s "$AP_NET" --dport 53 -j ACCEPT

sudo iptables -A INPUT -p tcp  -s "$AP_NET" --dport 53 -j ACCEPT

sudo iptables -A INPUT -p udp -s "$HOME_LAN" --dport 53 -j ACCEPT

sudo iptables -A INPUT -p tcp  -s "$HOME_LAN" --dport 53 -j ACCEPT

# ENABLE DHCP FOR AP LAN 

sudo iptables -A INPUT -i "$AP_I"  -p udp --sport 68 --dport 67 -j  ACCEPT 

#netsentry portal from both lans 

#sudo iptables -A INPUT -p tcp -s "$HOME_LAN" --dport 5500 -j ACCEPT 

#sudo iptables -A INPUT -p tcp -s "$AP_NET" --dport 5500 -j ACCEPT

#HOney pot for both lans 

#sudo iptables -A INPUT -p tcp -s "$HOME_LAN" --dport 8082 -j ACCEPT

#sudo iptables -A INPUT -p tcp -s "$AP_NET" --dport 8082 -j ACCEPT

# STATUS_API for both lans  

#sudo iptables -A INPUT -p tcp -s "$HOME_LAN" --dport 5051 -j ACCEPT

#sudo iptables -A INPUT -p tcp -s "$AP_NET" --dport 5051 -j ACCEPT

# ADMIN ONLY SERVICES  

#sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 5050 -j ACCEPT

sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 3001 -j ACCEPT

#sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 8081  -j ACCEPT

sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 21 -j ACCEPT

sudo iptables -A INPUT -p tcp -s "$ADMIN_IP" --dport 40000:40100 -j ACCEPT

# Nginx web frontend for NetSentry unified web app
sudo iptables -A INPUT -p tcp -s "$HOME_LAN" --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp -s "$AP_NET" --dport 80 -j ACCEPT

sudo iptables -A INPUT -p tcp -s "$HOME_LAN" --dport 443 -j ACCEPT
sudo iptables -A INPUT -p tcp -s "$AP_NET" --dport 443 -j ACCEPT



# Allow Tailscale remote admin access to NetSentry only
sudo iptables -A INPUT -i "$TAILSCALE_I" -s "$TAILSCALE_NET" -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -i "$TAILSCALE_I" -s "$TAILSCALE_NET" -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -i "$TAILSCALE_I" -s "$TAILSCALE_NET" -p tcp --dport 443 -j ACCEPT




#DROP EVERYTHING

sudo iptables -A  INPUT -j DROP 

#INTER VLAN ROUTING 

sudo iptables -A FORWARD -i "$WAN_I"  -o "$AP_I" -s "$HOME_LAN" -d "$AP_NET"  -j ACCEPT 

sudo iptables -A FORWARD -i  "$AP_I" -o "$WAN_I" -s "$AP_NET" -d "$HOME_LAN" -j ACCEPT 



#AP LAN TO UPSTREAM TO THE ISP ROUTER 

sudo iptables -A FORWARD -i "$AP_I" -o "$WAN_I" -s "$AP_NET" -j ACCEPT 

sudo iptables -A FORWARD -i "$WAN_I" -o "$AP_I" -d "$AP_NET" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 

sudo iptables -A  FORWARD -j DROP 




#DROP EVERYTHING ELSE (STATEFULL FIREWALL)

sudo iptables -P INPUT DROP 

sudo iptables -P FORWARD DROP 

sudo iptables -P OUTPUT ACCEPT 


#checking results 

 #input 
sudo iptables -L INPUT -n -v --line-numbers 

 #forward
sudo iptables -L FORWARD -n -v --line-numbers  

 #output 
sudo iptables -L OUTPUT -n -v --line-numbers 


