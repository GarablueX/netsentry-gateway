# NetSentry V0 — Snort 3 IDS Alert Dashboard Day Log

## Goal of the Day

Build the first working IDS alert pipeline for NetSentry V0.

The target was:

```text
Snort detects traffic
→ alert output is saved
→ Python watcher parses alerts
→ structured JSONL alert file is created
→ Flask dashboard displays alerts
→ dashboard is protected by iptables
```

## Starting Context

NetSentry was already running as a Debian V0 lab host.

Current network:

| Item | Value |
|---|---|
| Debian NetSentry IP | `192.168.1.17` |
| Admin laptop IP | `192.168.1.11` |
| LAN | `192.168.1.0/24` |
| Active interface | `wlx200db0220b9a` |

Important note:

```text
NetSentry is not a full gateway yet.
Snort is currently host-facing IDS.
It detects traffic hitting the Debian machine itself.
```

---

# 1. Snort 3 Package Check

Tried to install Snort 3 from APT:

```bash
sudo apt install snort3 -y
```

Result:

```text
Unable to locate package snort3
```

Decision:

```text
Do not use random packages.
Do not add unstable repositories.
Build Snort 3 from source.
```

---

# 2. Project Folder Preparation

Inside the GitHub project repo:

```bash
cd ~/netsentry-gateway
mkdir -p snort/build snort/rules snort/config snort/alerts snort/tests
```

Created install notes:

```text
snort/tests/snort3-install-notes.md
```

---

# 3. Build Dependencies Installed

Installed required build packages:

```bash
sudo apt update
sudo apt install -y \
build-essential cmake make gcc g++ flex bison \
libpcap-dev libpcre2-dev libdumbnet-dev zlib1g-dev \
libluajit-5.1-dev libssl-dev pkg-config hwloc libhwloc-dev \
liblzma-dev libunwind-dev uuid-dev git wget curl \
autoconf libtool
```

Verified build tools:

```bash
gcc --version
cmake --version
git --version
```

Confirmed:

```text
gcc: 14.2.0
cmake: 3.31.6
git: 2.47.3
```

---

# 4. DAQ Built From Source

Snort requires DAQ for packet acquisition.

Commands used:

```bash
cd ~/netsentry-gateway/snort/build
git clone https://github.com/snort3/libdaq.git
cd libdaq
./bootstrap
./configure
make
sudo make install
sudo ldconfig
```

DAQ installed successfully.

---

# 5. Snort 3 Built From Source

Commands used:

```bash
cd ~/netsentry-gateway/snort/build
git clone https://github.com/snort3/snort3.git
cd snort3
./configure_cmake.sh --prefix=/usr/local
cd build
make -j$(nproc)
sudo make install
sudo ldconfig
```

Validated with:

```bash
snort -V
```

Confirmed:

```text
Snort++ / Snort 3 works
Snort version: 3.12.2.0
DAQ version: 3.0.27
```

---

# 6. First Snort Rule: ICMP Detection

Created local rules file:

```text
snort/rules/local.rules
```

Initial ICMP rule:

```snort
alert icmp !192.168.1.11 any -> 192.168.1.17 any (
msg:"Netsentry ICMP ping detected";
sid:10000001;
rev:2;
)
```

Purpose:

```text
Detect ICMP/ping traffic from non-admin clients.
Exclude admin laptop 192.168.1.11 to avoid alert spam.
```

Tested Snort config:

```bash
sudo snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i wlx200db0220b9a \
-T
```

Ran Snort live:

```bash
sudo snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i wlx200db0220b9a \
-A alert_fast
```

Generated traffic:

```bash
ping 192.168.1.17
```

Result:

```text
Snort generated ICMP alerts successfully.
```

---

# 7. SSH Detection Rules

Added SSH SYN probe detection.

Single SSH SYN probe rule:

```snort
alert tcp !192.168.1.11 any -> 192.168.1.17 22 (
msg:"SSH Connection attempt From no Admin detected";
flags:S;
sid:10000002;
rev:2;
)
```

