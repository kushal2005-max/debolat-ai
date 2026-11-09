r"""
Debolat AI - Apply Actions
Actually performs the actions the user confirmed in the Review Selection
modal. This is the ONLY file that does anything destructive - everything
else in the app is read-only. Every function here is called only after
explicit per-item user confirmation in the UI.

Safety choices (deliberate, not defaults):
- Folders are sent to the Recycle Bin (send2trash), never permanently
  deleted. The user can recover them if something goes wrong.
- Processes get a graceful terminate() first, and are only force-killed
  if they don't exit within a short timeout.
- Startup registry entries are backed up to a local JSON log BEFORE being
  removed, since Windows has no "recycle bin" for the registry. This
  doesn't auto-restore them, but the information isn't silently lost.

Usage:
    python apply_actions.py '<json array of actions>'

Each action:
    {"category": "ram", "name": "...", "pid": 123}
    {"category": "storage", "name": "...", "path": "..."}
    {"category": "startup", "name": "...", "command": "...", "scope": "..."}

Prints a JSON array of results to stdout: [{category, name, success, error?}]
"""

import sys
import os
import json
import time
import psutil

try:
    from send2trash import send2trash
except ImportError:
    send2trash = None

try:
    import winreg
except ImportError:
    winreg = None

from app_paths import data_path

STARTUP_BACKUP_LOG = data_path("startup_removals_backup.json")


def kill_process_action(action):
    pid = action["pid"]
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except psutil.TimeoutExpired:
            proc.kill()  # didn't exit gracefully - force it
            proc.wait(timeout=3)
        return {"success": True}
    except psutil.NoSuchProcess:
        # Already gone - treat as success, not an error, since the
        # user's goal (process not running) is already achieved.
        return {"success": True}
    except (psutil.AccessDenied, Exception) as e:
        return {"success": False, "error": str(e)}


import re

# Top-level system locations that must never be sent to the Recycle Bin, even if
# a request asks for it (the UI blocks them too - this is the second guard).
_PROTECTED = re.compile(
    r"^[a-z]:\\?(windows|program files|program files \(x86\)|programdata|users|"
    r"system volume information|\$recycle\.bin|recovery|boot)?$", re.IGNORECASE)


def _is_protected(path):
    return bool(_PROTECTED.match(os.path.normpath(path).rstrip("\\/") or path))


def delete_folder_action(action):
    path = action["path"]
    if _is_protected(path):
        return {"success": False, "error": "This is a protected system folder and cannot be removed here."}
    if send2trash is None:
        return {"success": False, "error": "send2trash is not installed - run: pip install send2trash"}
    try:
        send2trash(path)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _backup_startup_entry(item):
    """Appends the entry being removed to a local JSON log, so the
    information isn't lost even though there's no automatic undo."""
    entry = {
        "name": item["name"],
        "command": item["command"],
        "scope": item["scope"],
        "removed_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    existing = []
    if os.path.exists(STARTUP_BACKUP_LOG):
        try:
            with open(STARTUP_BACKUP_LOG, "r") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []

    existing.append(entry)
    with open(STARTUP_BACKUP_LOG, "w") as f:
        json.dump(existing, f, indent=2)


def remove_startup_action(action):
    if winreg is None:
        return {"success": False, "error": "winreg is not available (not running on Windows)"}

    name = action["name"]
    scope = action["scope"]

    hive = winreg.HKEY_CURRENT_USER if scope == "Current User" else winreg.HKEY_LOCAL_MACHINE
    subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        _backup_startup_entry(action)  # back up BEFORE deleting
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
        return {"success": True}
    except FileNotFoundError:
        # Already removed - treat as success for the same reason as above.
        return {"success": True}
    except PermissionError:
        return {"success": False, "error": "Permission denied - try running as administrator for 'All Users' entries"}
    except Exception as e:
        return {"success": False, "error": str(e)}


HANDLERS = {
    "ram": kill_process_action,
    "storage": delete_folder_action,
    "startup": remove_startup_action,
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps([{"error": "No actions provided"}]))
        sys.exit(1)

    try:
        actions = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps([{"error": f"Invalid actions payload: {e}"}]))
        sys.exit(1)

    results = []
    for action in actions:
        category = action.get("category")
        handler = HANDLERS.get(category)

        if handler is None:
            results.append({
                "category": category,
                "name": action.get("name"),
                "success": False,
                "error": f"Unknown category: {category}"
            })
            continue

        outcome = handler(action)
        results.append({
            "category": category,
            "name": action.get("name"),
            **outcome
        })

    print(json.dumps(results))
