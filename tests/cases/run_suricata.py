#!/usr/bin/env python3
"""
Runs Suricata against each ID/ID.pcap in tests/cases and saves output
to that ID directory.

Default command:
    sudo suricata -r <pcaps_dir>/<id>/<id>.pcap \\
        -S /etc/suricata/rules/local.rules \\
        -c /etc/suricata/suricata.yaml \\
        -k none

Usage:
    python run_suricata.py            # process all pcaps
    python run_suricata.py 10000001   # process a single id
"""

import subprocess
import sys
from pathlib import Path

CASES_DIR = Path(__file__).parent

# --- configurable paths ---
SURICATA_RULES = "/home/gbx/netsentry-gateway/suricata/rules/local.rules"
SURICATA_CONFIG = "/etc/suricata/suricata.yaml"
# ------------------------------------------------------------------


def run_suricata(pcap_path: Path, case_dir: Path) -> int:
    """
    Run Suricata on a single pcap file.

    -r : read pcap
    -S : rules file
    -c : suricata.yaml
    -k none : disable checksum validation
    -l : set log directory (here: the case dir so output lands alongside the pcap)
    """
    print(f"\n{'=' * 60}")
    print(f"Running Suricata on: {pcap_path}")
    print(f"Output dir:           {case_dir}")
    print('=' * 60)

    result = subprocess.run(
        [
            "sudo", "suricata",
            "-r", str(pcap_path),
            "-S", SURICATA_RULES,
            "-c", SURICATA_CONFIG,
            "-k", "none",
            "-l", str(case_dir),          # <-- output goes into the id directory
        ],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print(f"[stderr]: {result.stderr}", file=sys.stderr)
    print(f"[exit code: {result.returncode}]")
    return result.returncode


def main():
    case_id = sys.argv[1] if len(sys.argv) > 1 else None
    targets = []

    if case_id:
        case_dir = CASES_DIR / case_id
        pcap = case_dir / f"{case_id}.pcap"
        if pcap.exists():
            targets.append((pcap, case_dir))
        else:
            print(f"PCAP not found: {pcap}", file=sys.stderr)
            return 1
    else:
        # every subdirectory that contains a .pcap
        for case_dir in sorted(CASES_DIR.iterdir()):
            if not case_dir.is_dir():
                continue
            pcap = case_dir / f"{case_dir.name}.pcap"
            if pcap.exists():
                targets.append((pcap, case_dir))

    if not targets:
        print("No pcap files found.", file=sys.stderr)
        return 1

    failures = 0
    for pcap, case_dir in targets:
        if run_suricata(pcap, case_dir) != 0:
            failures += 1

    print(f"\n{'=' * 60}")
    print(f"Processed {len(targets)} pcap(s), {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