Repeated SSH SYN / brute-force style rule:

```snort
alert tcp !192.168.1.11 any -> 192.168.1.17 22 (
msg:"SSH SCAN/Brute-force potential detected";
flags:S;
detection_filter:track by_src, count 10, seconds 60;
sid:10000003;
rev:2;
)
```

Important learning:

```text
A normal SSH connection attempt and an nmap probe can both look like a TCP SYN to port 22.
So “SSH SYN probe” is more technically accurate than “SSH session.”
```

Also learned:

```text
Snort can detect the attempt even if iptables later blocks it.
```

This is correct because:

```text
Packet reaches the interface
Snort sees it
iptables blocks unauthorized access
```

---

# 8. AdGuard UI Detection Rule

AdGuard UI runs on:

```text
3001/tcp
```

Rule:

```snort
alert tcp !192.168.1.11 any -> 192.168.1.17 3001 (
msg:"AD-Guard UI access attempt";
flags:S;
sid:10000004;
rev:4;
)
```

Purpose:

```text
Detect non-admin attempts to access the AdGuard web UI.
```

Expected result:

```text
iptables blocks the request
Snort alerts on the attempt
```

Result:

```text
Worked.
```

---

# 9. DNS Blocked Domains Discussion

Question asked:

```text
Can Snort alert on all AdGuard-blocked domains?
```

Conclusion:

```text
Snort is not the right source for “all blocked domains.”
AdGuard knows what it blocked.
Snort only sees DNS packets.
```

Correct future architecture:

```text
Snort → network/security behavior alerts
AdGuard → blocked DNS domain events
Python watcher/dashboard → combine both later
```

Decision:

```text
Do not duplicate AdGuard blocklists into Snort rules.
Use AdGuard logs/API later for blocked-domain dashboard alerts.
```

Optional generic DNS visibility rule was discussed, but blocked-domain detection should come from AdGuard later.

---

# 10. Alert Output to File

Goal:

```text
Save Snort alerts to a file so Python can read them.
```

Tried using:

```bash
sudo snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i wlx200db0220b9a \
-A alert_fast \
-l ~/netsentry-gateway/snort/alerts
```

Problem:

```text
No alert file was created by this method.
```

Working solution:

```bash
sudo snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i wlx200db0220b9a \
-A alert_fast | tee -a ~/netsentry-gateway/snort/alerts/alert_fast.txt
```

Result:

```text
alert_fast.txt was created and contained detections.
```

---

# 11. Buffering Problem and stdbuf Fix

Problem:

```text
Python watcher worked at first, then froze on a half-written alert line.
```

Cause:

```text
Snort/tee output buffering caused incomplete lines to be written.
```

Fix:

```bash
sudo stdbuf -oL -eL snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i wlx200db0220b9a \
-A alert_fast | stdbuf -oL tee -a ~/netsentry-gateway/snort/alerts/alert_fast.txt
```

Result:

```text
Line buffering fixed the partial-line freeze.
```

This became the standard Snort run command.

---

# 12. Python Alert Watcher

Created:

```text
scripts/snort_alert_watcher.py
```

Purpose:

```text
Watch alert_fast.txt
Read new Snort alerts live
Parse alert fields
Print clean alert output
Write structured JSONL alerts
```

Fields parsed:

```text
received_at
snort_time
sid
rev
priority
proto
src
dst
message
raw
```

Output file:

```text
snort/alerts/alerts.jsonl
```

Important behavior:

```text
By default, watcher starts at the end of alert_fast.txt and only shows new alerts.
--from-start can read old alerts from the beginning.
```

Confirmed:

```text
Python watcher reads Snort alerts successfully.
Python watcher writes structured alerts to alerts.jsonl.
```

---

# 13. Flask Dashboard

Installed Flask:

```bash
sudo apt update
sudo apt install python3-flask -y
```

Created:

```text
scripts/netsentry_dashboard.py
```

Purpose:

