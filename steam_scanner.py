r"""
Debolat AI - Steam Last-Played Scanner

Reads Steam's OWN local data files to find installed games, their disk
size, and their exact last-played timestamp. This is real, Steam-tracked
data - not a file-access-time guess.

Data sources (both are plain Valve Data Format / VDF text files):
- steamapps/appmanifest_<appid>.acf   -> installed game name + size on disk
- userdata/<id>/config/localconfig.vdf -> per-game LastPlayed (unix time)

Requires the `vdf` package: pip install vdf
"""

import os
import sys
import glob
import time

try:
    import vdf
except ImportError:
    vdf = None

try:
    import winreg
except ImportError:
    winreg = None


def find_steam_path():
    """Finds the Steam install folder via registry, falling back to the
    common default install location if the registry lookup fails."""
    if winreg:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                path, _ = winreg.QueryValueEx(key, "SteamPath")
                return os.path.normpath(path)
        except (FileNotFoundError, OSError):
            pass

    default = r"C:\Program Files (x86)\Steam"
    return default if os.path.isdir(default) else None


def find_library_folders(steam_path):
    """Returns every Steam library folder (games can be installed across
    multiple drives) by reading libraryfolders.vdf, plus the main install
    folder itself."""
    libraries = [steam_path]

    vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
    if vdf is None or not os.path.isfile(vdf_path):
        return libraries

    try:
        with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
            data = vdf.load(f)
        folders = data.get("libraryfolders", {})
        for key, entry in folders.items():
            if isinstance(entry, dict) and "path" in entry:
                lib_path = os.path.normpath(entry["path"])
                if lib_path not in libraries:
                    libraries.append(lib_path)
    except Exception as e:
        print(f"Could not parse libraryfolders.vdf: {e}", file=sys.stderr)

    return libraries


def get_installed_games(libraries):
    """Returns installed games as a dict: {appid: {name, size_gb}} by
    reading each library's appmanifest_*.acf files."""
    games = {}

    for library in libraries:
        steamapps_dir = os.path.join(library, "steamapps")
        if not os.path.isdir(steamapps_dir):
            continue

        for manifest_path in glob.glob(os.path.join(steamapps_dir, "appmanifest_*.acf")):
            try:
                with open(manifest_path, "r", encoding="utf-8", errors="ignore") as f:
                    data = vdf.load(f)
                app_state = data.get("AppState", {})
                appid = app_state.get("appid")
                name = app_state.get("name")
                size_bytes = int(app_state.get("SizeOnDisk", 0))

                if appid and name:
                    games[str(appid)] = {
                        "name": name,
                        "size_gb": round(size_bytes / (1024 ** 3), 3)
                    }
            except Exception as e:
                print(f"Could not parse {manifest_path}: {e}", file=sys.stderr)

    return games


def get_last_played_times(steam_path):
    """Returns {appid: last_played_unix_timestamp} by reading the first
    found user's localconfig.vdf. Apps with no recorded play time are
    simply absent from the result - never guessed."""
    last_played = {}

    userdata_dir = os.path.join(steam_path, "userdata")
    if not os.path.isdir(userdata_dir):
        return last_played

    user_folders = [f for f in os.listdir(userdata_dir)
                     if os.path.isdir(os.path.join(userdata_dir, f)) and f.isdigit()]
    if not user_folders:
        return last_played

    config_path = os.path.join(userdata_dir, user_folders[0], "config", "localconfig.vdf")
    if not os.path.isfile(config_path):
        return last_played

    try:
        with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
            data = vdf.load(f)

        apps = (data.get("UserLocalConfigStore", {})
                    .get("Software", {})
                    .get("Valve", {})
                    .get("Steam", {})
                    .get("apps", {}))

        for appid, entry in apps.items():
            if isinstance(entry, dict) and "LastPlayed" in entry:
                try:
                    last_played[str(appid)] = int(entry["LastPlayed"])
                except (ValueError, TypeError):
                    continue
    except Exception as e:
        print(f"Could not parse localconfig.vdf: {e}", file=sys.stderr)

    return last_played


def get_steam_games_with_last_played():
    """Returns a list of dicts: name, appid, size_gb, last_played_unix
    (None if never recorded), days_since_played (None if never recorded).
    Returns an empty list (with a stderr note) if Steam isn't found or
    the vdf package isn't installed.
    """
    if vdf is None:
        print("The 'vdf' package is required (pip install vdf).", file=sys.stderr)
        return []

    steam_path = find_steam_path()
    if not steam_path:
        print("Steam installation not found.", file=sys.stderr)
        return []

    libraries = find_library_folders(steam_path)
    games = get_installed_games(libraries)
    last_played = get_last_played_times(steam_path)

    now = time.time()
    results = []
    for appid, info in games.items():
        last_played_unix = last_played.get(appid)
        days_since = None
        if last_played_unix is not None:
            days_since = round((now - last_played_unix) / 86400, 1)

        results.append({
            "name": info["name"],
            "appid": appid,
            "size_gb": info["size_gb"],
            "last_played_unix": last_played_unix,
            "days_since_played": days_since
        })

    results.sort(key=lambda g: (g["days_since_played"] is None, -(g["days_since_played"] or 0)))
    return results


if __name__ == "__main__":
    print("=== Steam Games - Last Played ===\n")
    for game in get_steam_games_with_last_played():
        if game["days_since_played"] is not None:
            played_str = f"{game['days_since_played']} days ago"
        else:
            played_str = "never recorded"
        print(f"{game['name']:<40} {game['size_gb']:>8.2f} GB   last played: {played_str}")
