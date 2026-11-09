/*
 * Debolat AI - Frontend Logic
 */

const DEFAULT_SCAN_PATH = null;
let lastScanResult = null;

const selection = new Map();
const userTouched = new Set();


// ---- Motion + feedback helpers ----

const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Animates a number inside an element (eased count-up).
function countUp(el, target, format = (n) => String(n), duration = 800) {
  if (!el) return;
  if (prefersReducedMotion || !Number.isFinite(target)) { el.textContent = format(target); return; }
  const start = performance.now();
  const from = 0;
  function frame(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = format(from + (target - from) * eased);
    if (t < 1) requestAnimationFrame(frame);
    else el.textContent = format(target);
  }
  requestAnimationFrame(frame);
}

// Toasts: small slide-in notifications instead of native alert() boxes.
function showToast(message, kind = 'ok', title = '') {
  let stack = document.querySelector('.toast-stack');
  if (!stack) { stack = document.createElement('div'); stack.className = 'toast-stack'; document.body.appendChild(stack); }
  const toast = document.createElement('div');
  toast.className = `toast ${kind === 'ok' ? '' : kind}`;
  toast.innerHTML = `<div>${title ? `<div class="toast-title">${escapeHtml(title)}</div>` : ''}<div>${escapeHtml(message)}</div></div>`;
  stack.appendChild(toast);
  const remove = () => { toast.classList.add('leaving'); setTimeout(() => toast.remove(), 300); };
  setTimeout(remove, kind === 'err' ? 7000 : 4200);
  toast.addEventListener('click', remove);
}

