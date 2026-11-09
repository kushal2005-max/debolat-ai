r"""
Debolat AI - Watchlist Manager

Stores the small, user-chosen list of apps to watch for neglect. Unlike
installed_apps_scanner.py (which tries to find historical usage for
EVERY installed app), this only cares about apps the user explicitly
picked, starting from the moment they picked them - no backfilling,
no guessing about the past.

Each watched app stores:
- name, install_location (for future re-matching)
- watch_started: when the user added it (ISO date)
- last_confirmed_used: the most recent usage timestamp we've found,
  either at watch-start time (if one existed) or from a later check.
  None means "no usage seen since we started watching, or ever."
- threshold_days: how many days of no activity before this counts as neglected
- snoozed_until: an ISO date the user picked when dismissing a nag,
  or None if not currently snoozed
"""

import os
import json
from datetime import datetime, timezone

from app_paths import data_path

WATCHLIST_PATH = data_path("watchlist.json")


def load_watchlist():
    if not os.path.exists(WATCHLIST_PATH):
        return []
    try:
        with open(WATCHLIST_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_watchlist(entries):
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def add_watched_app(name, install_location, initial_last_used_iso, uninstall_string="", threshold_days=21):
    """
    Adds an app to the watchlist. initial_last_used_iso is whatever
    last-used date we found at the moment of adding it (or None if no
    record was found) - this becomes the starting baseline, not
    something re-derived from deep history later. uninstall_string is
    stored now so the nag's "Uninstall" button works later without
    needing to re-scan installed apps at nag time.
    """
    entries = load_watchlist()

    # Don't add the same app twice - update its settings instead.
    for entry in entries:
        if entry["name"] == name:
            entry["threshold_days"] = threshold_days
            save_watchlist(entries)
            return entry

    new_entry = {
        "name": name,
        "install_location": install_location,
        "uninstall_string": uninstall_string,
        "watch_started": datetime.now(timezone.utc).isoformat(),
        "last_confirmed_used": initial_last_used_iso,  # may be None
        "threshold_days": threshold_days,
        "snoozed_until": None
    }
    entries.append(new_entry)
    save_watchlist(entries)
    return new_entry


def remove_watched_app(name):
    entries = load_watchlist()
    entries = [e for e in entries if e["name"] != name]
    save_watchlist(entries)


def snooze_watched_app(name, snooze_until_iso):
    entries = load_watchlist()
    for entry in entries:
        if entry["name"] == name:
            entry["snoozed_until"] = snooze_until_iso
    save_watchlist(entries)


def update_last_used(name, new_last_used_iso):
    """Called by the periodic checker when fresh activity is found."""
    entries = load_watchlist()
    for entry in entries:
        if entry["name"] == name:
            entry["last_confirmed_used"] = new_last_used_iso
            entry["snoozed_until"] = None  # using it again clears any snooze
    save_watchlist(entries)


if __name__ == "__main__":
    print("=== Current Watchlist ===\n")
    entries = load_watchlist()
    if not entries:
        print("Nothing being watched yet.")
    for e in entries:
        baseline = e["last_confirmed_used"] or f"never (watching since {e['watch_started']})"
        print(f"{e['name']} - threshold {e['threshold_days']}d - last used: {baseline}")
