r"""
Debolat AI - UserAssist Scanner (EXPERIMENTAL - needs validation)

Reads the Windows "UserAssist" registry keys, which track programs
launched from the Start Menu / Desktop, including a run count and (in
newer Windows versions) a last-execution timestamp.

IMPORTANT HONESTY NOTE: UserAssist is NOT officially documented by
Microsoft. Everything about its binary value format comes from the
digital-forensics community reverse-engineering it over the years. The
byte offsets used below (run count at bytes 4-7, last-run FILETIME at
byte offset 60 in a 72-byte value) match the most commonly cited "Version
5" format used since Windows 7, but this has NOT been verified against
your specific Windows build. Treat this script's output as a hypothesis
to check against what you actually remember using - not as ground truth
- until you've confirmed it lines up with reality.

Key names are ROT13-encoded by Windows itself (a deliberate, documented
obfuscation, not a bug) - this script decodes that part, which IS
reliable. It's the timestamp decoding inside the value that's uncertain.
"""

import sys
import codecs
import struct
import time
from datetime import datetime, timedelta

try:
    import winreg
except ImportError:
    winreg = None

# These two GUIDs are the commonly documented UserAssist buckets:
# one for directly-run executables, one for shortcut-based launches.
USERASSIST_GUIDS = [
    r"{CEBFF5CD-ACE2-4F4F-9178-9926F41749EA}",  # direct .exe launches
    r"{F4E57C4B-2036-45F0-A9AB-443BCFE33D9F}",  # shortcut (.lnk) launches
]

FILETIME_EPOCH = datetime(1601, 1, 1)


def _rot13_path(name):
    """UserAssist value names are ROT13-encoded path strings. Non-letter
    characters (backslashes, braces, colons) pass through unchanged."""
    return codecs.encode(name, "rot13")


def _filetime_to_datetime(filetime_int):
    """Converts a Windows FILETIME (100ns intervals since 1601-01-01)
    into a Python datetime. Returns None for 0 (never recorded)."""
    if filetime_int <= 0:
        return None
    try:
        return FILETIME_EPOCH + timedelta(microseconds=filetime_int / 10)
    except (OverflowError, OSError):
        return None  # corrupted/implausible value - don't guess a date


def _decode_value(raw_bytes):
    """
    Attempts to decode the UserAssist binary blob (Version 5 format,
    Windows 7+). Returns (run_count, last_run_datetime) or (None, None)
    if the blob isn't the expected 72-byte structure - we do NOT guess
    at a different layout.
    """
    if len(raw_bytes) != 72:
        return None, None

    try:
        run_count = struct.unpack_from("<I", raw_bytes, 4)[0]
        filetime_int = struct.unpack_from("<Q", raw_bytes, 60)[0]
        last_run = _filetime_to_datetime(filetime_int)
        return run_count, last_run
    except struct.error:
        return None, None


def get_userassist_entries():
    """
    Returns a list of dicts: name (decoded program path/name), run_count,
    last_run (datetime or None), days_since_run (float or None).
    Returns an empty list if not on Windows or the registry path is
    unreadable.
    """
    if winreg is None:
        print("UserAssist scanning requires Windows (winreg not available).", file=sys.stderr)
        return []

    entries = []
    now = datetime.utcnow()

    for guid in USERASSIST_GUIDS:
        subkey = rf"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist\{guid}\Count"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as key:
                i = 0
                while True:
                    try:
                        raw_name, raw_value, _ = winreg.EnumValue(key, i)
                        i += 1
                    except OSError:
                        break  # no more values

                    decoded_name = _rot13_path(raw_name)
                    # Skip internal Explorer bookkeeping entries - not real programs.
                    if decoded_name.startswith("UEME_CTLSESSION"):
                        continue

                    run_count, last_run = _decode_value(raw_value)

                    days_since = None
                    if last_run is not None:
                        days_since = round((now - last_run).total_seconds() / 86400, 1)

                    entries.append({
                        "name": decoded_name,
                        "run_count": run_count,
                        "last_run": last_run.isoformat() if last_run else None,
                        "days_since_run": days_since
                    })
        except (FileNotFoundError, PermissionError) as e:
            print(f"Could not read {subkey}: {e}", file=sys.stderr)
            continue

    entries.sort(key=lambda e: (e["days_since_run"] is None, -(e["days_since_run"] or 0)))
    return entries


if __name__ == "__main__":
    print("=== UserAssist Entries (EXPERIMENTAL - verify before trusting) ===\n")
    for entry in get_userassist_entries():
        last_run_str = entry["last_run"] if entry["last_run"] else "unknown/never decoded"
        days_str = f" ({entry['days_since_run']} days ago)" if entry["days_since_run"] is not None else ""
        print(f"{entry['name']}")
        print(f"    Run count: {entry['run_count']}, Last run: {last_run_str}{days_str}\n")
