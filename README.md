# Debolat AI

Explains what is using your Windows PC's RAM, storage and startup, in plain English,
and lets you decide what to clean up. Nothing is changed without your confirmation.

## For users
Download `DebolatAI-Setup-x.y.z.exe`, double-click it, done. No Python or other tools needed.
Open the app, click **Connect AI** (top right) and follow the steps to connect the AI you prefer.

## For developers

### Run from source
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
npm install
npm start
```
Optional: copy `.env.example` to `.env` and add a Gemini key as a developer fallback.

### Build the installer
Double-click `build.bat` (or run it in a terminal). It
1. compiles the Python backend into `backend.exe` (PyInstaller),
2. self-tests it,
3. packages everything into `release\DebolatAI-Setup-<version>.exe` (electron-builder).

Change the version in `package.json` before each release.

### Where things are stored (installed app)
`%APPDATA%\Debolat AI\` holds the watchlist, the startup-removal backup and the (encrypted) AI key.
Uninstalling does not delete this folder.

### Adding another AI provider
Add one entry to `PROVIDERS` in `providers.py` (and one `_call_*` function if it is not
OpenAI-compatible). The Connect AI panel builds itself from that list.
