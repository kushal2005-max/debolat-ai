r"""
Debolat AI - where the app keeps its own small data files.

An installed app is not allowed to write next to its own program files, so
the watchlist and the startup-removal backup must live in the user's own
app-data folder. The Electron app passes that folder in through the
DEBOLAT_DATA_DIR environment variable when running as an installed app.

While developing from source (no variable set) files stay next to the scripts,
exactly as before, so nothing changes for the dev workflow.
"""

import os


def data_dir():
    folder = os.environ.get("DEBOLAT_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        pass
    return folder


def data_path(filename):
    return os.path.join(data_dir(), filename)
