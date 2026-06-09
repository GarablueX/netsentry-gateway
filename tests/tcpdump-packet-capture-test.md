# tcpdump Packet Capture Test

## Debian NetSentry IP
192.168.1.17

## Admin PC IP
192.168.1.11

## Interface used
wlx200db0220b9a

## Capture command
sudo tcpdump -i wlx200db0220b9a host 192.168.1.11 -w ~/netsentry-gateway/captures/admin-pc-test.pcap

## Traffic generated from Windows
- ping 192.168.1.17
- nslookup google.com 192.168.1.17
- nslookup tiktok.com 192.168.1.17

## Read pcap command
sudo tcpdump -r ~/netsentry-gateway/captures/admin-pc-test.pcap

## Read DNS-only packets
sudo tcpdump -r ~/netsentry-gateway/captures/admin-pc-test.pcap port 53

## Result
The packet capture file was created successfully and DNS packets were visible when filtering for port 53.

## Interpretation
NetSentry can capture packet evidence from traffic between the admin PC and the Debian machine. Monitor mode is not required for this test because the capture is for normal IP traffic reaching the Debian interface.
