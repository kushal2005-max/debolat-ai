r"""
Debolat AI - backend dispatcher (the program PyInstaller turns into backend.exe).

The Electron app used to run "python <script>.py args". In the installed app
there is no Python, so it runs "backend.exe <script> args" instead and this
file starts the matching script exactly as if it had been run directly
(same sys.argv, same __main__ behaviour, same stdout JSON).
"""

import sys
import runpy

# Only these scripts may be started - the app never runs arbitrary names.
SCRIPTS = {
    "main", "explain_item", "apply_actions", "check_watchlist", "respond_to_nag",
    "installed_apps_scanner", "watchlist_json", "connect_ai", "scan_folder",
}


def run():
    if len(sys.argv) < 2 or sys.argv[1] not in SCRIPTS:
        print('{"error": "Unknown backend script"}')
        sys.exit(2)
    script = sys.argv[1]
    sys.argv = [script + ".py"] + sys.argv[2:]
    try:
        runpy.run_module(script, run_name="__main__", alter_sys=True)
    except SystemExit:
        raise
    except Exception as e:  # never die silently: the app shows this message
        import json, traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)


if __name__ == "__main__":
    run()
