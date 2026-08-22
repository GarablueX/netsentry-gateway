import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# Directory containing this script and the SID directories.
CASES_DIR = Path(__file__).resolve().parent


# Suricata configuration.
SURICATA_RULES = Path(
    "/home/gbx/netsentry-gateway/suricata/rules/local.rules"
)

SURICATA_CONFIG = Path(
    "/etc/suricata/suricata.yaml"
)


def find_case_dirs() -> list[Path]:
    """
    Return all valid case directories.

    A valid case directory looks like:

        100000125/
            100000125.pcap
    """

    cases = []

    for directory in sorted(CASES_DIR.iterdir()):
        if not directory.is_dir():
            continue

        pcap = directory / f"{directory.name}.pcap"

        if pcap.exists():
            cases.append(directory)

    return cases


def run_suricata_temp(pcap_path: Path) -> tuple[int, Path, str]:
    """
    Run Suricata against a PCAP using a fresh temporary log directory.

    Returns:

        (return_code, temporary_directory, diagnostic_message)
    """

    tmpdir = Path(
        tempfile.mkdtemp(
            prefix=f"suricata_{pcap_path.parent.name}_"
        )
    )

    cmd = [
        "sudo",
        "suricata",
        "-r", str(pcap_path),
        "-S", str(SURICATA_RULES),
        "-c", str(SURICATA_CONFIG),
        "-k", "none",
        "-l", str(tmpdir),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

    except FileNotFoundError as exc:
        return (
            -1,
            tmpdir,
            f"Command not found: {exc}",
        )

    if result.returncode != 0:

        diagnostic = result.stderr.strip()

        if not diagnostic:
            diagnostic = result.stdout.strip()

        if not diagnostic:
            diagnostic = f"Suricata exited with code {result.returncode}"

        return (
            result.returncode,
            tmpdir,
            diagnostic,
        )

    return (
        result.returncode,
        tmpdir,
        "",
    )


def load_eve_json(path: Path) -> list[dict] | None:
    """
    Parse Suricata eve.json.

    Suricata EVE is normally newline-delimited JSON:

        {...}
        {...}
        {...}

    It is NOT one large JSON array.
    """

    if not path.exists():
        print(
            f"ERROR: {path} does not exist",
            file=sys.stderr,
        )
        return None

    events = []

    try:

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            for line_number, line in enumerate(
                file,
                start=1,
            ):

                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)

                except json.JSONDecodeError as exc:

                    print(
                        f"ERROR: invalid JSON in "
                        f"{path}:{line_number}: {exc}",
                        file=sys.stderr,
                    )

                    return None

                events.append(event)

    except OSError as exc:

        print(
            f"ERROR: unable to read {path}: {exc}",
            file=sys.stderr,
        )

        return None

    return events


def extract_alert_sids(events: list[dict]) -> list[int]:
    """
    Extract Suricata alert.signature_id values from EVE events.
    """

    sids = []

    for event in events:

        if event.get("event_type") != "alert":
            continue

        alert = event.get("alert")

        if not isinstance(alert, dict):
            continue

        sid = alert.get("signature_id")

        if isinstance(sid, int):
            sids.append(sid)

    return sids


def validate_case(
    case_id: str,
    eve_path: Path,
) -> bool:
    """
    Validate one Suricata case.

    PASS conditions:

        expected SID appears at least once

    AND

        no different SID appears.
    """

    try:
        expected_sid = int(case_id)

    except ValueError:

        print(
            f"[{case_id}] ERROR: directory name "
            f"is not a numeric SID",
            file=sys.stderr,
        )

        return False

    events = load_eve_json(eve_path)

    if events is None:

        print(
            f"[{case_id}] ERROR: could not parse eve.json",
            file=sys.stderr,
        )

        return False

    actual_sids = extract_alert_sids(events)

    if not actual_sids:

        print(
            f"[{case_id}] FAIL — no Suricata alerts triggered"
        )

        return False

    unique_sids = sorted(set(actual_sids))

    if expected_sid not in unique_sids:

        print(
            f"[{case_id}] FAIL — expected SID "
            f"{expected_sid} did not trigger"
        )

        print(
            f"    triggered SIDs: {unique_sids}"
        )

        return False

    unexpected_sids = [
        sid
        for sid in unique_sids
        if sid != expected_sid
    ]

    if unexpected_sids:

        print(
            f"[{case_id}] FAIL — unexpected rules triggered"
        )

        print(
            f"    expected SID:   {expected_sid}"
        )

        print(
            f"    triggered SIDs: {unique_sids}"
        )

        print(
            f"    unexpected:     {unexpected_sids}"
        )

        return False

    count = actual_sids.count(expected_sid)

    print(
        f"[{case_id}] PASS — SID {expected_sid} "
        f"triggered {count} time(s)"
    )

    return True


def check_configuration() -> bool:
    """
    Verify required Suricata files exist before running tests.
    """

    ok = True

    if not SURICATA_RULES.exists():

        print(
            f"ERROR: rules file not found:\n"
            f"  {SURICATA_RULES}",
            file=sys.stderr,
        )

        ok = False

    if not SURICATA_CONFIG.exists():

        print(
            f"ERROR: Suricata config not found:\n"
            f"  {SURICATA_CONFIG}",
            file=sys.stderr,
        )

        ok = False

    return ok


def main() -> int:

    if not check_configuration():
        return 2

    # Optional SID argument.
    case_filter = (
        sys.argv[1]
        if len(sys.argv) > 1
        else None
    )

    case_dirs = find_case_dirs()

    if case_filter:

        case_dirs = [
            directory
            for directory in case_dirs
            if directory.name == case_filter
        ]

        if not case_dirs:

            print(
                f"ERROR: case '{case_filter}' not found",
                file=sys.stderr,
            )

            return 2

    if not case_dirs:

        print(
            f"ERROR: no valid test cases found in "
            f"{CASES_DIR}",
            file=sys.stderr,
        )

        return 2

    passed = 0
    failed = 0
    exec_errors = 0

    for case_dir in case_dirs:

        case_id = case_dir.name

        pcap_path = (
            case_dir /
            f"{case_id}.pcap"
        )

        print()
        print("=" * 60)
        print(f"Testing SID: {case_id}")
        print(f"PCAP:        {pcap_path}")

        exit_code, tmpdir, error = run_suricata_temp(
            pcap_path
        )

        try:

            if exit_code != 0:

                print(
                    f"[{case_id}] ERROR — Suricata failed",
                    file=sys.stderr,
                )

                print(
                    error,
                    file=sys.stderr,
                )

                exec_errors += 1
                continue

            eve_path = tmpdir / "eve.json"

            if not eve_path.exists():

                print(
                    f"[{case_id}] ERROR — Suricata did "
                    f"not produce eve.json",
                    file=sys.stderr,
                )

                exec_errors += 1
                continue

            if validate_case(
                case_id,
                eve_path,
            ):

                passed += 1

            else:

                failed += 1

        finally:

            shutil.rmtree(
                tmpdir,
                ignore_errors=True,
            )

    print()
    print("=" * 60)
    print("SURICATA TEST RESULTS")
    print("=" * 60)

    print(f"Total:       {len(case_dirs)}")
    print(f"Passed:      {passed}")
    print(f"Failed:      {failed}")
    print(f"Exec errors: {exec_errors}")

    if exec_errors > 0:
        return 2

    if failed > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())