/*
 * Debolat AI - Preload Script
 *
 * Safely exposes a minimal API to the webpage (renderer.js) without
 * giving it full Node.js access.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  runScan: (targetPath) => ipcRenderer.invoke('run-scan', targetPath),
  explainItem: (category, data) => ipcRenderer.invoke('explain-item', { category, data }),
  applyActions: (actions) => ipcRenderer.invoke('apply-actions', actions),
  checkWatchlist: () => ipcRenderer.invoke('check-watchlist'),
  respondToNag: (payload) => ipcRenderer.invoke('respond-to-nag', payload),
  getInstalledApps: () => ipcRenderer.invoke('get-installed-apps'),
  getWatchlist: () => ipcRenderer.invoke('get-watchlist'),
  addToWatchlist: (app) => ipcRenderer.invoke('add-to-watchlist', app),
  removeFromWatchlist: (name) => ipcRenderer.invoke('remove-from-watchlist', name),
  scanFolder: (folderPath) => ipcRenderer.invoke('scan-folder', folderPath),
  aiGetState: () => ipcRenderer.invoke('ai-get-state'),
  aiOpenKeyPage: (providerId) => ipcRenderer.invoke('ai-open-key-page', providerId),
  aiConnect: (providerId, key, model) => ipcRenderer.invoke('ai-connect', { providerId, key, model }),
  aiSetActive: (providerId) => ipcRenderer.invoke('ai-set-active', providerId),
  aiDisconnect: (providerId) => ipcRenderer.invoke('ai-disconnect', providerId)
});