// In-app confirm dialog (same look as the other modals). Resolves true/false.
function askConfirm({ title, message, confirmText = 'Confirm', danger = false }) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay hidden';
    overlay.innerHTML = `
      <div class="modal">
        <h2>${escapeHtml(title)}</h2>
        <p class="confirm-message">${escapeHtml(message)}</p>
        <div class="modal-actions">
          <button class="btn btn-secondary" data-act="no">Cancel</button>
          <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-act="yes">${escapeHtml(confirmText)}</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const finish = (value) => {
      overlay.classList.add('hidden');
      setTimeout(() => overlay.remove(), 350);
      document.removeEventListener('keydown', onKey);
      resolve(value);
    };
    const onKey = (e) => { if (e.key === 'Escape') finish(false); };
    document.addEventListener('keydown', onKey);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) finish(false);
      const act = e.target.dataset && e.target.dataset.act;
      if (act) finish(act === 'yes');
    });
    requestAnimationFrame(() => requestAnimationFrame(() => overlay.classList.remove('hidden')));
  });
}

// Sliding highlight behind the active top-nav tab.
function moveNavIndicator() {
  const tabs = document.querySelector('.nav-tabs');
  const active = document.querySelector('.nav-tab.active');
  if (!tabs || !active) return;
  let ind = tabs.querySelector('.nav-indicator');
  if (!ind) { ind = document.createElement('div'); ind.className = 'nav-indicator'; tabs.prepend(ind); }
  ind.style.width = `${active.offsetWidth}px`;
  ind.style.transform = `translateX(${active.offsetLeft}px)`;
}
window.addEventListener('resize', moveNavIndicator);
window.addEventListener('load', moveNavIndicator);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(moveNavIndicator);

// ---- Nav / screen switching ----

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');

  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.target === id);
  });

  moveNavIndicator();
  if (id === 'watchlist-screen') loadWatchlistScreen();
}

document.querySelectorAll('[data-target]').forEach(el => {
  el.addEventListener('click', () => showScreen(el.dataset.target));
});

// The app never assumes a name. The greeting is just "Good morning" until the
// user chooses to add one (kept only on this PC, in the app's local storage).
function getUserName() {
  try { return (localStorage.getItem('debolat.userName') || '').trim(); } catch (e) { return ''; }
}
function saveUserName(name) {
  try { if (name) localStorage.setItem('debolat.userName', name); else localStorage.removeItem('debolat.userName'); } catch (e) { /* storage unavailable: greeting stays generic */ }
}

function setGreeting() {
  const hour = new Date().getHours();
  const timeOfDay = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
  const name = getUserName();
  document.getElementById('greeting').textContent = `Good ${timeOfDay}${name ? ', ' + name : ''}`;

  let link = document.getElementById('set-name-btn');
  if (!link) {
    link = document.createElement('button');
    link.id = 'set-name-btn';
    link.className = 'link-btn';
    document.querySelector('.hero').appendChild(link);
    link.addEventListener('click', () => {
      const input = document.createElement('input');
      input.type = 'text';
      input.className = 'name-input';
      input.maxLength = 30;
      input.placeholder = 'Your first name';
      input.value = getUserName();
      link.replaceWith(input);
      input.focus();
      let done = false;
      const finish = (save) => {
        if (done) return; done = true;
        if (save) saveUserName(input.value.trim().slice(0, 30));
        input.replaceWith(link);
        setGreeting();
      };
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') finish(true); if (e.key === 'Escape') finish(false); });
      input.addEventListener('blur', () => finish(true));
    });
  }
  link.textContent = name ? 'Change name' : 'Add your name';
}
setGreeting();

// ---- Shared rendering helpers ----

function recommendationClass(rec) {
  switch (rec) {
    case 'KEEP': return 'keep';
    case 'INVESTIGATE': return 'investigate';
    case 'LIKELY_SAFE_TO_REMOVE': return 'safe-to-remove';
    default: return 'unsure';
  }
}
function recommendationLabel(rec) {
  switch (rec) {
    case 'KEEP': return 'Keep';
    case 'INVESTIGATE': return 'Investigate';
    case 'LIKELY_SAFE_TO_REMOVE': return 'Likely safe to remove';
    default: return 'Unsure - you decide';
  }
}

function updateSelectionFooter() {
  const footer = document.getElementById('selection-footer');
  const count = selection.size;
  if (count === 0) { footer.classList.add('hidden'); return; }
  footer.classList.remove('hidden');
  document.getElementById('selection-count').textContent = `${count} item${count === 1 ? '' : 's'} selected`;
}

function toggleSelection(uniqueKey, actionPayload, checked) {
  if (checked) selection.set(uniqueKey, actionPayload);
  else selection.delete(uniqueKey);
  updateSelectionFooter();
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function formatMb(mb) {
  return mb >= 1024 ? `${(mb / 1024).toFixed(2)} GB` : `${mb.toFixed(1)} MB`;
}

function formatBytes(bytes) {
  const gb = bytes / (1024 ** 3);
  if (gb >= 1) return `${gb.toFixed(2)} GB`;
  const mb = bytes / (1024 ** 2);
  if (mb >= 1) return `${mb.toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

// Top-level system folders that must never be offered for deletion, even
// though they appear when browsing a drive. (The Python action layer should
// enforce this too - the UI check is only the first guard.)
const PROTECTED_PATH = /^[a-z]:\\?(windows|program files|program files \(x86\)|programdata|users|system volume information|\$recycle\.bin|recovery|boot)?$/i;
function isProtectedPath(p) {
  return PROTECTED_PATH.test(String(p || '').replace(/[\\/]+$/, ''));
}

// Inserts (once) a container above a list, for filters, drive bars, notes.
function ensureExtras(listEl) {
  let extras = listEl.previousElementSibling;
  if (!extras || !extras.classList.contains('list-extras')) {
    extras = document.createElement('div');
    extras.className = 'list-extras';
    extras.style.cssText = 'margin-bottom:12px;display:flex;flex-direction:column;gap:10px;';
    listEl.parentNode.insertBefore(extras, listEl);
  }
  return extras;
}

function readOnlyRow(titleHtml, metaHtml, noteHtml) {
  const row = document.createElement('div');
  row.className = 'item-row';
  row.innerHTML = `
    <div></div>
    <div class="item-main">
      <div class="item-title-row"><span class="item-name">${titleHtml}</span></div>
      ${noteHtml ? `<div class="item-reasoning">${noteHtml}</div>` : ''}
    </div>
    <div class="item-meta"><div class="item-size mono">${metaHtml}</div></div>
  `;
  return row;
}

function renderItemRow({ category, raw, nameLabel, sizeLabel, subLabel, onOpen, protectedItem }) {
  const uniqueKey = `${category}:${category === 'storage' ? raw.path : category === 'ram' ? (raw.exe_path || raw.name) : nameLabel}`;
  const row = document.createElement('div');
  row.className = 'item-row';

  let actionPayload = { category, name: raw.name };
  if (category === 'ram') { actionPayload.pids = raw.pids; actionPayload.pid = raw.pids[0]; actionPayload.process_count = raw.process_count; }
  if (category === 'storage') actionPayload.path = raw.path;
  if (category === 'startup') { actionPayload.command = raw.command; actionPayload.scope = raw.scope; }

  row.innerHTML = `
    <input type="checkbox" class="item-checkbox" data-key="${escapeHtml(uniqueKey)}" ${protectedItem ? 'disabled title="System folder - protected"' : ''} />
    <div class="item-main">
      <div class="item-title-row">
        <span class="item-name">${escapeHtml(nameLabel)}</span>
        ${subLabel ? `<span class="watchlist-threshold">${escapeHtml(subLabel)}</span>` : ''}
        ${protectedItem ? '<span class="watchlist-threshold">System folder - protected</span>' : ''}
        <span class="item-type-tag ai-tag">Not checked yet</span>
      </div>
      <div class="ai-explanation-area">
        <button class="btn btn-secondary explain-btn">Show AI Explanation</button>
        ${onOpen ? '<button class="btn btn-secondary open-btn" style="margin-left:8px;">Open</button>' : ''}
      </div>
    </div>
    <div class="item-meta">
      <div class="item-size mono">${escapeHtml(sizeLabel)}</div>
    </div>
  `;

  const checkbox = row.querySelector('.item-checkbox');
  checkbox.addEventListener('change', (e) => {
    userTouched.add(uniqueKey);
    toggleSelection(uniqueKey, actionPayload, e.target.checked);
  });

  if (onOpen) row.querySelector('.open-btn').addEventListener('click', onOpen);

  const explainBtn = row.querySelector('.explain-btn');
  const explanationArea = row.querySelector('.ai-explanation-area');
  const typeTag = row.querySelector('.ai-tag');

  explainBtn.addEventListener('click', async () => {
    explainBtn.disabled = true;
    explainBtn.textContent = 'Asking AI...';
    explainBtn.classList.add('loading');

    const response = await window.api.explainItem(category, raw);

    if (!response.success || response.data.error) {
      const msg = escapeHtml(response.error || response.data.error);
      explanationArea.innerHTML = `<div class="item-explanation">Could not get an explanation: ${msg}</div>`;
      const retry = document.createElement('button');
      retry.className = 'btn btn-secondary';
      retry.textContent = 'Try again';
      retry.addEventListener('click', () => { explanationArea.innerHTML = ''; explanationArea.appendChild(explainBtn); explainBtn.disabled = false; explainBtn.classList.remove('loading'); explainBtn.textContent = 'Show AI Explanation'; });
      explanationArea.appendChild(retry);
      const kind = response.data && response.data.error_kind;
      if (kind === 'not_connected' || kind === 'auth' || kind === 'quota') {
        const connect = document.createElement('button');
        connect.className = 'btn btn-primary';
        connect.style.marginLeft = '8px';
        connect.textContent = kind === 'quota' ? 'Switch AI' : 'Connect AI';
        connect.addEventListener('click', openAiModal);
        explanationArea.appendChild(connect);
      }
      return;
    }

    const ai = response.data;
    const isJunk = ai.item_type === 'GENERIC_JUNK';
    typeTag.textContent = isJunk ? 'Generic junk' : 'Named application';
    typeTag.classList.toggle('junk', isJunk);

    explanationArea.innerHTML = `
      <div class="item-explanation">${escapeHtml(ai.explanation)}</div>
      <div class="item-reasoning">${escapeHtml(ai.reasoning)}</div>
      <div class="confidence-note">Confidence: ${escapeHtml(String(ai.confidence).toLowerCase())}</div>
      <span class="recommendation ${recommendationClass(ai.recommendation)}">${recommendationLabel(ai.recommendation)}</span>
    `;

    if (!userTouched.has(uniqueKey) && isJunk && !protectedItem) {
      checkbox.checked = true;
      toggleSelection(uniqueKey, actionPayload, true);
    }
  });

  // Keep the checkbox in sync if this row is re-rendered (filter / fold toggles).
  if (selection.has(uniqueKey)) checkbox.checked = true;

  return row;
}

// ---- Search box shared by the RAM and Storage lists ----

function attachFilter(listEl, placeholder, onChange) {
  const extras = ensureExtras(listEl);
  let input = extras.querySelector('.list-filter');
  if (!input) {
    input = document.createElement('input');
    input.type = 'search';
    input.className = 'list-filter';
    input.placeholder = placeholder;
    input.style.cssText = 'padding:8px 12px;border-radius:8px;border:1px solid rgba(128,128,128,.35);background:transparent;color:inherit;font:inherit;';
    extras.appendChild(input);
    input.addEventListener('input', () => onChange(input.value.trim().toLowerCase()));
  }
  return extras;
}

// ---- RAM screen ----

const RAM_FOLD_BELOW_MB = 25;   // display only: smaller apps are folded, never dropped
let ramData = null;
let ramFoldOpen = false;

function renderRamList(filter = '') {
  const ramList = document.getElementById('ram-list');
  ramList.innerHTML = '';
  const ram = ramData;
  if (!ram) return;

  const matches = ram.apps.filter(a => !filter || a.name.toLowerCase().includes(filter) || (a.exe_path || '').toLowerCase().includes(filter));
  const big = filter ? matches : matches.filter(a => a.ram_mb >= RAM_FOLD_BELOW_MB);
  const small = filter ? [] : matches.filter(a => a.ram_mb < RAM_FOLD_BELOW_MB);

  const makeRow = (a) => ramList.appendChild(renderItemRow({
    category: 'ram', raw: a,
    nameLabel: a.name,
    subLabel: `${a.process_count} process${a.process_count === 1 ? '' : 'es'}${a.includes_shared ? ' - includes shared memory' : ''}`,
    sizeLabel: formatMb(a.ram_mb),
  }));

  big.forEach(makeRow);

  if (small.length > 0) {
    const total = small.reduce((s, a) => s + a.ram_mb, 0);
    const foldRow = readOnlyRow(`${small.length} smaller apps`, formatMb(total), 'Each uses less than ' + RAM_FOLD_BELOW_MB + ' MB. Nothing is hidden - expand to see and manage them.');
    const toggle = document.createElement('button');
    toggle.className = 'btn btn-secondary';
    toggle.textContent = ramFoldOpen ? 'Hide' : 'Show all';
    toggle.addEventListener('click', () => { ramFoldOpen = !ramFoldOpen; renderRamList(filter); });
    foldRow.querySelector('.item-main').appendChild(toggle);
    ramList.appendChild(foldRow);
    if (ramFoldOpen) small.forEach(makeRow);
  }

  if (!filter) {
    ramList.appendChild(readOnlyRow(
      'System, kernel and cache',
      formatMb(ram.system_other_mb),
      'Memory Windows reports as used that no app owns (drivers, kernel, compressed memory, file cache). It cannot be closed from here.'
    ));
    if (ram.unreadable_processes > 0) {
      ramList.appendChild(readOnlyRow(
        `${ram.unreadable_processes} protected process${ram.unreadable_processes === 1 ? '' : 'es'} could not be read`,
        '-',
        'Windows blocked access. Running Debolat AI as administrator lets it read more of them.'
      ));
    }
  }
  if (matches.length === 0) ramList.appendChild(readOnlyRow('No apps match that search.', '', ''));
}

// ---- Storage screen ----

let storageRoot = null;       // { path, entries, denied, cloud }
let storageStack = [];        // drill-down history, deepest last
let storageFilter = '';

function driveBarsHtml(drives, canScan) {
  return drives.map(d => `
    <div style="display:flex;align-items:center;gap:12px;">
      <span class="mono" style="min-width:48px;">${escapeHtml(d.mountpoint)}</span>
      <div style="flex:1;height:8px;border-radius:4px;background:var(--border);overflow:hidden;">
        <div style="width:${d.percent_used}%;height:100%;background:var(--emerald);border-radius:4px;transition:width .8s cubic-bezier(.2,.8,.2,1);"></div>
      </div>
      <span class="mono" style="min-width:190px;text-align:right;font-size:13px;">${d.used_gb} / ${d.total_gb} GB (${d.free_gb} free)</span>
      ${canScan ? `<button class="btn btn-secondary scan-drive-btn" data-mount="${escapeHtml(d.mountpoint)}">Scan whole drive</button>` : ''}
    </div>`).join('');
}

let storageDrives = [];

function normPath(p) { return String(p || '').replace(/[\\/]+$/, '').toLowerCase(); }
function driveFor(path) { return storageDrives.find(d => normPath(d.mountpoint) === normPath(path)); }
function driveContaining(path) { return storageDrives.find(d => normPath(path).startsWith(normPath(d.mountpoint))); }
function parentPath(path) {
  const trimmed = String(path).replace(/[\\/]+$/, '');
  const parent = trimmed.replace(/[\\/][^\\/]+$/, '');
  return /^[a-z]:$/i.test(parent) ? parent + '\\' : parent;
}

function renderStorageList() {
  const storageList = document.getElementById('storage-list');
  storageList.innerHTML = '';
  if (!storageRoot) return;

  const level = storageStack.length > 0 ? storageStack[storageStack.length - 1] : storageRoot;
  const canDrill = typeof window.api.scanFolder === 'function';

  const extras = ensureExtras(storageList);
  let crumb = extras.querySelector('.storage-crumb');
  if (!crumb) { crumb = document.createElement('div'); crumb.className = 'storage-crumb'; extras.appendChild(crumb); }
  crumb.innerHTML = '';
  const where = document.createElement('span');
  where.className = 'mono';
  where.textContent = level.path;
  if (storageStack.length > 0) {
    const back = document.createElement('button');
    back.className = 'btn btn-secondary';
    back.textContent = 'Back';
    back.style.marginRight = '10px';
    back.addEventListener('click', () => { storageStack.pop(); storageFilter = ''; renderStorageList(); });
    crumb.appendChild(back);
  }
  const parent = parentPath(level.path);
  if (canDrill && parent && normPath(parent) !== normPath(level.path) && !driveFor(level.path)) {
    const up = document.createElement('button');
    up.className = 'btn btn-secondary';
    up.textContent = 'Up one level';
    up.style.marginRight = '10px';
    up.addEventListener('click', () => openStorageFolder(parent));
    crumb.appendChild(up);
  }
  crumb.appendChild(where);

  // Coverage banner: be upfront that this view is only part of the drive.
  const listedBytes = level.entries.reduce((sum, e) => sum + e.size_bytes, 0);
  const levelDrive = driveFor(level.path);
  const hostDrive = driveContaining(level.path);
  if (!levelDrive && storageStack.length === 0 && hostDrive && canDrill) {
    const banner = readOnlyRow(
      `This view covers ${formatBytes(listedBytes)}, not the whole drive`,
      '',
      `Your ${escapeHtml(hostDrive.mountpoint)} drive has ${hostDrive.used_gb} GB in use. Only the folder shown above was scanned (${escapeHtml(level.path)}). Use "Scan whole drive" above to see where the rest is.`
    );
    storageList.appendChild(banner);
  }

  const shown = level.entries.filter(e => !storageFilter || e.name.toLowerCase().includes(storageFilter));
  shown.forEach(e => {
    if (e.is_dir) {
      storageList.appendChild(renderItemRow({
        category: 'storage', raw: e, nameLabel: e.name, sizeLabel: formatBytes(e.size_bytes),
        protectedItem: isProtectedPath(e.path),
        onOpen: canDrill ? () => openStorageFolder(e.path) : null,
      }));
    } else {
      storageList.appendChild(readOnlyRow(escapeHtml(e.name), formatBytes(e.size_bytes), 'File'));
    }
  });
  if (shown.length === 0) storageList.appendChild(readOnlyRow('Nothing here matches.', '', ''));

  // At a drive root, show how much of the drive's used space the list explains.
  if (levelDrive && !storageFilter) {
    const usedBytes = levelDrive.used_gb * (1024 ** 3);
    const unlisted = Math.max(0, usedBytes - listedBytes);
    storageList.appendChild(readOnlyRow(
      'Not listed above',
      formatBytes(unlisted),
      'Space Windows counts as used but this scan cannot list: items Windows blocked, System Volume Information (restore points), and rounding between file sizes and disk blocks. The hibernation file, pagefile and swapfile are listed above when present.'
    ));
  }

  if (level.denied > 0 || level.cloud_only_skipped > 0) {
    const bits = [];
    if (level.denied > 0) bits.push(`${level.denied} item${level.denied === 1 ? '' : 's'} could not be read (permissions), so sizes may be slightly low`);
    if (level.cloud_only_skipped > 0) bits.push(`${level.cloud_only_skipped} online-only OneDrive file${level.cloud_only_skipped === 1 ? '' : 's'} skipped (they take no disk space)`);
    storageList.appendChild(readOnlyRow('Scan notes', '', bits.join('. ') + '.'));
  }
}

async function openStorageFolder(path) {
  const storageList = document.getElementById('storage-list');
  storageList.innerHTML = `<div class="item-explanation">Scanning ${escapeHtml(path)} ... this reads every file, so a whole drive can take several minutes. You can keep using the other tabs.</div>`;
  const response = await window.api.scanFolder(path);
  if (!response.success || (response.data && response.data.error)) {
    renderStorageList();
    storageList.insertBefore(readOnlyRow('Could not open that folder', '', escapeHtml(response.error || response.data.error)), storageList.firstChild);
    return;
  }
  const d = response.data;
  storageStack.push({ path: d.path, entries: d.entries, denied: d.denied, cloud_only_skipped: d.cloud_only_skipped });
  storageFilter = '';
  renderStorageList();
}

function renderResult(result) {
  const ram = result.ram, storage = result.storage, startup = result.startup;
  selection.clear();
  userTouched.clear();

  countUp(document.getElementById('ram-value'), ram.used_gb, (n) => `${n.toFixed(1)} GB`);
  countUp(document.getElementById('ram-percent'), ram.percent_used, (n) => `of ${ram.total_gb} GB \u00B7 ${n.toFixed(0)}% used`);

  const topFolder = storage.folders[0];
  if (topFolder) {
    const gbVal = topFolder.size_bytes / (1024 ** 3);
    if (gbVal >= 1) countUp(document.getElementById('storage-value'), gbVal, (n) => `${n.toFixed(2)} GB`);
    else document.getElementById('storage-value').textContent = formatBytes(topFolder.size_bytes);
    document.getElementById('storage-name').textContent = topFolder.name;
  }

  countUp(document.getElementById('startup-value'), startup.items.length, (n) => `${Math.round(n)}`, 600);
  document.getElementById('startup-sub').textContent = startup.items.length > 0 ? `e.g. ${startup.items[0].name}` : 'None found';

  // RAM
  ramData = ram;
  ramFoldOpen = false;
  const ramList = document.getElementById('ram-list');
  const ramExtras = attachFilter(ramList, 'Search apps...', renderRamList);
  ramExtras.querySelector('.list-filter').value = '';
  renderRamList('');

  // Storage: drives overview + every folder in the scanned location
  storageRoot = { path: storage.scanned_path, entries: storage.folders, denied: storage.denied, cloud_only_skipped: storage.cloud_only_skipped };
  storageStack = [];
  storageFilter = '';
  const storageList = document.getElementById('storage-list');
  const storageExtras = attachFilter(storageList, 'Search folders...', (q) => { storageFilter = q; renderStorageList(); });
  storageExtras.querySelector('.list-filter').value = '';
  let bars = storageExtras.querySelector('.drive-bars');
  if (!bars) { bars = document.createElement('div'); bars.className = 'drive-bars'; bars.style.cssText = 'display:flex;flex-direction:column;gap:8px;'; storageExtras.insertBefore(bars, storageExtras.firstChild); }
  storageDrives = storage.drives || [];
  const canScanDrives = typeof window.api.scanFolder === 'function';
  bars.innerHTML = driveBarsHtml(storageDrives, canScanDrives);
  bars.querySelectorAll('.scan-drive-btn').forEach(btn => btn.addEventListener('click', () => { showScreen('storage-screen'); openStorageFolder(btn.dataset.mount); }));
  renderStorageList();

  // Startup (every entry - nothing capped)
  const startupList = document.getElementById('startup-list');
  startupList.innerHTML = '';
  startup.items.forEach(item => startupList.appendChild(renderItemRow({ category: 'startup', raw: item, nameLabel: item.name, sizeLabel: item.scope })));

  updateSelectionFooter();
}

function setScanStatus(text) {
  document.getElementById('last-scan-time').textContent = text;
  document.body.classList.toggle('is-scanning', text === 'Scanning...');
}

function showScanError(message) {
  setScanStatus('Scan failed');
  const errorHtml = `<div class="item-row"><div class="item-main"><div class="item-explanation">Scan failed: ${message}</div></div></div>`;
  document.getElementById('ram-list').innerHTML = errorHtml;
  document.getElementById('storage-list').innerHTML = errorHtml;
  document.getElementById('startup-list').innerHTML = errorHtml;
}

async function runScan() {
  setScanStatus('Scanning...');
  const response = await window.api.runScan(DEFAULT_SCAN_PATH);
  if (!response.success) { showScanError(response.error); return; }
  lastScanResult = response.data;
  renderResult(lastScanResult);
  const now = new Date();
  setScanStatus(`Last scanned ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
}

runScan();
checkNeglectedApps();

document.getElementById('refresh-btn').addEventListener('click', runScan);

// ---- Watchlist screen ----

async function loadWatchlistScreen() {
  const list = document.getElementById('watchlist-list');
  list.innerHTML = '<div class="item-explanation">Loading...</div>';

  const response = await window.api.getWatchlist();
  if (!response.success) {
    list.innerHTML = `<div class="item-explanation">Could not load watchlist: ${response.error}</div>`;
    return;
  }

  const entries = response.data;
  if (entries.length === 0) {
    list.innerHTML = '<p class="screen-intro">Nothing being watched yet. Click "Add an app" to start.</p>';
    return;
  }

  list.innerHTML = '';
  entries.forEach(entry => {
    const row = document.createElement('div');
    row.className = 'item-row';
    const baseline = entry.last_confirmed_used
      ? new Date(entry.last_confirmed_used).toLocaleDateString()
      : `watching since ${new Date(entry.watch_started).toLocaleDateString()}`;

    row.innerHTML = `
      <div></div>
      <div class="item-main">
        <div class="item-title-row"><span class="item-name">${entry.name}</span></div>
        <div class="watchlist-row-meta">
          <span class="watchlist-threshold">Threshold: ${entry.threshold_days} days</span>
          <span class="watchlist-threshold">Last used: ${baseline}</span>
          ${entry.snoozed_until ? `<span class="watchlist-threshold">Snoozed until ${new Date(entry.snoozed_until).toLocaleDateString()}</span>` : ''}
        </div>
      </div>
      <div class="item-meta">
        <button class="btn btn-secondary remove-watch-btn">Stop watching</button>
      </div>
    `;

    row.querySelector('.remove-watch-btn').addEventListener('click', async () => {
      await window.api.removeFromWatchlist(entry.name);
      loadWatchlistScreen();
    });

    list.appendChild(row);
  });
}

// ---- Add-to-watchlist picker ----

let installedAppsCache = null;

document.getElementById('add-to-watchlist-btn').addEventListener('click', async () => {
  document.getElementById('picker-modal').classList.remove('hidden');
  const listEl = document.getElementById('picker-list');
  listEl.innerHTML = '<div class="item-explanation">Loading installed apps...</div>';

  if (!installedAppsCache) {
    const response = await window.api.getInstalledApps();
    if (!response.success) {
      listEl.innerHTML = `<div class="item-explanation">Could not load apps: ${response.error}</div>`;
      return;
    }
    installedAppsCache = response.data;
  }
  renderPickerList(installedAppsCache);
});

function renderPickerList(apps) {
  const listEl = document.getElementById('picker-list');
  listEl.innerHTML = '';

  apps.forEach(app => {
    const row = document.createElement('div');
    row.className = 'picker-row';
    const lastUsedStr = app.days_since_used !== null
      ? `${app.days_since_used}d ago${app.match_type === 'approximate' ? ' (approx)' : ''}`
      : 'no usage record';

    row.innerHTML = `
      <div>
        <div class="picker-row-name">${app.name}</div>
        <div class="picker-row-meta">${lastUsedStr}</div>
      </div>
      <select class="threshold-select mono">
        <option value="7">1 week</option>
        <option value="14">2 weeks</option>
        <option value="21" selected>3 weeks</option>
        <option value="30">1 month</option>
      </select>
      <button class="btn btn-primary watch-btn">Watch</button>
    `;

    row.querySelector('.watch-btn').addEventListener('click', async (e) => {
      const thresholdDays = parseInt(row.querySelector('.threshold-select').value, 10);
      e.target.disabled = true;
      e.target.textContent = 'Added';
      await window.api.addToWatchlist({
        name: app.name,
        install_location: app.install_location,
        uninstall_string: app.uninstall_string,
        threshold_days: thresholdDays
      });
    });

    listEl.appendChild(row);
  });
}

document.getElementById('picker-search').addEventListener('input', (e) => {
  if (!installedAppsCache) return;
  const query = e.target.value.toLowerCase();
  renderPickerList(installedAppsCache.filter(a => a.name.toLowerCase().includes(query)));
});

document.getElementById('close-picker-btn').addEventListener('click', () => {
  document.getElementById('picker-modal').classList.add('hidden');
});

// ---- Review Selection modal ----

const categoryLabels = { ram: 'RAM process', storage: 'Storage folder', startup: 'Startup app' };
const categoryActionVerb = { ram: 'terminated', storage: 'sent to Recycle Bin', startup: 'removed from startup (backed up)' };

function openReviewModal() {
  const list = document.getElementById('review-list');
  list.innerHTML = '';
  if (selection.size === 0) {
    list.innerHTML = '<li>No items selected.</li>';
  } else {
    selection.forEach((payload) => {
      const li = document.createElement('li');
      const extra = payload.category === 'ram' && payload.process_count > 1 ? ` (${payload.process_count} processes)` : '';
      li.innerHTML = `<span>${escapeHtml(payload.name)}${extra}</span><span class="review-category">${categoryLabels[payload.category]} - will be ${categoryActionVerb[payload.category]}</span>`;
      list.appendChild(li);
    });
  }
  document.getElementById('apply-result').innerHTML = '';
  document.getElementById('apply-selection-btn').disabled = selection.size === 0;
  document.getElementById('review-modal').classList.remove('hidden');
}
function closeReviewModal() { document.getElementById('review-modal').classList.add('hidden'); }

document.getElementById('review-selection-btn').addEventListener('click', openReviewModal);
document.getElementById('close-modal-btn').addEventListener('click', closeReviewModal);
document.getElementById('review-modal').addEventListener('click', (e) => { if (e.target.id === 'review-modal') closeReviewModal(); });

document.getElementById('apply-selection-btn').addEventListener('click', async () => {
  const confirmed = await askConfirm({
    title: `Apply ${selection.size} action${selection.size === 1 ? '' : 's'}?`,
    message: 'Processes will be terminated immediately.\nFolders will be sent to the Recycle Bin (recoverable).\nStartup entries will be removed from the registry (backed up to a local log).\n\nThis cannot be undone from within the app.',
    confirmText: 'Apply now',
    danger: true
  });
  if (!confirmed) return;

  const applyBtn = document.getElementById('apply-selection-btn');
  applyBtn.disabled = true;
  applyBtn.textContent = 'Applying...';

  // An app group can be many processes: send one kill action per PID so the
  // existing single-pid apply_actions handler works unchanged.
  const actions = [];
  selection.forEach((p) => {
    if (p.category === 'ram' && Array.isArray(p.pids)) {
      p.pids.forEach(pid => actions.push({ category: 'ram', name: p.name, pid }));
    } else {
      actions.push(p);
    }
  });
  const response = await window.api.applyActions(actions);
  const resultArea = document.getElementById('apply-result');

  if (!response.success) {
    resultArea.innerHTML = `<p class="modal-note">Failed to apply actions: ${response.error}</p>`;
    showToast(String(response.error), 'err', 'Something went wrong');
  } else {
    const succeeded = response.data.filter(r => r.success).length;
    const failed = response.data.length - succeeded;
    const lines = response.data.map(r => `${r.success ? '✓' : '✗'} ${escapeHtml(r.name)} (${r.category})${r.error ? ' - ' + escapeHtml(r.error) : ''}`);
    const summary = failed === 0 ? `✅ Done — all ${succeeded} action(s) completed successfully.` : `⚠️ Completed with issues — ${succeeded} succeeded, ${failed} failed.`;
    resultArea.innerHTML = `<p class="apply-summary ${failed === 0 ? 'success' : 'warning'}">${summary}</p><pre class="apply-results">${lines.join('\n')}</pre>`;
    showToast(summary.replace(/^\S+\s/, ''), failed === 0 ? 'ok' : 'warn', failed === 0 ? 'Done' : 'Finished with issues');
  }

  applyBtn.disabled = false;
  applyBtn.textContent = 'Apply Selected';
  selection.clear();
  updateSelectionFooter();
  runScan();
});

// ---- Connect AI ----

let aiState = null;          // { providers, active, dev_fallback, encryption_available }
let aiSelectedId = null;
let aiDropdownOpen = false;

async function refreshAiState() {
  const response = await window.api.aiGetState();
  if (response.success) aiState = response.data;
  renderAiStatus();
  return aiState;
}

function renderAiStatus() {
  const el = document.getElementById('ai-status-text');
  const btn = document.getElementById('connect-ai-btn');
  btn.classList.remove('connected', 'dev', 'attention');
  if (!aiState) { el.textContent = 'AI unavailable'; btn.classList.add('attention'); return; }
  const active = aiState.providers.find(p => p.id === aiState.active);
  if (active) {
    el.textContent = active.name;
    btn.classList.add('connected');
    btn.title = `Connected to ${active.name}${active.model ? ' (' + active.model + ')' : ''} - click to change`;
  } else if (aiState.dev_fallback) {
    el.textContent = 'Developer key';
    btn.classList.add('dev');
    btn.title = 'Using the built-in developer key. Click to connect your own AI.';
  } else {
    el.textContent = 'Connect AI';
    btn.classList.add('attention');
    btn.title = 'No AI connected - click to set one up';
  }
}

async function openAiModal() {
  document.getElementById('ai-modal').classList.remove('hidden');
  if (!aiState) await refreshAiState();
  if (!aiState) {
    document.getElementById('ai-modal-body').innerHTML = '<div class="item-explanation">Could not load AI settings.</div>';
    return;
  }
  aiSelectedId = aiState.active || aiState.providers[0].id;
  aiDropdownOpen = false;
  renderAiModal();
}

function setAiMessage(text, kind) {
  const el = document.getElementById('ai-msg');
  if (!el) return;
  el.textContent = text;
  el.className = `ai-msg ${kind || ''}`;
}

function renderAiModal(keepMessage) {
  const body = document.getElementById('ai-modal-body');
  const providers = aiState.providers;
  const selected = providers.find(p => p.id === aiSelectedId);
  const isActive = aiState.active === selected.id;

  body.innerHTML = `
    <div class="ai-dropdown ${aiDropdownOpen ? 'open' : ''}" id="ai-dropdown">
      <button class="ai-dropdown-toggle" id="ai-dropdown-toggle">
        <span>${escapeHtml(selected.name)}${selected.connected ? (isActive ? ' - active' : ' - connected') : ''}</span>
        <svg class="ai-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <div class="ai-dropdown-list" id="ai-dropdown-list"></div>
    </div>
    <div class="ai-form" id="ai-form"></div>
    <div class="ai-msg" id="ai-msg"></div>
    <p class="ai-privacy" id="ai-privacy"></p>
  `;

  document.getElementById('ai-dropdown-toggle').addEventListener('click', () => { aiDropdownOpen = !aiDropdownOpen; document.getElementById('ai-dropdown').classList.toggle('open', aiDropdownOpen); });

  // Dropdown: every AI is its own row with its own "Get ..." button.
  const list = document.getElementById('ai-dropdown-list');
  providers.forEach(p => {
    const row = document.createElement('div');
    row.className = `ai-option ${p.id === aiSelectedId ? 'selected' : ''}`;
    row.innerHTML = `
      <div>
        <div class="ai-option-name">${escapeHtml(p.name)}</div>
        <div class="ai-option-note">${escapeHtml(p.note)}</div>
      </div>
      <div class="ai-option-actions">
        ${p.id === aiState.active ? '<span class="ai-badge active">Active</span>' : p.connected ? '<span class="ai-badge">Connected</span>' : ''}
        <button class="btn btn-secondary get-key-btn">${escapeHtml(p.key_button)}</button>
      </div>
    `;
    row.querySelector('.get-key-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      window.api.aiOpenKeyPage(p.id);
    });
    row.addEventListener('click', () => { aiSelectedId = p.id; aiDropdownOpen = false; document.getElementById('ai-dropdown').classList.remove('open'); setTimeout(() => renderAiModal(), 220); });
    list.appendChild(row);
  });

  // Form for the selected AI
  const form = document.getElementById('ai-form');
  if (selected.needs_key) {
    form.innerHTML = `
      <ol class="ai-steps">
        <li>Click <b>${escapeHtml(selected.key_button)}</b> - it opens the right page in your browser.</li>
        <li>Create a key there and copy it.</li>
        <li>Paste it below and press Connect.</li>
      </ol>
      <div class="ai-row"><button class="btn btn-secondary" id="ai-get-key-btn">${escapeHtml(selected.key_button)}</button></div>
      <input type="password" id="ai-key-input" placeholder="${selected.connected ? 'Paste a new key to replace the saved one' : 'Paste your API key here'}" autocomplete="off" spellcheck="false" />
      <input type="text" id="ai-model-input" value="${escapeHtml(selected.model || selected.default_model)}" spellcheck="false" />
      <div class="ai-option-note">Model name - leave as is unless the connection test says it isn't available.</div>
      <div class="ai-row">
        <button class="btn btn-primary" id="ai-connect-btn">Connect</button>
      </div>
    `;
  } else {
    form.innerHTML = `
      <ol class="ai-steps">
        <li>Install Ollama and download a model (for example <b>ollama pull llama3.2</b>).</li>
        <li>Leave Ollama running, then press Detect and connect.</li>
      </ol>
      <div class="ai-row"><button class="btn btn-secondary" id="ai-get-key-btn">${escapeHtml(selected.key_button)}</button></div>
      <div class="ai-row"><button class="btn btn-primary" id="ai-connect-btn">Detect and connect</button></div>
    `;
  }

  if (selected.connected) {
    const connectRow = document.getElementById('ai-connect-btn').parentNode;
    connectRow.insertAdjacentHTML('beforeend', `
      ${isActive ? '' : '<button class="btn btn-secondary" id="ai-activate-btn">Use this AI</button>'}
      <button class="btn btn-secondary" id="ai-disconnect-btn">Disconnect</button>
    `);
  }

  document.getElementById('ai-get-key-btn').addEventListener('click', () => window.api.aiOpenKeyPage(selected.id));

  document.getElementById('ai-connect-btn').addEventListener('click', async (e) => {
    const btn = e.target;
    const keyInput = document.getElementById('ai-key-input');
    const modelInput = document.getElementById('ai-model-input');
    btn.disabled = true;
    const originalLabel = btn.textContent;
    btn.innerHTML = '<span class="btn-spinner"></span>Testing...';
    setAiMessage('Sending a tiny test request...', '');

    const response = await window.api.aiConnect(selected.id, keyInput ? keyInput.value : '', modelInput ? modelInput.value : '');
    if (keyInput) keyInput.value = '';   // never keep the key in the page

    if (!response.success) {
      btn.disabled = false; btn.textContent = originalLabel;
      setAiMessage(`Something went wrong: ${response.error}`, 'err');
      return;
    }
    if (!response.data.ok) {
      btn.disabled = false; btn.textContent = originalLabel;
      setAiMessage(response.data.error, 'err');
      return;
    }
    await refreshAiState();
    renderAiModal();
    setAiMessage(`Connected to ${selected.name}. Explanations will use it from now on.`, 'ok');
    showToast(`${selected.name} is now your AI.`, 'ok', 'Connected');
  });

  const activate = document.getElementById('ai-activate-btn');
  if (activate) activate.addEventListener('click', async () => {
    await window.api.aiSetActive(selected.id);
    await refreshAiState(); renderAiModal();
    setAiMessage(`Now using ${selected.name}.`, 'ok');
  });
  const disconnect = document.getElementById('ai-disconnect-btn');
  if (disconnect) disconnect.addEventListener('click', async () => {
    if (!(await askConfirm({ title: `Disconnect ${selected.name}?`, message: 'The saved key will be removed from this PC.', confirmText: 'Disconnect', danger: true }))) return;
    await window.api.aiDisconnect(selected.id);
    await refreshAiState(); renderAiModal();
    setAiMessage(`${selected.name} disconnected.`, 'ok');
  });

  document.getElementById('ai-privacy').textContent = selected.location === 'local'
    ? 'Runs on this PC. The names and paths of the items you ask about never leave your computer.'
    : `When you click "Show AI Explanation", that item's name and path (for example a process or folder name) are sent to ${selected.name}. Nothing is sent during scanning. Your key is stored encrypted on this PC.`;
  if (!aiState.encryption_available && selected.needs_key) {
    setAiMessage('Windows secure storage is unavailable, so keys cannot be saved safely on this PC.', 'err');
  }
}

document.getElementById('connect-ai-btn').addEventListener('click', openAiModal);
document.getElementById('close-ai-btn').addEventListener('click', () => document.getElementById('ai-modal').classList.add('hidden'));
document.getElementById('ai-modal').addEventListener('click', (e) => { if (e.target.id === 'ai-modal') e.currentTarget.classList.add('hidden'); });
refreshAiState();

// ---- Neglected app nag ----

let nagQueue = [];

async function checkNeglectedApps() {
  const response = await window.api.checkWatchlist();
  if (!response.success || !response.data || response.data.length === 0) return;
  nagQueue = response.data;
  showNextNag();
}

function showNextNag() {
  if (nagQueue.length === 0) return;
  const app = nagQueue[0];
  document.getElementById('nag-title').textContent = `Still need ${app.name}?`;
  document.getElementById('nag-body').textContent = `You haven't used ${app.name} in ${app.days_neglected} days (threshold: ${app.threshold_days} days). What would you like to do?`;
  document.getElementById('nag-uninstall-btn').disabled = !app.uninstall_string;
  document.getElementById('nag-modal').classList.remove('hidden');
}

async function respondToCurrentNag(action) {
  const app = nagQueue[0];
  if (!app) return;
  await window.api.respondToNag({ name: app.name, action, uninstall_string: app.uninstall_string });
  nagQueue.shift();
  document.getElementById('nag-modal').classList.add('hidden');
  if (nagQueue.length > 0) showNextNag();
}

document.getElementById('nag-uninstall-btn').addEventListener('click', () => respondToCurrentNag('uninstall'));
document.getElementById('nag-snooze-1-btn').addEventListener('click', () => respondToCurrentNag('snooze_1_week'));
document.getElementById('nag-snooze-2-btn').addEventListener('click', () => respondToCurrentNag('snooze_2_weeks'));
document.getElementById('nag-no-btn').addEventListener('click', () => respondToCurrentNag('stop_watching'));
