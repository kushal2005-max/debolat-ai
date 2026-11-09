/*
 * Debolat AI - Electron Main Process
 *
 * Creates the app window and runs the Python backend (main.py) as a
 * subprocess whenever the frontend asks for a scan. This is the bridge
 * that lets the webpage talk to your real scanner + AI code.
 *
 * (Connect AI: the user's own AI + key is stored encrypted - see the
 * "Connect AI" section near the bottom. The .env Gemini keys are now only a
 * developer fallback.)
 *
 * API keys now come from a local ".env" file in this same folder (see
 * loadEnvFile below) instead of needing $env: set in PowerShell every
 * session. Create a file named exactly ".env" here with:
 *     GEMINI_API_KEY=your-key-here
 *     GEMINI_API_KEY_2=your-second-key-here
 * This file is loaded automatically on launch - no terminal setup needed
 * beyond this one-time file.
 */

const { app, BrowserWindow, ipcMain, shell, safeStorage, Menu } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// ---------------------------------------------------------------------
// How the Python backend is started.
//
//  - While developing (npm start): .venv\Scripts\python.exe <script>.py
//  - Installed app (packaged by electron-builder): there is NO Python on the
//    user's PC. The backend was compiled into resources\backend\backend.exe
//    (see backend.spec) and is started as:  backend.exe <script-name> args
//
// backendCommand() hides that difference from every call site below.
// ---------------------------------------------------------------------
const PYTHON_EXE = path.join(__dirname, '.venv', 'Scripts', 'python.exe');
const BACKEND_EXE = path.join(process.resourcesPath || '', 'backend', 'backend.exe');

function script(name) { return path.join(__dirname, `${name}.py`); }

function backendCommand(scriptPath) {
  if (app.isPackaged) {
    return { cmd: BACKEND_EXE, prefix: [path.basename(scriptPath, '.py')] };
  }
  return { cmd: PYTHON_EXE, prefix: [scriptPath] };
}

// Environment every backend process gets. Installed apps cannot write next to
// their own files, so the backend is told to keep its data (watchlist, backups)
// in the user's app-data folder.
function backendEnv(extra) {
  const env = { ...process.env, PYTHONUTF8: '1', ...(extra || {}) };
  if (app.isPackaged) env.DEBOLAT_DATA_DIR = app.getPath('userData');
  return env;
}

function spawnBackend(scriptPath, args, extraEnv) {
  const { cmd, prefix } = backendCommand(scriptPath);
  return spawn(cmd, [...prefix, ...args], { env: backendEnv(extraEnv), windowsHide: true });
}

const MAIN_PY = script('main');
const EXPLAIN_ITEM_PY = script('explain_item');
const APPLY_ACTIONS_PY = script('apply_actions');
const CHECK_WATCHLIST_PY = script('check_watchlist');
const RESPOND_TO_NAG_PY = script('respond_to_nag');
const INSTALLED_APPS_PY = script('installed_apps_scanner');
const WATCHLIST_JSON_PY = script('watchlist_json');
const CONNECT_AI_PY = script('connect_ai');
const SCAN_FOLDER_PY = script('scan_folder');
const ENV_FILE = path.join(__dirname, '.env');

// Minimal .env file loader - no extra npm package needed. Reads KEY=VALUE
// lines (skipping blank lines and lines starting with #) and sets them
// into process.env, so the Python subprocess inherits them automatically.
function loadEnvFile() {
  if (!fs.existsSync(ENV_FILE)) {
    console.warn(`No .env file found at ${ENV_FILE} - GEMINI_API_KEY must be set another way.`);
    return;
  }

  const lines = fs.readFileSync(ENV_FILE, 'utf-8').split('\n');
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;

    const eqIndex = line.indexOf('=');
    if (eqIndex === -1) continue;

    const key = line.slice(0, eqIndex).trim();
    const value = line.slice(eqIndex + 1).trim();
    if (key) process.env[key] = value;
  }
}

