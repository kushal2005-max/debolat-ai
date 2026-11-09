# PyInstaller recipe for backend.exe  (run by build.bat - see README)
# One-folder build on purpose: a one-file build unpacks itself to a temp
# folder on EVERY launch, and the app starts the backend many times.
from PyInstaller.utils.hooks import collect_submodules

hidden = [
    "main", "explain_item", "apply_actions", "check_watchlist", "respond_to_nag",
    "installed_apps_scanner", "watchlist_json", "connect_ai", "scan_folder",
    "ram_scanner", "storage_scanner", "startup_scanner", "userassist_scanner",
    "steam_scanner", "watchlist_manager", "ai_engine", "providers", "app_paths",
    "psutil", "requests", "send2trash", "vdf", "winreg",
]
hidden += collect_submodules("google.genai")
hidden += collect_submodules("send2trash")

a = Analysis(
    ["backend_entry.py"],
    pathex=["."],
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL", "IPython", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="backend",
    console=True,          # needed: Electron reads the JSON the program prints
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="backend", upx=False)
