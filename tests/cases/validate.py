#!/usr/bin/env python3
"""
Validate Suricata test cases.

For each ID directory in tests/cases/:
  1. Verify the pcap exists at ID/<id>.pcap
  2. Run Suricata in a fresh temporary directory
  3. Parse the newly generated eve.json
  4. Compare it against the existing (old) eve.json in the ID directory

Exit codes:
  0 — all cases passed
  1 — one or more eve.json mismatches
  2 — execution / configuration error
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CASES_DIR = Path(__file__).parent

# --- configurable paths (mirrors run_suricata.py) ---
SURICATA_RULES = "/home/gbx/netsentry-gateway/suricata/rules/local.rules"
SURICATA_CONFIG = "/etc/suricata/suricata.yaml"


def find_case_dirs() -> list[Path]:
    """Return every sub-directory in cases/ that contains a <id>.pcap."""
    cases = []
    for d in sorted(CASES_DIR.iterdir()):
        if d.is_dir() and (d / f"{d.name}.pcap").exists():
            cases.append(d)
    return cases


def run_suricata_temp(pcap_path: Path) -> tuple[int, Path]:
    """
    Run Suricata in a temporary directory on the given pcap.

    Returns (exit_code, temp_dir_path).
    """
    tmpdir = Path(tempfile.mkdtemp(prefix=f"suricata_{pcap_path.parent.name}_"))
    result = subprocess.run(
        [
            "sudo", "suricata",
            "-r", str(pcap_path),
            "-S", SURICATA_RULES,
            "-c", SURICATA_CONFIG,
            "-k", "none",
            "-l", str(tmpdir),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode, tmpdir


def load_eve_json(path: Path) -> list | None:
    """Load eve.json; return None on error."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def compare_eve(new_eve: Path, old_eve: Path, case_id: str) -> bool:
    """
    Compare new vs old eve.json.

    Returns True if they match, False otherwise.
    """
    new_data = load_eve_json(new_eve)
    old_data = load_eve_json(old_eve)

    if new_data is None:
        print(f"[{case_id}] ERROR: could not parse new eve.json", file=sys.stderr)
        return False
    if old_data is None:
        print(f"[{case_id}] WARNING: no existing eve.json to compare — saving new one")
        # copy new eve.json into the case dir so it becomes the baseline
        shutil.copy2(new_eve, old_eve)
        return True

    if new_data == old_data:
        print(f"[{case_id}] PASS — eve.json matches")
        return True
    else:
        print(f"[{case_id}] FAIL — eve.json mismatch")
        # Show a brief diff summary
        if isinstance(new_data, list) and isinstance(old_data, list):
            print(f"   new entries: {len(new_data)}, old entries: {len(old_data)}")
        return False



def main():
    case_id_filter = sys.argv[1] if len(sys.argv) > 1 else None
    case_dirs = find_case_dirs()

    if case_id_filter:
        case_dirs = [d for d in case_dirs if d.name == case_id_filter]
        if not case_dirs:
            print(f"ERROR: case '{case_id_filter}' not found", file=sys.stderr)
            return 2

    if not case_dirs:
        print("No valid case directories found.", file=sys.stderr)
        return 2

    mismatches = 0
    exec_errors = 0

    for case_dir in case_dirs:
        case_id = case_dir.name
        pcap = case_dir / f"{case_id}.pcap"

        if not pcap.exists():
            print(f"[{case_id}] ERROR: pcap not found at {pcap}", file=sys.stderr)
            exec_errors += 1
            continue

        print(f"\n{'=' * 60}")
        print(f"Validating case: {case_id}")
        print(f"  pcap: {pcap}")

        # --- run Suricata in temp dir ---
        exit_code, tmpdir = run_suricata_temp(pcap)

        if exit_code != 0:
            print(f"[{case_id}] ERROR: Suricata exited with code {exit_code}", file=sys.stderr)
            shutil.rmtree(tmpdir, ignore_errors=True)
            exec_errors += 1
            continue

        new_eve = tmpdir / "eve.json"
        old_eve = case_dir / "eve.json"

        if not new_eve.exists():
            print(f"[{case_id}] ERROR: Suricata did not produce eve.json", file=sys.stderr)
            shutil.rmtree(tmpdir, ignore_errors=True)
            exec_errors += 1
            continue

        if not compare_eve(new_eve, old_eve, case_id):
            mismatches += 1

        # cleanup temp dir
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\n{'=' * 60}")
    print(f"Results: {len(case_dirs)} case(s) checked")
    print(f"  mismatches: {mismatches}")
    print(f"  exec errors: {exec_errors}")

    if exec_errors > 0:
        return 2
    if mismatches > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