if (!app.isPackaged) loadEnvFile();   // .env keys are a developer fallback only

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 780,
    minWidth: 860,
    minHeight: 600,
    title: 'Debolat AI',
    backgroundColor: '#F3F5F1',   // matches the app, so there is no white flash on start
    show: false,
    autoHideMenuBar: true,
    icon: path.join(__dirname, 'build', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (app.isPackaged) Menu.setApplicationMenu(null);   // no File/Edit/View bar in the installed app
  win.once('ready-to-show', () => win.show());
  win.loadFile(path.join(__dirname, 'index.html'));
}

// Runs "python main.py <targetPath>" and resolves with the parsed JSON
// result, or rejects with a readable error message.
function runPythonScan(targetPath) {
  return new Promise((resolve, reject) => {
    const args = [];
    if (targetPath) args.push(targetPath);

    const proc = spawnBackend(MAIN_PY, args);

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    proc.stderr.on('data', (chunk) => { stderr += chunk.toString(); });

    proc.on('error', (err) => {
      reject(`Could not start Python process: ${err.message}`);
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(`Python exited with code ${code}.\n${stderr}`);
        return;
      }
      try {
        const result = JSON.parse(stdout.trim());
        resolve(result);
      } catch (e) {
        reject(`Could not parse Python output as JSON.\nRaw output:\n${stdout}\n\nStderr:\n${stderr}`);
      }
    });
  });
}

// Generic helper: runs a Python script with ONE json-string argv argument
// and resolves with its parsed stdout JSON.
function runPythonJson(scriptPath, jsonPayload, extraEnv) {
  return new Promise((resolve, reject) => {
    const proc = spawnBackend(scriptPath, [JSON.stringify(jsonPayload)], extraEnv);

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    proc.stderr.on('data', (chunk) => { stderr += chunk.toString(); });

    proc.on('error', (err) => {
      reject(`Could not start Python process: ${err.message}`);
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(`Python exited with code ${code}.\n${stderr}`);
        return;
      }
      try {
        resolve(JSON.parse(stdout.trim()));
      } catch (e) {
        reject(`Could not parse Python output as JSON.\nRaw output:\n${stdout}\n\nStderr:\n${stderr}`);
      }
    });
  });
}

// Exposed to the renderer via preload.js -> window.api.runScan(path)
ipcMain.handle('run-scan', async (event, targetPath) => {
  try {
    const result = await runPythonScan(targetPath);
    return { success: true, data: result };
  } catch (errorMessage) {
    return { success: false, error: errorMessage };
  }
});

// Lazy, per-item AI explanation - only called when the user clicks
// "Show AI Explanation" on a specific item.
ipcMain.handle('explain-item', async (event, { category, data }) => {
  try {
    const result = await runPythonJson(EXPLAIN_ITEM_PY, { category, data }, activeAiEnv());
    return { success: true, data: result };
  } catch (errorMessage) {
    return { success: false, error: errorMessage };
  }
});

// Applies confirmed destructive actions (kill process / trash folder /
// remove startup entry). Only called after explicit user confirmation
// in the Review Selection modal.
ipcMain.handle('apply-actions', async (event, actions) => {
  try {
    const result = await runPythonJson(APPLY_ACTIONS_PY, actions);
    return { success: true, data: result };
  } catch (errorMessage) {
    return { success: false, error: errorMessage };
  }
});

// Checks the watchlist for neglected apps - run on every app launch.
ipcMain.handle('check-watchlist', async () => {
  try {
    const result = await runPythonJson(CHECK_WATCHLIST_PY, null);
    return { success: true, data: result };
  } catch (errorMessage) {
    return { success: false, error: errorMessage };
  }
});

// Handles the user's response to a nag (uninstall / snooze / stop watching).
ipcMain.handle('respond-to-nag', async (event, payload) => {
  try {
    const result = await runPythonJson(RESPOND_TO_NAG_PY, payload);
    return { success: true, data: result };
  } catch (errorMessage) {
    return { success: false, error: errorMessage };
  }
});

