# Snort 3 Build and Validation

## Goal

Install Snort 3 from source on the Debian NetSentry V0 machine and validate that it can detect traffic hitting the host.

## Why Snort 3 Was Built From Source

Debian APT did not provide a `snort3` package.

Tested command:

```bash
sudo apt install snort3 -y
```

Result:

```text
Unable to locate package snort3
```

Decision:

- Do not add unstable Debian repositories.
- Do not install random `.deb` packages from unknown sources.
- Build Snort 3 from official source in a controlled way.

## Environment

| Item | Value |
|---|---|
| Debian NetSentry IP | `192.168.1.17` |
| Admin laptop IP | `192.168.1.11` |
| LAN | `192.168.1.0/24` |
| Active interface | `wlx200db0220b9a` |
| Project path | `~/netsentry-gateway` |

## Build Dependencies

The following dependencies were installed:

```bash
sudo apt update
sudo apt install -y \
build-essential cmake make gcc g++ flex bison \
libpcap-dev libpcre2-dev libdumbnet-dev zlib1g-dev \
libluajit-5.1-dev libssl-dev pkg-config hwloc libhwloc-dev \
liblzma-dev libunwind-dev uuid-dev git wget curl \
autoconf libtool
```

Build tools were verified with:

```bash
gcc --version
cmake --version
git --version
```

Confirmed versions:

```text
gcc: 14.2.0
cmake: 3.31.6
git: 2.47.3
```

## DAQ Build

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

## Snort 3 Build

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

## Installation Validation

Command used:

```bash
snort -V
```

Confirmed result:

```text
Snort++ / Snort 3 installed successfully
Snort version: 3.12.2.0
DAQ version: 3.0.27
```

## First Rule Validation

Local rule file:

```text
~/netsentry-gateway/snort/rules/local.rules
```

First validation rule:

```snort
alert icmp !192.168.1.11 any -> 192.168.1.17 any (
msg:"Netsentry ICMP ping detected";
sid:10000001;
rev:2;
)
```

Configuration test command:

```bash
sudo snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i wlx200db0220b9a \
-T
```

Live test command:

```bash
cd ~/netsentry-gateway

sudo stdbuf -oL -eL snort -c /usr/local/etc/snort/snort.lua \
-R ~/netsentry-gateway/snort/rules/local.rules \
-i wlx200db0220b9a \
-A alert_fast | stdbuf -oL tee -a ~/netsentry-gateway/snort/alerts/alert_fast.txt
```

Traffic generated from a non-admin test device:

```bash
ping 192.168.1.17
```

Result:

```text
Snort generated an ICMP alert.
```

## Important Note About Buffering

Initial alert output worked in the terminal, but the Python watcher later froze on partial lines.

Cause:

```text
Snort/tee output buffering caused incomplete alert lines to be written.
```

Fix:

```bash
sudo stdbuf -oL -eL snort ...
```

and:

```bash
stdbuf -oL tee -a ~/netsentry-gateway/snort/alerts/alert_fast.txt
```

This forced line-buffered output and fixed the watcher issue.

## Current Status

Snort 3 is installed and validated.

Confirmed:

- Snort 3 runs successfully.
- DAQ works.
- Local rule file loads.
- ICMP alert works.
- Alert output can be written to `alert_fast.txt`.
- Buffered output issue was fixed with `stdbuf`.

## Interpretation

Snort 3 is now ready to act as the IDS engine for NetSentry V0.

At this stage, Snort is a host-facing IDS. It detects traffic hitting the Debian NetSentry machine itself.

It is not yet full gateway IDS because NetSentry is not yet forwarding all LAN traffic.
