"""
Debolat AI - Startup App Scanner
Lists apps configured to launch at Windows startup, by reading the
registry's Run keys (both current-user and all-users scopes).

Note: this covers the most common startup mechanism (registry Run keys).
It does NOT yet cover the Windows Startup folder (shortcut files) or
Task Scheduler-based autostarts - those are a possible future addition.
"""

import sys


def _get_winreg():
    try:
        import winreg
        return winreg
    except ImportError:
        return None


def get_startup_items():
    """
    Returns a list of dicts: name, command, scope ("Current User" or "All Users").
    Returns an empty list (with a stderr note) if not running on Windows.
    """
    winreg = _get_winreg()
    if winreg is None:
        print("Startup scanning requires Windows (winreg module not available).",
              file=sys.stderr)
        return []

    locations = [
        (winreg.HKEY_CURRENT_USER,
         r"Software\Microsoft\Windows\CurrentVersion\Run",
         "Current User"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"Software\Microsoft\Windows\CurrentVersion\Run",
         "All Users"),
    ]

    items = []
    for hive, subkey, scope in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                i = 0
                while True:
                    try:
                        name, command, _ = winreg.EnumValue(key, i)
                        items.append({
                            "name": name,
                            "command": command,
                            "scope": scope
                        })
                        i += 1
                    except OSError:
                        break  # no more values in this key
        except (FileNotFoundError, PermissionError):
            continue  # key doesn't exist or isn't readable - skip it

    return items


if __name__ == "__main__":
    print("=== Startup Apps (Registry Run Keys) ===\n")
    for item in get_startup_items():
        print(f"[{item['scope']}] {item['name']}")
        print(f"    {item['command']}\n")