// Runs a Python script with plain string argv args (not a single JSON
// blob) and resolves with its parsed stdout JSON - used for the
// list/add/remove watchlist commands and the installed-apps listing.
function runPythonArgs(scriptPath, args) {
  return new Promise((resolve, reject) => {
    const proc = spawnBackend(scriptPath, args);
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (c) => { stdout += c.toString(); });
    proc.stderr.on('data', (c) => { stderr += c.toString(); });
    proc.on('error', (err) => reject(`Could not start Python process: ${err.message}`));
    proc.on('close', (code) => {
      if (code !== 0) { reject(`Python exited with code ${code}.\n${stderr}`); return; }
      try { resolve(JSON.parse(stdout.trim())); }
      catch (e) { reject(`Could not parse Python output as JSON.\nRaw output:\n${stdout}\n\nStderr:\n${stderr}`); }
    });
  });
}

ipcMain.handle('get-installed-apps', async () => {
  try {
    const result = await runPythonArgs(INSTALLED_APPS_PY, ['--json']);
    return { success: true, data: result };
  } catch (errorMessage) {
    return { success: false, error: errorMessage };
  }
});

ipcMain.handle('get-watchlist', async () => {
  try {
    const result = await runPythonArgs(WATCHLIST_JSON_PY, ['list']);
    return { success: true, data: result };
  } catch (errorMessage) {
    return { success: false, error: errorMessage };
  }
});

ipcMain.handle('add-to-watchlist', async (event, app) => {
  try {
    const result = await runPythonArgs(WATCHLIST_JSON_PY, ['add', JSON.stringify(app)]);
    return { success: true, data: result };
  } catch (errorMessage) {
    return { success: false, error: errorMessage };
  }
});

ipcMain.handle('remove-from-watchlist', async (event, name) => {
  try {
    const result = await runPythonArgs(WATCHLIST_JSON_PY, ['remove', name]);
    return { success: true, data: result };
  } catch (errorMessage) {
    return { success: false, error: errorMessage };
  }
});


// ---------------------------------------------------------------------
// Connect AI: the user's own AI provider + key.
//
// Keys are encrypted with Windows' protected storage (Electron safeStorage)
// before being written to disk, and handed to Python only through
// environment variables of the one process that needs them - never on a
// command line, never in plain text on disk.
// ---------------------------------------------------------------------

const AI_CONFIG_FILE = () => path.join(app.getPath('userData'), 'ai-config.json');
let registryCache = null;

function readAiConfig() {
  try {
    const cfg = JSON.parse(fs.readFileSync(AI_CONFIG_FILE(), 'utf-8'));
    return { active: cfg.active || null, providers: cfg.providers || {} };
  } catch (e) {
    return { active: null, providers: {} };
  }
}

function writeAiConfig(cfg) {
  fs.mkdirSync(path.dirname(AI_CONFIG_FILE()), { recursive: true });
  fs.writeFileSync(AI_CONFIG_FILE(), JSON.stringify(cfg, null, 2), 'utf-8');
}

async function getRegistry() {
  if (!registryCache) {
    const res = await runPythonJson(CONNECT_AI_PY, { action: 'registry' });
    registryCache = res.providers;
  }
  return registryCache;
}

function decryptKey(entry) {
  if (!entry || !entry.key_enc) return '';
  try {
    return safeStorage.decryptString(Buffer.from(entry.key_enc, 'base64'));
  } catch (e) {
    return '';
  }
}

// Environment variables describing the active AI, for the Python subprocess.
function activeAiEnv() {
  const cfg = readAiConfig();
  if (!cfg.active || !cfg.providers[cfg.active]) return {};
  const entry = cfg.providers[cfg.active];
  return {
    DEBOLAT_AI_PROVIDER: cfg.active,
    DEBOLAT_AI_KEY: decryptKey(entry),
    DEBOLAT_AI_MODEL: entry.model || ''
  };
}

