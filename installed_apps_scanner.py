r"""
Debolat AI - Installed Apps Scanner

Reads the SAME data Windows' own Settings > Apps page uses: the
registry's "Uninstall" keys. This gives a clean, real list of installed
programs (name, publisher, install location, estimated size) - not
folder-name guessing, not noisy raw launch records.

Each installed app is then cross-referenced against UserAssist's last-run
data (userassist_scanner.py) by matching install paths, to attach a real
"last used" date where one can be found. If no matching launch record
exists, last_used stays None - never guessed.
"""

import sys
import os

try:
    import winreg
except ImportError:
    winreg = None

from userassist_scanner import get_userassist_entries

UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") if winreg else None,
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall") if winreg else None,
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") if winreg else None,
]


def _read_value(key, name, default=None):
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return value
    except FileNotFoundError:
        return default


def get_installed_apps():
    """
    Returns a list of dicts: name, publisher, install_location,
    estimated_size_gb (None if Windows doesn't have an estimate),
    uninstall_string. Only real, user-visible apps - entries Windows
    itself marks as hidden system components are excluded.
    """
    if winreg is None:
        print("Installed apps scanning requires Windows.", file=sys.stderr)
        return []

    apps = []
    seen_names = set()

    for entry in UNINSTALL_KEYS:
        if entry is None:
            continue
        hive, subkey_path = entry

        try:
            with winreg.OpenKey(hive, subkey_path) as root_key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(root_key, i)
                        i += 1
                    except OSError:
                        break

                    try:
                        with winreg.OpenKey(root_key, subkey_name) as app_key:
                            name = _read_value(app_key, "DisplayName")
                            if not name:
                                continue  # no display name - not a real user-facing app

                            is_system_component = _read_value(app_key, "SystemComponent", 0)
                            if is_system_component == 1:
                                continue  # Windows itself hides these from Add/Remove Programs

                            if name in seen_names:
                                continue  # same app registered under multiple keys
                            seen_names.add(name)

                            install_location = _read_value(app_key, "InstallLocation", "")
                            publisher = _read_value(app_key, "Publisher", "Unknown")
                            uninstall_string = _read_value(app_key, "UninstallString", "")

                            size_kb = _read_value(app_key, "EstimatedSize")
                            size_gb = round(size_kb / (1024 ** 2), 3) if size_kb else None

                            apps.append({
                                "name": name,
                                "publisher": publisher,
                                "install_location": install_location,
                                "estimated_size_gb": size_gb,
                                "uninstall_string": uninstall_string
                            })
                    except OSError:
                        continue
        except (FileNotFoundError, PermissionError):
            continue

    return apps


def _normalize_for_fuzzy_match(text):
    """Lowercase, alphanumeric-only - for loose name comparison only.
    This is NOT exact matching; it can be wrong, which is why fuzzy
    matches are labeled separately from exact path matches."""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _find_last_used(app, userassist_entries):
    """
    Looks for a UserAssist entry that corresponds to this app, in two
    passes:
    1. EXACT: the app's install_location appears as a substring of a
       full-path UserAssist entry. High confidence - a real path match.
    2. FUZZY (fallback only): the app's name loosely matches an app-ID
       or shortcut-style UserAssist entry (common for apps launched via
       Start Menu tiles or packaged apps, which UserAssist doesn't
       record with a real file path). Lower confidence - flagged as such.

    Returns (last_run_iso, days_since, match_type) where match_type is
    "exact", "approximate", or None if nothing was found - never guessed
    as a specific type when no match exists.
    """
    install_loc = app.get("install_location", "")
    app_name_norm = _normalize_for_fuzzy_match(app.get("name", ""))

    # Pass 1: exact path match
    if install_loc:
        install_loc_norm = os.path.normpath(install_loc).lower()
        best_exact = None
        for entry in userassist_entries:
            if "\\" not in entry["name"]:
                continue  # not a path-style entry - skip for exact pass
            name_norm = os.path.normpath(entry["name"]).lower()
            if install_loc_norm in name_norm and entry["last_run"]:
                if best_exact is None or (entry["days_since_run"] is not None and
                                            entry["days_since_run"] < best_exact["days_since_run"]):
                    best_exact = entry
        if best_exact:
            return best_exact["last_run"], best_exact["days_since_run"], "exact"

    # Pass 2: fuzzy fallback - only if an exact match wasn't found
    if len(app_name_norm) >= 4:  # avoid matching on very short/generic names
        best_fuzzy = None
        for entry in userassist_entries:
            if not entry["last_run"]:
                continue
            # Compare against the last path segment (for .lnk/path entries)
            # or the whole string (for app-ID style entries).
            tail = entry["name"].split("\\")[-1] if "\\" in entry["name"] else entry["name"]
            tail_norm = _normalize_for_fuzzy_match(tail)

            if app_name_norm in tail_norm or tail_norm in app_name_norm:
                if best_fuzzy is None or (entry["days_since_run"] is not None and
                                            entry["days_since_run"] < best_fuzzy["days_since_run"]):
                    best_fuzzy = entry
        if best_fuzzy:
            return best_fuzzy["last_run"], best_fuzzy["days_since_run"], "approximate"

    return None, None, None


def get_apps_with_last_used():
    """
    Returns installed apps enriched with last_used/days_since_used where
    a matching launch record was found via UserAssist.
    """
    apps = get_installed_apps()
    userassist_entries = get_userassist_entries()

    for app in apps:
        last_used, days_since, match_type = _find_last_used(app, userassist_entries)
        app["last_used"] = last_used
        app["days_since_used"] = days_since
        app["match_type"] = match_type  # "exact", "approximate", or None

    apps.sort(key=lambda a: (a["days_since_used"] is None, -(a["days_since_used"] or 0)))
    return apps


if __name__ == "__main__":
    if "--json" in sys.argv:
        import json
        print(json.dumps(get_apps_with_last_used()))
    else:
        print("=== Installed Apps (with last-used where found) ===\n")
        for app in get_apps_with_last_used():
            size_str = f"{app['estimated_size_gb']:.2f} GB" if app['estimated_size_gb'] else "size unknown"
            if app['days_since_used'] is not None:
                tag = " (approx)" if app['match_type'] == "approximate" else ""
                used_str = f"{app['days_since_used']} days ago{tag}"
            else:
                used_str = "no usage record found"
            print(f"{app['name']:<45} {size_str:>14}   last used: {used_str}")
