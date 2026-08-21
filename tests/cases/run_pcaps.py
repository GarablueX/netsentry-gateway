#!/usr/bin/env python3
"""
Reads each ID/ID.pcap in tests/cases and runs it through tcpdump.

Usage:
    python run_pcaps.py            # process all pcaps
    python run_pcaps.py 10000001   # process a single id
"""

import subprocess
import sys
from pathlib import Path

CASES_DIR = Path(__file__).parent


def run_pcap(pcap_path: Path) -> int:
    """Run a single pcap file through tcpdump -r."""
    print(f"\n{'=' * 60}")
    print(f"Running tcpdump on: {pcap_path}")
    print('=' * 60)
    result = subprocess.run(
        ["sudo", "tcpdump", "-r", str(pcap_path)],
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
    pcaps = []

    if case_id:
        pcap = CASES_DIR / case_id / f"{case_id}.pcap"
        if pcap.exists():
            pcaps.append(pcap)
        else:
            print(f"PCAP not found: {pcap}", file=sys.stderr)
            return 1
    else:
        pcaps = sorted(CASES_DIR.glob("*/id.pcap".replace("id", "*")))
        # More explicit glob: each subdir has <id>.pcap
        pcaps = sorted(CASES_DIR.glob("*/*.pcap"))

    if not pcaps:
        print("No pcap files found.", file=sys.stderr)
        return 1

    failures = 0
    for pcap in pcaps:
        if run_pcap(pcap) != 0:
            failures += 1

    print(f"\n{'=' * 60}")
    print(f"Processed {len(pcaps)} pcap(s), {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