ipcMain.handle('ai-get-state', async () => {
  try {
    const registry = await getRegistry();
    const cfg = readAiConfig();
    const providers = registry.map((p) => ({
      ...p,
      connected: !!cfg.providers[p.id],
      model: (cfg.providers[p.id] && cfg.providers[p.id].model) || ''
    }));
    return {
      success: true,
      data: {
        providers,
        active: cfg.active,
        dev_fallback: !!process.env.GEMINI_API_KEY,
        encryption_available: safeStorage.isEncryptionAvailable()
      }
    };
  } catch (errorMessage) {
    return { success: false, error: String(errorMessage) };
  }
});

// Opens the provider's "get an API key" page in the user's normal browser.
// The URL comes from our own registry (never from the renderer), https only.
ipcMain.handle('ai-open-key-page', async (event, providerId) => {
  try {
    const registry = await getRegistry();
    const provider = registry.find((p) => p.id === providerId);
    if (!provider || !String(provider.key_url).startsWith('https://')) {
      return { success: false, error: 'Unknown provider' };
    }
    await shell.openExternal(provider.key_url);
    return { success: true };
  } catch (errorMessage) {
    return { success: false, error: String(errorMessage) };
  }
});

// Tests the key with one tiny request; only if it works is it saved.
ipcMain.handle('ai-connect', async (event, { providerId, key, model }) => {
  try {
    const registry = await getRegistry();
    const provider = registry.find((p) => p.id === providerId);
    if (!provider) return { success: false, error: 'Unknown provider' };

    const cleanKey = (key || '').trim();
    if (provider.needs_key && !cleanKey) {
      return { success: true, data: { ok: false, error: 'Paste your API key first.' } };
    }
    if (provider.needs_key && !safeStorage.isEncryptionAvailable()) {
      return { success: true, data: { ok: false, error: 'Windows secure storage is not available, so the key cannot be saved safely.' } };
    }

    const test = await runPythonJson(
      CONNECT_AI_PY,
      { action: 'test', provider: providerId, model: (model || '').trim() },
      { DEBOLAT_AI_KEY: cleanKey }
    );
    if (!test.ok) return { success: true, data: test };

    const cfg = readAiConfig();
    cfg.providers[providerId] = {
      key_enc: provider.needs_key ? safeStorage.encryptString(cleanKey).toString('base64') : null,
      model: test.model || ''
    };
    cfg.active = providerId;
    writeAiConfig(cfg);
    return { success: true, data: { ok: true, model: test.model } };
  } catch (errorMessage) {
    return { success: false, error: String(errorMessage) };
  }
});

ipcMain.handle('ai-set-active', async (event, providerId) => {
  const cfg = readAiConfig();
  if (!cfg.providers[providerId]) return { success: false, error: 'That AI is not connected yet.' };
  cfg.active = providerId;
  writeAiConfig(cfg);
  return { success: true };
});

ipcMain.handle('ai-disconnect', async (event, providerId) => {
  const cfg = readAiConfig();
  delete cfg.providers[providerId];
  if (cfg.active === providerId) cfg.active = Object.keys(cfg.providers)[0] || null;
  writeAiConfig(cfg);
  return { success: true };
});

// Drill-down: sizes of everything directly inside one folder.
ipcMain.handle('scan-folder', async (event, folderPath) => {
  try {
    const result = await runPythonArgs(SCAN_FOLDER_PY, [folderPath]);
    return { success: true, data: result };
  } catch (errorMessage) {
    return { success: false, error: errorMessage };
  }
});

// Only one copy of the app at a time (a second launch just focuses the first).
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    const win = BrowserWindow.getAllWindows()[0];
    if (win) { if (win.isMinimized()) win.restore(); win.focus(); }
  });
  app.whenReady().then(createWindow);
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
