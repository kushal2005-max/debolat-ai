r"""
Debolat AI - On-Demand Item Explanation
Explains exactly ONE item (a process, folder, or startup entry) via the
AI. This is called fresh each time the user clicks "Show AI Explanation"
on a specific item - not run automatically during scanning. This is what
keeps quota usage tied to what the user actually wants explained, instead
of spending it on every scanned item whether they look at it or not.

Usage:
    python explain_item.py '<json payload>'

Payload shape:
    {"category": "ram", "data": {"name": "...", "exe_path": "...", "process_count": 3, "ram_mb": 45.6}}
    {"category": "storage", "data": {"name": "...", "path": "...", "size_gb": 1.2}}
    {"category": "startup", "data": {"name": "...", "command": "...", "scope": "..."}}

Prints the AI's JSON result (explanation, confidence, recommendation,
item_type, reasoning) to stdout. Progress/errors go to stderr.
"""

import sys
import json

from ai_engine import ask_ai


def build_process_context(proc):
    # A RAM item is now an app GROUP (e.g. all of chrome.exe's processes).
    lines = [f"Process name: {proc['name']}"]
    if proc.get("exe_path"):
        lines.append(f"Executable path: {proc['exe_path']}")
    if proc.get("process_count", 1) > 1:
        lines.append(f"Number of running processes of this app: {proc['process_count']}")
    lines.append(f"RAM usage (all of this app's processes combined): {proc['ram_mb']} MB")
    return "\n".join(lines)


def build_folder_context(folder):
    return (
        f"Folder name: {folder['name']}\n"
        f"Full path: {folder['path']}\n"
        f"Size: {folder['size_gb']} GB"
    )


def build_startup_context(item):
    return (
        f"Startup entry name: {item['name']}\n"
        f"Command: {item['command']}\n"
        f"Scope: {item['scope']} (runs at every Windows login for this scope)"
    )


BUILDERS = {
    "ram": build_process_context,
    "storage": build_folder_context,
    "startup": build_startup_context,
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No payload provided"}))
        sys.exit(1)

    try:
        payload = json.loads(sys.argv[1])
        category = payload["category"]
        data = payload["data"]
    except (json.JSONDecodeError, KeyError) as e:
        print(json.dumps({"error": f"Invalid payload: {e}"}))
        sys.exit(1)

    builder = BUILDERS.get(category)
    if builder is None:
        print(json.dumps({"error": f"Unknown category: {category}"}))
        sys.exit(1)

    context = builder(data)
    result = ask_ai(context)  # no cache_key - this is a single, fresh call
    print(json.dumps(result))
