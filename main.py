r"""
Debolat AI - End-to-End Pipeline (JSON output mode, scan-only)

Runs real scans (RAM, storage, startup apps) and prints a single JSON
object to stdout for the Electron frontend. Scanning is pure local data
collection - fast and free (no API quota). Nothing is capped: every app,
every folder and every startup entry is returned; the UI decides how to
fold long lists, never the scanner.

AI explanations are fetched LAZILY, one item at a time, only when the user
clicks "Show AI Explanation" - see explain_item.py.
"""

import sys
import os
import json

from ram_scanner import get_all_ram_apps, get_total_ram_usage
from storage_scanner import get_drives, scan_children
from startup_scanner import get_startup_items


def run_ram_scan():
    print("Scanning all running processes...", file=sys.stderr)
    totals = get_total_ram_usage()
    scan = get_all_ram_apps()

    # Honest reconciliation: what apps account for vs. what the OS reports as
    # used. The remainder is kernel / drivers / compressed memory / cache -
    # memory that no process list can attribute to an app.
    other_mb = round(max(0.0, totals["used_mb"] - scan["accounted_mb"]), 2)

    return {
        "total_gb": totals["total_gb"],
        "used_gb": totals["used_gb"],
        "percent_used": totals["percent_used"],
        "accounted_mb": scan["accounted_mb"],
        "system_other_mb": other_mb,
        "unreadable_processes": scan["unreadable_processes"],
        "apps": scan["apps"],  # raw: name, exe_path, ram_mb, process_count, pids
    }


def run_storage_scan(target_path):
    print(f"Scanning storage under: {target_path}", file=sys.stderr)
    drives = get_drives()
    children = scan_children(target_path)

    if "error" in children:
        return {"scanned_path": target_path, "drives": drives, "folders": [],
                "denied": 0, "cloud_only_skipped": 0, "error": children["error"]}

    return {
        "scanned_path": target_path,
        "drives": drives,
        "folders": [x for x in children["entries"] if x["is_dir"]],  # all of them
        "denied": children["denied"],
        "cloud_only_skipped": children["cloud_only_skipped"],
    }


def run_startup_scan():
    print("Scanning startup apps...", file=sys.stderr)
    return {"items": get_startup_items()}  # raw: name, command, scope - all of them


if __name__ == "__main__":
    default_path = os.path.join(os.path.expanduser("~"), "AppData", "Local")
    target_path = sys.argv[1] if len(sys.argv) > 1 else default_path

    result = {
        "ram": run_ram_scan(),
        "storage": run_storage_scan(target_path),
        "startup": run_startup_scan(),
    }

    print(json.dumps(result))