```text
Read alerts.jsonl
Show latest alerts in browser
Auto-refresh every 5 seconds
Show total alert count
Show latest source
Show latest protocol
```

Dashboard URL:

```text
http://192.168.1.17:5050
```

Confirmed:

```text
Dashboard works from admin laptop.
Dashboard displays Snort alerts.
```

---

# 14. Dashboard Firewall Protection

Dashboard should only be accessible from admin laptop:

```text
192.168.1.11
```

iptables rules added:

```bash
sudo iptables -I INPUT 7 -p tcp -s 192.168.1.11 --dport 5050 -j ACCEPT
sudo iptables -I INPUT 8 -p tcp --dport 5050 -j DROP
```

Result:

```text
Admin laptop can access dashboard.
Non-admin clients are blocked.
```

---

# 15. Snort Rule for Dashboard Access Attempts

Added rule:

```snort
alert tcp !192.168.1.11 any -> 192.168.1.17 5050 (
msg:"NETSENTRY Dashboard access attempt from non-admin detected";
flags:S;
sid:10000006;
rev:1;
)
```

Test:

```bash
curl http://192.168.1.17:5050
```

Expected:

```text
iptables blocks non-admin dashboard access.
Snort detects the access attempt.
Python watcher parses the alert.
Dashboard displays the alert.
```

Result:

```text
Worked.
```

This completed the loop:

```text
Dashboard is protected
Unauthorized access attempt to dashboard becomes visible inside the dashboard
```

---

# 16. Final Working Pipeline

Final confirmed architecture:

```text
Snort 3
  ↓
alert_fast.txt
  ↓
Python watcher
  ↓
alerts.jsonl
  ↓
Flask dashboard
  ↓
Admin browser
```

Current run commands:

## Terminal 1 — Snort

```bash
cd ~/netsentry-gateway

sudo stdbuf -oL -eL snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i wlx200db0220b9a \
-A alert_fast | stdbuf -oL tee -a ~/netsentry-gateway/snort/alerts/alert_fast.txt
```

## Terminal 2 — Watcher

```bash
cd ~/netsentry-gateway
python3 scripts/snort_alert_watcher.py
```

## Terminal 3 — Dashboard

```bash
cd ~/netsentry-gateway
python3 scripts/netsentry_dashboard.py
```

Browser:

```text
http://192.168.1.17:5050
```

---

# 17. Current Confirmed Detections

| Detection | Status |
|---|---|
| ICMP from non-admin | Works |
| SSH SYN from non-admin | Works |
| Repeated SSH SYN / possible brute force | Works |
| AdGuard UI access attempt from non-admin | Works |
| Dashboard access attempt from non-admin | Works |
| Raw alert file output | Works |
| Python alert parsing | Works |
| JSONL structured alert output | Works |
| Dashboard display | Works |
| Dashboard firewall protection | Works |

---

# 18. Important Files Created or Modified

Source/config/docs:

```text
snort/rules/local.rules
scripts/snort_alert_watcher.py
scripts/netsentry_dashboard.py
snort/tests/snort3-install-notes.md
snort/tests/snort3-build-and-validation.md
snort/tests/snort-rules-test-results.md
docs/netsentry-v0-alert-pipeline.md
docs/dashboard-v0.md
docs/day-snort3-alert-dashboard.md
.gitignore
```

Runtime files not meant for GitHub:

```text
snort/build/
snort/alerts/alert_fast.txt
snort/alerts/alerts.jsonl
```

These should stay ignored.

---

# 19. Final Assessment

This is the first complete NetSentry V0 IDS alert stack.

It is not full gateway IDS yet.

It is:

```text
Host-facing IDS + firewall-protected dashboard + structured alert pipeline
```

The system now proves:

```text
Unauthorized traffic can be blocked by iptables.
The same attempt can be detected by Snort.
Snort alerts can be parsed by Python.
Structured alerts can be displayed in a local web dashboard.
The dashboard itself can be protected and monitored.
```

This is a real blue-team lab milestone.
