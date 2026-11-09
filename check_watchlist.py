r"""
Debolat AI - Watchlist Checker

Re-checks every watched app against FRESH UserAssist data. If a watched
app has been used more recently than our stored baseline, the baseline
is updated (the neglect clock resets). If an app has gone past its
threshold with no new activity, and isn't currently snoozed, it's
reported as due for a nag.

This is designed to be run periodically (eventually via Windows Task
Scheduler - see project notes), but can also just be run manually to
check right now.

Prints a JSON list of apps due for a nag to stdout (for Electron/future
notification code to consume). Diagnostic info goes to stderr.
"""

import sys
import json
import os
from datetime import datetime, timezone

from watchlist_manager import load_watchlist, update_last_used
from userassist_scanner import get_userassist_entries
from installed_apps_scanner import _find_last_used


def _parse_iso(iso_str):
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str)
    except ValueError:
        return None


def check_all_watched_apps():
    watchlist = load_watchlist()
    if not watchlist:
        print("Nothing is being watched.", file=sys.stderr)
        return []

    userassist_entries = get_userassist_entries()
    now = datetime.now(timezone.utc)
    due_for_nag = []

    for entry in watchlist:
        app_stub = {"name": entry["name"], "install_location": entry["install_location"]}
        fresh_last_used, fresh_days_since, match_type = _find_last_used(app_stub, userassist_entries)

        stored_baseline = _parse_iso(entry["last_confirmed_used"])
        fresh_timestamp = _parse_iso(fresh_last_used)

        # If fresh data shows more recent activity than what we had stored,
        # the app has been used again - update the baseline and move on.
        if fresh_timestamp and (stored_baseline is None or fresh_timestamp > stored_baseline):
            update_last_used(entry["name"], fresh_last_used)
            print(f"{entry['name']}: fresh activity found, baseline updated.", file=sys.stderr)
            continue

        # Figure out how long it's actually been neglected, from whichever
        # baseline we have: last confirmed use, or when we started watching.
        reference_point = stored_baseline or _parse_iso(entry["watch_started"])
        if reference_point is None:
            continue  # shouldn't happen, but don't crash on bad data

        days_neglected = (now - reference_point).total_seconds() / 86400

        # Respect an active snooze.
        snoozed_until = _parse_iso(entry["snoozed_until"])
        if snoozed_until and now < snoozed_until:
            print(f"{entry['name']}: snoozed until {entry['snoozed_until']}.", file=sys.stderr)
            continue

        if days_neglected >= entry["threshold_days"]:
            due_for_nag.append({
                "name": entry["name"],
                "days_neglected": round(days_neglected, 1),
                "threshold_days": entry["threshold_days"],
                "uninstall_string": entry.get("uninstall_string", "")
            })

    return due_for_nag


if __name__ == "__main__":
    results = check_all_watched_apps()
    print(json.dumps(results))
