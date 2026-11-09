r"""
Debolat AI - Watchlist JSON helpers
Thin wrappers so the Electron UI can read/add/remove watchlist entries
as JSON, without each needing a dedicated hand-rolled script.

Usage:
    python watchlist_json.py list
    python watchlist_json.py add '<json app data>'
    python watchlist_json.py remove '<app name>'
"""

import sys
import json

from watchlist_manager import load_watchlist, add_watched_app, remove_watched_app
from userassist_scanner import get_userassist_entries
from installed_apps_scanner import _find_last_used


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No command given"}))
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        print(json.dumps(load_watchlist()))

    elif command == "add":
        app = json.loads(sys.argv[2])
        userassist_entries = get_userassist_entries()
        last_used, _, _ = _find_last_used(app, userassist_entries)

        entry = add_watched_app(
            name=app["name"],
            install_location=app.get("install_location", ""),
            initial_last_used_iso=last_used,
            uninstall_string=app.get("uninstall_string", ""),
            threshold_days=app.get("threshold_days", 21)
        )
        print(json.dumps(entry))

    elif command == "remove":
        remove_watched_app(sys.argv[2])
        print(json.dumps({"success": True}))

    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
