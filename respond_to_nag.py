r"""
Debolat AI - Respond to Nag
Performs whatever the user chose when shown a "you haven't used X in a
while" prompt: launch the real uninstaller, snooze for 1-2 weeks, or
stop watching the app entirely.

"Uninstall" does NOT silently delete anything itself - it launches the
app's own registered uninstaller (the same one Windows Settings would
run) and lets the user interact with it normally. This keeps the final
confirmation with the app's own uninstaller UI, not something Debolat
AI fakes.

Usage:
    python respond_to_nag.py '<json payload>'

Payload:
    {"name": "...", "action": "uninstall", "uninstall_string": "..."}
    {"name": "...", "action": "snooze_1_week"}
    {"name": "...", "action": "snooze_2_weeks"}
    {"name": "...", "action": "stop_watching"}
"""

import sys
import json
import subprocess
from datetime import datetime, timedelta, timezone

from watchlist_manager import snooze_watched_app, remove_watched_app


def handle_uninstall(name, uninstall_string):
    if not uninstall_string:
        return {"success": False, "error": "No uninstaller registered for this app."}
    try:
        # Launch the app's own real uninstaller - we don't control or
        # parse what happens next; the user interacts with it directly,
        # same as running it from Windows Settings themselves.
        subprocess.Popen(uninstall_string, shell=True)
        remove_watched_app(name)  # no need to keep watching something being removed
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_snooze(name, days):
    snooze_until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    snooze_watched_app(name, snooze_until)
    return {"success": True}


def handle_stop_watching(name):
    remove_watched_app(name)
    return {"success": True}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No payload provided"}))
        sys.exit(1)

    try:
        payload = json.loads(sys.argv[1])
        name = payload["name"]
        action = payload["action"]
    except (json.JSONDecodeError, KeyError) as e:
        print(json.dumps({"success": False, "error": f"Invalid payload: {e}"}))
        sys.exit(1)

    if action == "uninstall":
        result = handle_uninstall(name, payload.get("uninstall_string"))
    elif action == "snooze_1_week":
        result = handle_snooze(name, 7)
    elif action == "snooze_2_weeks":
        result = handle_snooze(name, 14)
    elif action == "stop_watching":
        result = handle_stop_watching(name)
    else:
        result = {"success": False, "error": f"Unknown action: {action}"}

    print(json.dumps(result))
