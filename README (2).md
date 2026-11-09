# Debolat AI

**Understand what's slowing your Windows PC, in plain English, and clean it up safely.**

Debolat AI scans your RAM, storage and startup apps, then uses the AI of your choice to explain what each item is, how confident it is, and what you could do about it. You approve every action. Nothing is removed, closed or changed without your confirmation.

> Version 1.0 · Windows 10/11 · Early release

## Why it's different
- **Real data only.** Every number comes from Windows itself. The AI never invents sizes, dates or usage.
- **It says when it's unsure.** If the AI doesn't know what something is, it says so instead of guessing.
- **You stay in control.** Folders go to the Recycle Bin, startup entries are backed up before removal, and uninstalling launches the app's own uninstaller.
- **Bring your own AI.** Connect Gemini, OpenAI, Claude, OpenRouter, or a local model through Ollama. Scanning sends nothing anywhere; only the item you click "Show AI Explanation" on is sent.

## Features
- **RAM:** every running app grouped together (all of Chrome's processes in one row), plus an honest line for memory no app owns.
- **Storage:** drive usage bars, a whole-drive scan, and drill-down into any folder.
- **Startup:** apps that launch with Windows (registry Run entries).
- **Watchlist:** pick apps to watch; get asked what to do when one goes unused for too long.
- **Connect AI:** one panel, a "Get API key" button per provider, keys stored encrypted on your PC.

## Install
Download `DebolatAI-Setup-1.0.0.exe` from the [Releases](../../releases) page and run it.
Windows may show a SmartScreen warning because the installer isn't code-signed yet: choose **More info → Run anyway**.

## Known limitations (v1.0)
- Windows only.
- Startup scan covers registry Run entries only (not the Startup folder or Task Scheduler).
- "Last used" detection relies on Windows' UserAssist data and can't find every app.
- The installer is unsigned, so SmartScreen warns on first run.

## Build from source
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
npm install
npm start
```
Build the installer with `build.bat` (output goes to `release\`).
Optional: copy `.env.example` to `.env` to use a developer Gemini key while developing.

## How it works
Windows data → Python scanners → (only when you click) your chosen AI → Electron UI → confirmed actions.
Adding a new AI provider is one entry in `providers.py`.

## License
Copyright (c) 2026 Y. Kushal Goud. All rights reserved.
You may use the installed app for personal use and view the source code, but you may not copy,
modify, redistribute or sell it. See [LICENSE](LICENSE) for the full terms.
