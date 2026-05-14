import './styles.css';
import logoUrl from './assets/orionssh.png';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { makeT } from './i18n.js';
import { themes, resolveTheme, applyTheme } from './themes.js';

const api = window.orion;
const state = {
  settings: null,
  sessions: [],
  presets: [],
  contacts: {},
  tabs: [],
  activeTab: null,
  filter: '',
  groupFilter: '',
  terminals: new Map(),
  tasks: new Map()
};
const t = makeT(() => state.settings?.language || 'en');
const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);
const $ = sel => document.querySelector(sel);
const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));

init();

async function init() {
  const bootstrap = await api.invoke('app:get-bootstrap');
  state.settings = bootstrap.settings;
  state.sessions = bootstrap.sessions;
  state.presets = bootstrap.presets;
  state.contacts = bootstrap.contacts;
  applyAllTheme();
  renderShell();
  bindIpc();
  openHome();
}

function applyAllTheme() {
  const theme = resolveTheme(state.settings);
  applyTheme(theme);
  document.body.classList.toggle('reduce-motion', !!state.settings.reduceMotion);
}

function fitVisibleTerminals() {
  for (const term of state.terminals.values()) {
    try {
      if (term?.container?.isConnected) term.fitSoon(0);
    } catch {}
  }
}

window.addEventListener('resize', () => {
  clearTimeout(window.__orionFitTimer);
  window.__orionFitTimer = setTimeout(fitVisibleTerminals, 90);
});

function renderShell() {
  $('#app').innerHTML = `
    <div class="app-shell">
      <header class="titlebar">
        <div class="title-left"><img src="${logoUrl}" alt=""><span>OrionSSH</span></div>
        <div class="window-controls">
          <button id="minBtn">—</button><button id="maxBtn">□</button><button class="close" id="closeBtn">×</button>
        </div>
      </header>
      <div class="main-grid">
        <aside class="sidebar">
          <div class="brand"><img src="${logoUrl}" alt=""><h1>OrionSSH</h1></div>
          <div class="nav-grid">
            <button class="btn primary" id="newSessionBtn">${t('new')}</button>
            <button class="btn" id="presetsBtn">${t('presets')}</button>
            <button class="btn" id="settingsBtn">${t('settings')}</button>
            <button class="btn" id="contactsBtn">${t('contacts')}</button>
          </div>
          <div class="search-area">
            <input class="input" id="searchInput" placeholder="${t('search')}" />
            <select class="select" id="groupFilter"></select>
          </div>
          <div class="session-list" id="sessionList"></div>
        </aside>
        <main class="content">
          <div class="tabbar-row">
            <div class="tabbar" id="tabbar"></div>
            <div class="tab-actions" title="Split workspace">
              <button class="split-action" id="splitColsBtn" title="${t('splitRight')}" aria-label="${t('splitRight')}"><span class="split-ico cols"><i></i><i></i></span></button>
              <button class="split-action" id="splitRowsBtn" title="${t('splitDown')}" aria-label="${t('splitDown')}"><span class="split-ico rows"><i></i><i></i></span></button>
              <button class="split-action" id="splitGridBtn" title="${t('splitGrid')}" aria-label="${t('splitGrid')}"><span class="split-ico grid"><i></i><i></i><i></i><i></i></span></button>
            </div>
          </div>
          <div class="pages" id="pages"></div>
          <div class="activity" id="activity"></div>
        </main>
      </div>
    </div>`;
  $('#minBtn').onclick = () => api.invoke('window:minimize');
  $('#maxBtn').onclick = () => api.invoke('window:maximize');
  $('#closeBtn').onclick = () => api.invoke('window:close');
  $('#newSessionBtn').onclick = () => openSessionEditor();
  $('#presetsBtn').onclick = () => openPresets();
  $('#settingsBtn').onclick = () => openSettings();
  $('#contactsBtn').onclick = () => openContacts();
  $('#splitColsBtn').onclick = () => openSplitWorkspace('cols', activeSessionForSplit());
  $('#splitRowsBtn').onclick = () => openSplitWorkspace('rows', activeSessionForSplit());
  $('#splitGridBtn').onclick = () => openSplitWorkspace('grid', activeSessionForSplit());
  $('#searchInput').oninput = e => { state.filter = e.target.value.toLowerCase(); renderSidebar(); };
  $('#groupFilter').onchange = e => { state.groupFilter = e.target.value; renderSidebar(); };
  renderSidebar();
  renderTabs();
}

function bindIpc() {
  api.on('terminal:data', ({ terminalId, data }) => state.terminals.get(terminalId)?.write(data));
  api.on('terminal:status', payload => state.terminals.get(payload.terminalId)?.setStatus(payload));
  api.on('terminal:closed', payload => state.terminals.get(payload.terminalId)?.setStatus({ state: 'closed', message: payload.message || 'Closed' }));
  api.on('terminal:password-request', showPasswordModal);
  api.on('task:update', updateTask);
}

function saveSessions() { return api.invoke('sessions:save-all', state.sessions); }
function savePresets() { return api.invoke('presets:save-all', state.presets); }
function groups() {
  const map = new Map();
  for (const s of state.sessions) {
    const g = s.group || 'Default';
    map.set(g, Math.min(map.get(g) ?? s.groupOrder ?? 0, s.groupOrder ?? 0));
  }
  return [...map.entries()].sort((a,b)=>(a[1]-b[1]) || a[0].localeCompare(b[0])).map(x=>x[0]);
}
function groupColor(group) { return state.sessions.find(s => s.group === group)?.groupColor || 'var(--accent)'; }

function renderSidebar() {
  const groupSel = $('#groupFilter');
  if (groupSel) {
    const values = [t('allGroups'), ...groups()];
    groupSel.innerHTML = values.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
    if (!values.includes(state.groupFilter)) state.groupFilter = t('allGroups');
    groupSel.value = state.groupFilter || t('allGroups');
  }
  const list = $('#sessionList');
  if (!list) return;
  const q = state.filter || '';
  const selected = state.groupFilter || t('allGroups');
  const filtered = state.sessions.filter(s => {
    const hay = [s.name,s.host,s.username,s.group,s.tags,s.notes,s.protocol].join(' ').toLowerCase();
    return (!q || hay.includes(q)) && (selected === t('allGroups') || !selected || s.group === selected);
  });
  if (!filtered.length) { list.innerHTML = `<div class="empty-state">${t('noSessions')}</div>`; return; }
  const grouped = new Map();
  for (const s of filtered) {
    const g = s.group || 'Default';
    if (!grouped.has(g)) grouped.set(g, []);
    grouped.get(g).push(s);
  }
  list.innerHTML = '';
  for (const group of groups().filter(g => grouped.has(g))) {
    const section = document.createElement('section');
    section.className = 'group-section';
    section.dataset.group = group;
    section.innerHTML = `
      <div class="group-head">
        <span class="grow">${esc(group)}</span>
      </div>
      <div class="group-cards" data-group="${esc(group)}"></div>`;
    const cards = section.querySelector('.group-cards');
    grouped.get(group).sort((a,b)=>(a.order-b.order)||a.name.localeCompare(b.name)).forEach(s => cards.appendChild(sessionCard(s)));
    list.appendChild(section);
  }
  attachSessionDragAndDrop(list);
}

function sessionCard(s) {
  const card = document.createElement('div');
  card.className = 'session-card';
  card.draggable = true;
  card.dataset.sessionId = s.id;
  card.dataset.group = s.group || 'Default';
  card.style.borderLeftColor = s.groupColor || 'var(--accent)';
  card.innerHTML = `
    <div class="session-info">
      <div class="session-name" title="${esc(s.name)}">${s.favorite ? '★ ' : ''}${esc(s.name)}</div>
      <div class="session-sub" title="${esc(`${s.protocol.toUpperCase()} ${s.username ? s.username+'@' : ''}${s.host}:${s.port}`)}">${esc(s.protocol.toUpperCase())} ${esc(s.username ? s.username+'@' : '')}${esc(s.host)}:${esc(s.port)}</div>
      ${s.tags ? `<div class="session-tags" title="${esc(s.tags)}">🏷 ${esc(s.tags)}</div>` : ''}
      ${s.notes ? `<div class="session-notes" title="${esc(s.notes)}">${esc(s.notes)}</div>` : ''}
    </div>
    <div class="session-actions">
      <button class="icon-btn" title="${t('open')}" data-open>▶</button>
      <button class="icon-btn" title="${t('duplicate')}" data-dupe>⧉</button>
      <button class="icon-btn" title="${t('edit')}" data-edit>✎</button>
      <button class="icon-btn danger" title="${t('delete')}" data-delete>×</button>
    </div>`;
  card.ondblclick = e => { if (!e.target.closest('button')) openTerminalTab(s); };
  card.querySelector('[data-open]').onclick = () => openTerminalTab(s);
  card.querySelector('[data-dupe]').onclick = () => openTerminalTab(s, true);
  card.querySelector('[data-edit]').onclick = () => openSessionEditor(s);
  card.querySelector('[data-delete]').onclick = () => deleteSession(s);
  return card;
}

function attachSessionDragAndDrop(list) {
  let dragging = null;
  list.querySelectorAll('.session-card').forEach(card => {
    card.addEventListener('dragstart', e => {
      dragging = card;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.dataset.sessionId);
    });
    card.addEventListener('dragend', async () => {
      card.classList.remove('dragging');
      await saveGroupOrderFromDom(card.dataset.group);
      dragging = null;
      renderSidebar();
    });
  });
  list.querySelectorAll('.group-cards').forEach(container => {
    container.addEventListener('dragover', e => {
      e.preventDefault();
      const id = e.dataTransfer.getData('text/plain') || dragging?.dataset.sessionId;
      const session = state.sessions.find(x => x.id === id);
      if (!session || (session.group || 'Default') !== container.dataset.group) return;
      const after = getDragAfterElement(container, e.clientY);
      if (dragging && dragging.parentElement !== container) return;
      if (after == null) container.appendChild(dragging);
      else container.insertBefore(dragging, after);
    });
    container.addEventListener('drop', async e => {
      e.preventDefault();
      await saveGroupOrderFromDom(container.dataset.group);
    });
  });
}

function getDragAfterElement(container, y) {
  const elements = [...container.querySelectorAll('.session-card:not(.dragging)')];
  return elements.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset) return { offset, element: child };
    return closest;
  }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
}

async function saveGroupOrderFromDom(group) {
  const container = document.querySelector(`.group-cards[data-group="${CSS.escape(group)}"]`);
  if (!container) return;
  [...container.querySelectorAll('.session-card')].forEach((card, index) => {
    const session = state.sessions.find(s => s.id === card.dataset.sessionId);
    if (session) session.order = index * 10;
  });
  await saveSessions();
}

async function moveGroup(group, delta) {
  const gs = groups(); const idx = gs.indexOf(group); const ni = Math.max(0, Math.min(gs.length-1, idx+delta));
  if (idx < 0 || idx === ni) return;
  const a = gs[idx], b = gs[ni];
  const ao = state.sessions.find(s=>s.group===a)?.groupOrder ?? idx*10;
  const bo = state.sessions.find(s=>s.group===b)?.groupOrder ?? ni*10;
  state.sessions.forEach(s => { if (s.group===a) s.groupOrder = bo; if (s.group===b) s.groupOrder = ao; });
  await saveSessions(); renderSidebar();
}
async function moveSession(s, delta) {
  const rows = state.sessions.filter(x=>x.group===s.group).sort((a,b)=>(a.order-b.order)||a.name.localeCompare(b.name));
  const idx = rows.findIndex(x=>x.id===s.id); const ni = Math.max(0, Math.min(rows.length-1, idx+delta));
  if (idx < 0 || idx === ni) return;
  [rows[idx].order, rows[ni].order] = [rows[ni].order, rows[idx].order];
  await saveSessions(); renderSidebar();
}
async function deleteSession(s) {
  if (!confirm(`${t('delete')} “${s.name}”?`)) return;
  state.sessions = state.sessions.filter(x => x.id !== s.id);
  await api.invoke('credentials:delete', s);
  await saveSessions(); renderSidebar(); openHome(true);
}

function activeSessionForSplit() {
  const tab = state.tabs.find(x => x.id === state.activeTab);
  if (tab?.pane?.session) return tab.pane.session;
  if (tab?.element) {
    const firstPane = [...state.terminals.values()].find(term => term.container?.isConnected);
    if (firstPane?.session) return firstPane.session;
  }
  return state.sessions[0] || null;
}

function tabExists(key) { return state.tabs.find(t => t.key === key); }
function addTab({ key, title, closable = true, render }) {
  const existing = key && tabExists(key);
  if (existing) { state.activeTab = existing.id; renderTabs(); return existing; }
  const id = uid();
  const tab = { id, key, title, closable, render, element: null };
  state.tabs.push(tab); state.activeTab = id; renderTabs(); return tab;
}
function closeTab(id) {
  const index = state.tabs.findIndex(t => t.id === id);
  if (index < 0) return;
  const tab = state.tabs[index];
  tab.onClose?.();
  state.tabs.splice(index, 1);
  if (state.activeTab === id) state.activeTab = state.tabs[Math.max(0, index-1)]?.id || null;
  renderTabs();
}
function renderTabs() {
  const bar = $('#tabbar'), pages = $('#pages'); if (!bar || !pages) return;
  bar.innerHTML = '';
  const alive = new Set(state.tabs.map(t => t.id));
  [...pages.children].forEach(child => { if (!alive.has(child.dataset.tabId)) child.remove(); });
  for (const tab of state.tabs) {
    const tabBtn = document.createElement('div');
    tabBtn.className = 'tab' + (tab.id === state.activeTab ? ' active' : '');
    tabBtn.innerHTML = `<span>${esc(tab.title)}</span>${tab.closable ? '<b class="x">×</b>' : ''}`;
    tabBtn.onclick = e => { if (e.target.classList.contains('x')) closeTab(tab.id); else { state.activeTab = tab.id; renderTabs(); } };
    bar.appendChild(tabBtn);

    let page = tab.element;
    if (!page || !page.isConnected) {
      page = document.createElement('section');
      page.className = 'page';
      page.dataset.tabId = tab.id;
      pages.appendChild(page);
      tab.element = page;
      tab.render(page, tab);
    }
    page.classList.toggle('active', tab.id === state.activeTab);
  }
  requestAnimationFrame(() => requestAnimationFrame(fitVisibleTerminals));
}
function rerenderActive() { const tab = state.tabs.find(t => t.id === state.activeTab); if (tab?.element) { tab.element.innerHTML = ''; delete tab.element.dataset.ready; tab.render(tab.element, tab); } renderTabs(); }

function openHome(replace = false) {
  if (replace && tabExists('home')) { state.activeTab = tabExists('home').id; renderTabs(); return; }
  addTab({ key:'home', title:t('home'), closable:false, render: renderHome });
}

function renderHome(el) {
  const fav = state.sessions.filter(s=>s.favorite).length;
  const recent = [...state.sessions].sort((a,b)=>(a.order-b.order)).slice(0,6);
  el.innerHTML = `<div class="dashboard">
    <div class="hero"><h2>OrionSSH</h2><p>${t('welcome')}</p></div>
    <div class="stats">
      <div class="card"><div class="stat-num">${state.sessions.length}</div><div>${t('total')}</div></div>
      <div class="card"><div class="stat-num">${groups().length}</div><div>${t('groups')}</div></div>
      <div class="card"><div class="stat-num">${fav}</div><div>${t('favorites')}</div></div>
      <div class="card"><div class="stat-num">${state.presets.length}</div><div>${t('presets')}</div></div>
    </div>
    <div class="grid-2">
      <div class="card"><h3>${t('quickConnect')}</h3><form class="form-grid" id="quickForm">
        <label>${t('host')}</label><input class="input" name="host"><label>${t('port')}</label><input class="input" name="port" value="22"><label>${t('username')}</label><input class="input" name="username"></form>
        <p style="color:var(--muted)">${t('bulkHint')}</p><button class="btn primary" id="quickBtn">${t('connect')}</button></div>
      <div class="card"><h3>${t('quickActions')}</h3><button class="btn primary" id="homeNew">${t('new')}</button> <button class="btn" id="homeSplit">${t('splitGrid')}</button><p style="color:var(--muted); line-height:1.5">${t('helpText')}</p></div>
    </div>
    <div class="card" style="margin-top:16px"><h3>${t('recent')}</h3><div id="recentList"></div></div>
  </div>`;
  el.querySelector('#quickForm').onsubmit = e => { e.preventDefault(); el.querySelector('#quickBtn').click(); };
  el.querySelector('#quickBtn').onclick = () => {
    const fd = new FormData(el.querySelector('#quickForm'));
    const s = normalizeSession({ name: fd.get('host'), host: fd.get('host'), port: Number(fd.get('port')||22), username: fd.get('username'), protocol:'ssh', authMode:'password' });
    openTerminalTab(s, true);
  };
  el.querySelector('#homeNew').onclick = () => openSessionEditor();
  el.querySelector('#homeSplit').onclick = () => openSplitWorkspace('grid');
  const list = el.querySelector('#recentList');
  list.innerHTML = recent.length ? '' : `<p>${t('noSessions')}</p>`;
  recent.forEach(s => list.appendChild(sessionCard(s)));
}

function normalizeSession(data = {}) {
  const group = data.group || groups()[0] || 'Default';
  return { id:data.id || uid(), name:data.name || data.host || 'New session', protocol:data.protocol || 'ssh', host:data.host || '', port:Number(data.port || 22), username:data.username || '', authMode:data.authMode || 'password', keyPath:data.keyPath || '', startDir:data.startDir || '', group, groupColor:data.groupColor || '#38bdf8', tags:data.tags || '', notes:data.notes || '', favorite:!!data.favorite, order:Number(data.order || 0), groupOrder:Number(data.groupOrder || 0), savePassword:!!data.savePassword, tunnels:data.tunnels || '', serialPort:data.serialPort || '', serialBaud:Number(data.serialBaud || 9600) };
}

const colorKeys = ['bg','surface','surface2','surface3','accent','text','muted','border','termBg','termFg'];
const colorNames = {
  en: { bg:'App background', surface:'Main panels', surface2:'Cards and inputs', surface3:'Hover / active surface', accent:'Accent', text:'Text', muted:'Muted text', border:'Borders', termBg:'Terminal background', termFg:'Terminal text' },
  ru: { bg:'Фон приложения', surface:'Основные панели', surface2:'Карточки и поля', surface3:'Наведение / активные панели', accent:'Акцент', text:'Текст', muted:'Вторичный текст', border:'Границы', termBg:'Фон терминала', termFg:'Текст терминала' }
};
function colorLabel(key) { return colorNames[state.settings?.language || 'en']?.[key] || key; }
function colorControl(name, value) {
  const safe = /^#[0-9a-fA-F]{6}$/.test(String(value || '')) ? value : '#38bdf8';
  return `<div class="color-control"><input class="color-swatch" type="color" name="${name}" value="${esc(safe)}"><span class="color-value">${esc(safe)}</span></div>`;
}
function bindColorControls(root, onChange) {
  root.querySelectorAll('.color-control').forEach(control => {
    const input = control.querySelector('input[type=color]');
    const value = control.querySelector('.color-value');
    const update = () => { value.textContent = input.value; if (onChange) onChange(input.value); };
    input.addEventListener('input', update);
    input.addEventListener('change', update);
  });
}

function openSessionEditor(session = null) {
  addTab({ key: session ? `edit:${session.id}` : `edit:new`, title: session ? `${t('edit')}: ${session.name}` : t('new'), render: el => renderSessionEditor(el, session) });
}
function renderSessionEditor(el, session) {
  const s = normalizeSession(session || {}); const groupValues = [...new Set([...groups(), s.group])];
  el.innerHTML = `<div class="page-pad"><div class="card form-card session-editor-card"><h2>${session ? t('edit') : t('new')}</h2>
    <form class="form-grid compact-form" id="sessionForm">
      ${field('protocol', t('protocol'), 'select', s.protocol, ['ssh','telnet','rdp','serial'])}
      ${field('name', t('name'), 'text', s.name)}${field('host', t('host'), 'text', s.host)}${field('port', t('port'), 'number', s.port)}${field('username', t('username'), 'text', s.username)}
      ${field('authMode', t('authMode'), 'select', s.authMode, ['password','key','agent'])}${field('password', t('password'), 'password', '')}
      <label>${t('savePassword')}</label><label class="switch-row"><input type="checkbox" name="savePassword" ${s.savePassword?'checked':''}><span></span></label>
      ${field('keyPath', t('privateKey'), 'fileText', s.keyPath)}
      ${field('group', t('group'), 'select', s.group, groupValues)}
      <label>${t('addGroup')}</label><input class="input" name="newGroup" placeholder="${t('group')}">
      <label>${t('groupColor')}</label>${colorControl('groupColor', s.groupColor)}
      <label>${t('favorite')}</label><label class="switch-row"><input type="checkbox" name="favorite" ${s.favorite?'checked':''}><span></span></label>
      ${field('tags', t('tags'), 'text', s.tags)}${field('startDir', t('startDir'), 'text', s.startDir)}${field('serialPort', t('serialPort'), 'text', s.serialPort)}${field('serialBaud', t('serialBaud'), 'number', s.serialBaud)}
      <label>${t('tunnels')}</label><textarea name="tunnels" rows="4">${esc(s.tunnels)}</textarea>
      <label>${t('notes')}</label><textarea name="notes" rows="4">${esc(s.notes)}</textarea>
    </form><div class="action-row"><button class="btn" id="cancelEdit">${t('cancel')}</button><button class="btn" id="saveOnly">${t('save')}</button><button class="btn primary" id="saveAndConnect">${t('saveConnect')}</button></div></div></div>`;
  bindColorControls(el);
  el.querySelector('[name=keyPath]')?.nextElementSibling?.addEventListener('click', async () => {
    const files = await api.invoke('dialog:open-file', { properties:['openFile'] }); if (files?.[0]) el.querySelector('[name=keyPath]').value = files[0];
  });
  el.querySelector('#cancelEdit').onclick = () => closeTab(state.activeTab);
  el.querySelector('#saveOnly').onclick = () => saveEdited(false);
  el.querySelector('#saveAndConnect').onclick = () => saveEdited(true);
  async function saveEdited(connect) {
    const form = el.querySelector('#sessionForm'); const fd = new FormData(form); const ng = String(fd.get('newGroup')||'').trim();
    const updated = normalizeSession({ ...s, id: session?.id || s.id, protocol:fd.get('protocol'), name:fd.get('name'), host:fd.get('host'), port:Number(fd.get('port')||22), username:fd.get('username'), authMode:fd.get('authMode'), keyPath:fd.get('keyPath'), group:ng || fd.get('group'), groupColor:fd.get('groupColor'), favorite:!!fd.get('favorite'), tags:fd.get('tags'), startDir:fd.get('startDir'), serialPort:fd.get('serialPort'), serialBaud:Number(fd.get('serialBaud')||9600), tunnels:fd.get('tunnels'), notes:fd.get('notes'), savePassword:!!fd.get('savePassword') });
    if (!updated.name || !updated.host) { alert(`${t('name')} / ${t('host')}`); return; }
    const password = fd.get('password');
    if (password && updated.savePassword) await api.invoke('credentials:set', { session: updated, password });
    if (!updated.savePassword) await api.invoke('credentials:delete', updated);
    const i = state.sessions.findIndex(x=>x.id===updated.id);
    if (i>=0) state.sessions[i] = updated; else { updated.groupOrder = groups().indexOf(updated.group)>=0 ? state.sessions.find(x=>x.group===updated.group)?.groupOrder || 0 : groups().length*10; updated.order = state.sessions.filter(x=>x.group===updated.group).length*10; state.sessions.push(updated); }
    await saveSessions(); renderSidebar(); closeTab(state.activeTab); if (connect) openTerminalTab(updated);
  }
}
function field(name, label, type, value, options=[]) {
  if (type === 'select') return `<label>${label}</label><select class="select" name="${name}">${options.map(o=>`<option value="${esc(o)}" ${o===value?'selected':''}>${esc(o)}</option>`).join('')}</select>`;
  if (type === 'fileText') return `<label>${label}</label><div style="display:flex; gap:8px"><input class="input" name="${name}" value="${esc(value)}"><button type="button" class="btn small">${t('browse')}</button></div>`;
  return `<label>${label}</label><input class="input" type="${type}" name="${name}" value="${esc(value)}">`;
}

class TerminalPane {
  constructor(container, session) {
    this.container = container;
    this.session = session;
    this.id = uid();
    this.statusEl = null;
    this.fit = new FitAddon();
    this.fitTimer = null;
    this.resizeObserver = null;
    this.started = false;
    const theme = resolveTheme(state.settings);
    this.term = new Terminal({
      cursorBlink: state.settings.cursorBlink,
      fontSize: state.settings.fontSize,
      scrollback: state.settings.scrollback,
      convertEol: false,
      allowProposedApi: true,
      windowsMode: api.platform === 'win32',
      theme: { background: theme.termBg, foreground: theme.termFg, cursor: theme.accent }
    });
    this.term.loadAddon(this.fit);
    this.term.loadAddon(new WebLinksAddon());
    state.terminals.set(this.id, this);
    this.render();
  }

  render() {
    this.container.innerHTML = `<div class="terminal-wrap"><div class="toolbar terminal-toolbar"><span class="term-status">Connecting…</span><select class="select presetSelect" title="${t('selectPreset')}"></select><button class="btn primary small runPreset">${t('run')}</button><button class="btn small files">${t('files')}</button><button class="btn small copy">${t('copy')}</button><button class="btn small paste">${t('paste')}</button><button class="btn small clear">${t('clear')}</button><button class="btn danger small disconnect">${t('disconnect')}</button></div><div class="terminal-host"></div></div>`;
    this.statusEl = this.container.querySelector('.term-status');
    const host = this.container.querySelector('.terminal-host');
    this.term.open(host);
    host.addEventListener('paste', event => this.handlePasteEvent(event), true);
    this.resizeObserver = new ResizeObserver(() => this.fitSoon());
    this.resizeObserver.observe(host);
    this.resizeObserver.observe(this.container);
    this.term.onData(data => api.invoke('terminal:write', { terminalId:this.id, data }));
    this.term.attachCustomKeyEventHandler(ev => {
      if (ev.type !== 'keydown') return true;
      const key = String(ev.key || '').toUpperCase();
      if (ev.ctrlKey && !ev.altKey && ev.shiftKey && ['C','X'].includes(key)) { this.copy(); return false; }
      if ((ev.ctrlKey && !ev.altKey && ev.shiftKey && key === 'V') || (ev.shiftKey && ev.key === 'Insert')) { this.paste(); return false; }
      // Friendly Windows-style copy/paste: Ctrl+C copies only when there is a
      // terminal selection. Without a selection it is still sent to the remote
      // PTY as SIGINT, so nano/vim/shell shortcuts continue to work.
      if (ev.ctrlKey && !ev.altKey && !ev.shiftKey && key === 'C') {
        if (this.term.hasSelection && this.term.hasSelection()) { this.copy(); return false; }
        return true;
      }
      if (ev.ctrlKey && !ev.altKey && !ev.shiftKey && key === 'V') { this.paste(); return false; }
      return true;
    });
    this.renderPresetSelect();
    this.container.querySelector('.runPreset').onclick = () => { this.runPreset(); this.focus(); };
    this.container.querySelector('.files').onclick = () => { openSftp(this); this.focusSoon(); };
    this.container.querySelector('.copy').onclick = () => { this.copy(); this.focus(); };
    this.container.querySelector('.paste').onclick = () => { this.paste(); };
    this.container.querySelector('.clear').onclick = () => { api.invoke('terminal:write', { terminalId:this.id, data:'clear\r' }); this.focus(); };
    this.container.querySelector('.disconnect').onclick = () => this.disconnect();
    requestAnimationFrame(() => {
      this.fitNow(false);
      setTimeout(() => { this.fitNow(false); this.connect(); }, 120);
    });
  }

  renderPresetSelect() {
    const sel = this.container.querySelector('.presetSelect');
    sel.innerHTML = `<option>${state.presets.length?t('selectPreset'):t('noPresets')}</option>` + state.presets.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('');
  }

  fitSoon(delay = 70) {
    clearTimeout(this.fitTimer);
    this.fitTimer = setTimeout(() => this.fitNow(true), delay);
  }

  fitNow(sendResize = true) {
    try {
      if (!this.container.isConnected) return;
      const host = this.container.querySelector('.terminal-host');
      if (!host || host.clientWidth < 80 || host.clientHeight < 80) return;
      this.fit.fit();
      if (sendResize && this.started) {
        const cols = Math.max(20, this.term.cols || 100);
        const rows = Math.max(8, this.term.rows || 30);
        api.invoke('terminal:resize', { terminalId:this.id, cols, rows });
      }
    } catch {}
  }

  connect() {
    if (this.started) return;
    this.started = true;
    this.fitNow(false);
    const cols = Math.max(80, this.term.cols || 100);
    const rows = Math.max(24, this.term.rows || 30);
    api.invoke('terminal:create', { terminalId:this.id, session:this.session, cols, rows })
      .catch(e => this.term.writeln(`\r\nError: ${e.message}`));
  }

  write(data) { this.term.write(data); }
  setStatus(p) { if (this.statusEl) { this.statusEl.textContent = p.message || p.state; this.statusEl.style.color = p.state === 'error' ? 'var(--danger)' : p.state === 'connected' ? 'var(--success)' : 'var(--muted)'; } if (p.state === 'error') this.term.writeln(`\r\n${p.message}`); }
  focus() { try { this.term.focus(); } catch {} }
  focusSoon() { setTimeout(() => this.focus(), 80); }
  normalizePasteText(text) { return String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\n/g, '\r'); }
  copy() { const text = this.term.getSelection(); if (text) api.invoke('clipboard:write', text); this.focusSoon(); }
  async paste() { const text = await api.invoke('clipboard:read'); this.sendPasteText(text); this.focusSoon(); }
  handlePasteEvent(event) {
    const text = event.clipboardData?.getData('text/plain');
    if (!text) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.stopImmediatePropagation) event.stopImmediatePropagation();
    this.sendPasteText(text);
    this.focusSoon();
  }
  sendPasteText(text) {
    const normalized = this.normalizePasteText(text);
    if (!normalized) return;
    const now = Date.now();
    if (this.lastPasteText === normalized && now - (this.lastPasteAt || 0) < 350) return;
    this.lastPasteText = normalized;
    this.lastPasteAt = now;
    api.invoke('terminal:write', { terminalId:this.id, data:normalized });
  }
  runPreset() { const id = this.container.querySelector('.presetSelect').value; const p = state.presets.find(x=>x.id===id); if (!p) { this.focus(); return; } const block = this.normalizePasteText(p.commands.trimEnd()) + '\r'; api.invoke('terminal:write', { terminalId:this.id, data:block }); this.focusSoon(); }
  disconnect() { api.invoke('terminal:disconnect', { terminalId:this.id }); }
  dispose() {
    this.disconnect();
    clearTimeout(this.fitTimer);
    try { this.resizeObserver?.disconnect(); } catch {}
    state.terminals.delete(this.id);
    try { this.term.dispose(); } catch {}
  }
}

function openTerminalTab(session, forceNew=false) {
  const key = forceNew ? null : `term:${session.id}`;
  const tab = addTab({ key, title: session.name, render: (el, tab) => { if (!tab.pane) { tab.pane = new TerminalPane(el, session); tab.onClose = () => tab.pane.dispose(); } else el.appendChild(tab.pane.container.firstChild || tab.pane.container); } });
}
function openSplitWorkspace(layout='cols', initial=null) {
  addTab({ key:null, title:t('splitGrid'), render: el => renderSplit(el, layout, initial) });
}
function renderSplit(el, layout, initial) {
  if (el.dataset.ready) return; el.dataset.ready = '1';
  const cls = layout === 'grid' ? 'grid' : layout === 'rows' ? 'rows' : 'cols'; const count = cls === 'grid' ? 4 : 2;
  el.innerHTML = `<div class="toolbar"><button class="btn small" data-layout="cols">${t('splitRight')}</button><button class="btn small" data-layout="rows">${t('splitDown')}</button><button class="btn small" data-layout="grid">${t('splitGrid')}</button></div><div class="split-area ${cls}"></div>`;
  el.querySelectorAll('[data-layout]').forEach(b => b.onclick = () => { el.dataset.ready=''; renderSplit(el, b.dataset.layout, initial); });
  const area = el.querySelector('.split-area');
  for (let i=0;i<count;i++) {
    const pane = document.createElement('div'); pane.className = 'pane';
    pane.innerHTML = `<div class="pane-head"><select class="select">${state.sessions.map(s=>`<option value="${s.id}">${esc(s.name)} — ${esc(s.host)}</option>`).join('')}</select><button class="btn primary small">${t('connect')}</button></div><div class="pane-body" style="flex:1; min-height:0"></div>`;
    area.appendChild(pane); const select = pane.querySelector('select'); if (initial && i===0) select.value = initial.id;
    let term = null; pane.querySelector('button').onclick = () => { term?.dispose(); const s = state.sessions.find(x=>x.id===select.value); if (!s) return; term = new TerminalPane(pane.querySelector('.pane-body'), s); };
    if (initial && i===0) pane.querySelector('button').click();
  }
}

function openSftp(termPane) { addTab({ key:`sftp:${termPane.id}`, title:`${t('files')}: ${termPane.session.name}`, render: el => renderSftp(el, termPane) }); }
function renderSftp(el, termPane) {
  if (el.dataset.ready) return; el.dataset.ready = '1'; let cwd = termPane.session.startDir || '.';
  el.innerHTML = `<div class="sftp"><div class="toolbar"><button class="btn small icon-only up" title="${t('up')}" aria-label="${t('up')}">↑</button><input class="input path" value="${esc(cwd)}"><button class="btn primary small go">${t('open')}</button><button class="btn small refresh">${t('refresh')}</button></div><div style="overflow:auto"><table class="file-table"><thead><tr><th>${t('name')}</th><th>${t('type')}</th><th class="right">${t('size')}</th><th>${t('modified')}</th></tr></thead><tbody></tbody></table></div><div class="toolbar"><button class="btn primary small upload">${t('upload')}</button><button class="btn primary small download">${t('download')}</button><input class="input folderName" placeholder="${t('mkdir')}" style="max-width:260px"><button class="btn small mkdir">${t('mkdir')}</button></div></div>`;
  const tbody = el.querySelector('tbody');
  async function load(path='.') { cwd = path || '.'; el.querySelector('.path').value = cwd; const res = await api.invoke('sftp:list', { terminalId:termPane.id, remotePath:cwd }); tbody.innerHTML = ''; res.items.forEach(item => { const tr = document.createElement('tr'); tr.dataset.path=item.path; tr.dataset.dir=item.isDirectory?'1':'0'; tr.innerHTML = `<td>${item.isDirectory?'📁':'📄'} ${esc(item.name)}</td><td>${item.isDirectory?'dir':'file'}</td><td class="right">${fmtSize(item.size)}</td><td>${item.mtime ? new Date(item.mtime*1000).toLocaleString() : ''}</td>`; tr.ondblclick = () => item.isDirectory ? load(item.path) : download(item.path, item.name); tbody.appendChild(tr); }); }
  function selected() { const tr = tbody.querySelector('tr.selected'); return tr ? { path:tr.dataset.path, dir:tr.dataset.dir==='1', name:tr.cells[0].textContent.replace(/^📁 |^📄 /,'') } : null; }
  tbody.onclick = e => { tbody.querySelectorAll('tr').forEach(r=>r.classList.remove('selected')); e.target.closest('tr')?.classList.add('selected'); };
  el.querySelector('.go').onclick = () => load(el.querySelector('.path').value);
  el.querySelector('.refresh').onclick = () => load(cwd);
  el.querySelector('.up').onclick = () => load(cwd.split('/').slice(0,-1).join('/') || '/');
  el.querySelector('.upload').onclick = async () => { const files = await api.invoke('dialog:open-file', { properties:['openFile','multiSelections'] }); for (const f of files) await api.invoke('sftp:upload', { terminalId:termPane.id, localPath:f, remotePath:`${cwd.replace(/\/$/,'')}/${f.split(/[\\/]/).pop()}` }); load(cwd); };
  el.querySelector('.download').onclick = async () => { const s = selected(); if (!s || s.dir) return; await download(s.path, s.name); };
  async function download(remotePath, name) { const localPath = await api.invoke('dialog:save-file', { defaultPath:name }); if (localPath) await api.invoke('sftp:download', { terminalId:termPane.id, remotePath, localPath }); }
  el.querySelector('.mkdir').onclick = async () => { const name = el.querySelector('.folderName').value.trim(); if (!name) return; await api.invoke('sftp:mkdir', { terminalId:termPane.id, remotePath:`${cwd.replace(/\/$/,'')}/${name}` }); el.querySelector('.folderName').value=''; load(cwd); };
  el.ondragover = e => { e.preventDefault(); };
  el.ondrop = async e => { e.preventDefault(); for (const file of e.dataTransfer.files) { if (file.path) await api.invoke('sftp:upload', { terminalId:termPane.id, localPath:file.path, remotePath:`${cwd.replace(/\/$/,'')}/${file.name}` }); } load(cwd); };
  load(cwd).catch(err => alert(err.message));
}
function fmtSize(n) { if (!n) return ''; const u=['B','KB','MB','GB','TB']; let i=0, v=n; while(v>1024&&i<u.length-1){v/=1024;i++;} return `${v.toFixed(i?1:0)} ${u[i]}`; }

function openPresets() { addTab({ key:'presets', title:t('presets'), render: renderPresets }); }
function renderPresets(el) {
  const first = state.presets[0] || { id:'', name:'', commands:'' };
  el.innerHTML = `<div class="dashboard"><div class="card"><h2>${t('commandPresets')}</h2><div class="grid-2"><div><select class="select presetList" size="12" style="height:320px">${state.presets.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></div><div class="form-grid"><label>${t('presetName')}</label><input class="input presetName"><label>${t('commands')}</label><textarea class="presetCommands" rows="12"></textarea></div></div><p style="color:var(--muted)">${t('bulkHint')}</p><button class="btn" id="newPreset">${t('new')}</button> <button class="btn primary" id="savePreset">${t('save')}</button> <button class="btn danger" id="delPreset">${t('delete')}</button></div></div>`;
  let current = first.id;
  function load(id) { const p = state.presets.find(x=>x.id===id) || { id:'', name:'', commands:'' }; current=p.id; el.querySelector('.presetName').value=p.name; el.querySelector('.presetCommands').value=p.commands; }
  el.querySelector('.presetList').onchange = e => load(e.target.value); load(current);
  el.querySelector('#newPreset').onclick = () => { current=''; load(''); };
  el.querySelector('#savePreset').onclick = async () => { const p={ id:current||uid(), name:el.querySelector('.presetName').value.trim(), commands:el.querySelector('.presetCommands').value.trim() }; if(!p.name||!p.commands)return; const i=state.presets.findIndex(x=>x.id===p.id); if(i>=0)state.presets[i]=p; else state.presets.push(p); await savePresets(); rerenderActive(); };
  el.querySelector('#delPreset').onclick = async () => { state.presets=state.presets.filter(x=>x.id!==current); await savePresets(); rerenderActive(); };
}

function openSettings() { addTab({ key:'settings', title:t('settings'), render: renderSettings }); }
function renderSettings(el) {
  const theme = resolveTheme(state.settings);
  el.innerHTML = `<div class="page-pad"><div class="card form-card settings-card"><h2>${t('settings')}</h2>
    <form class="form-grid compact-form" id="settingsForm">
      <label>${t('language')}</label><select class="select" name="language"><option value="en">English</option><option value="ru">Русский</option></select>
      <label>${t('theme')}</label><select class="select" name="theme">${Object.entries(themes).map(([k,v])=>`<option value="${k}">${v.name}</option>`).join('')}<option value="custom">${t('customTheme')}</option></select>
      <label>${t('fontSize')}</label><input class="input" type="number" name="fontSize" value="${state.settings.fontSize}">
      <label>${t('scrollback')}</label><input class="input" type="number" name="scrollback" value="${state.settings.scrollback}">
      <label>${t('reconnectSettings')}</label><label class="switch-row"><input type="checkbox" name="reconnect" ${state.settings.reconnect?'checked':''}><span></span></label>
      <label>${t('reduceMotion')}</label><label class="switch-row"><input type="checkbox" name="reduceMotion" ${state.settings.reduceMotion?'checked':''}><span></span></label>
      <div class="form-section-title">${t('customTheme')}</div>
      ${colorKeys.map(k=>`<label>${colorLabel(k)}</label>${colorControl(k, theme[k])}`).join('')}
    </form>
    <p class="muted-note">${t('restartHint')}</p>
    <div class="settings-status" id="settingsStatus"></div>
    <div class="action-row"><button class="btn primary" id="saveSettings" type="button">${t('save')}</button><button class="btn danger" id="restartApp" type="button">${t('restart')}</button></div>
  </div></div>`;
  const form = el.querySelector('#settingsForm');
  form.querySelector('[name=language]').value = state.settings.language || 'en';
  form.querySelector('[name=theme]').value = state.settings.theme || 'midnight';
  bindColorControls(el, () => { form.querySelector('[name=theme]').value = 'custom'; });
  form.querySelector('[name=theme]').onchange = e => {
    const picked = e.target.value === 'custom' ? resolveTheme({ ...state.settings, theme:'custom' }) : themes[e.target.value];
    if (!picked) return;
    colorKeys.forEach(k => {
      const input = form.querySelector(`[name="${k}"]`);
      const wrap = input?.closest('.color-control');
      if (input && picked[k]) { input.value = picked[k]; wrap.querySelector('.color-value').textContent = picked[k]; }
    });
  };
  async function saveSettingsFromForm({ rerender = true } = {}) {
    const fd = new FormData(form);
    const next = {
      ...state.settings,
      language: fd.get('language') === 'ru' ? 'ru' : 'en',
      theme: String(fd.get('theme') || 'midnight'),
      fontSize: Number(fd.get('fontSize') || 13),
      scrollback: Number(fd.get('scrollback') || 10000),
      reconnect: !!fd.get('reconnect'),
      reduceMotion: !!fd.get('reduceMotion'),
      customTheme: {}
    };
    for (const k of colorKeys) next.customTheme[k] = String(fd.get(k) || '').trim();
    if (next.theme !== 'custom') next.customTheme = null;
    const saved = await api.invoke('settings:save', next);
    state.settings = saved || next;
    applyAllTheme();
    refreshTerminalAppearance();
    if (rerender) {
      renderShell();
      openSettings();
    }
    return true;
  }
  el.querySelector('#saveSettings').onclick = async () => {
    const btn = el.querySelector('#saveSettings');
    const status = el.querySelector('#settingsStatus');
    try {
      btn.disabled = true;
      await saveSettingsFromForm({ rerender:true });
      const fresh = document.querySelector('#settingsStatus');
      if (fresh) fresh.textContent = t('saved');
    } catch (err) {
      status.textContent = err?.message || String(err);
    } finally {
      btn.disabled = false;
    }
  };
  el.querySelector('#restartApp').onclick = async () => {
    const btn = el.querySelector('#restartApp');
    const status = el.querySelector('#settingsStatus');
    try {
      btn.disabled = true;
      status.textContent = t('restarting');
      await saveSettingsFromForm({ rerender:false });
      await api.invoke('settings:restart');
    } catch (err) {
      btn.disabled = false;
      status.textContent = err?.message || String(err);
    }
  };
}

function refreshTerminalAppearance() {
  const theme = resolveTheme(state.settings);
  for (const pane of state.terminals.values()) {
    try {
      pane.term.options.theme = { background: theme.termBg, foreground: theme.termFg, cursor: theme.accent };
      pane.term.options.fontSize = Number(state.settings.fontSize || 13);
      pane.fitSoon(80);
    } catch {}
  }
}


function openContacts() { addTab({ key:'contacts', title:t('contacts'), render: renderContacts }); }
function renderContacts(el) {
  const lang = state.settings.language;
  el.innerHTML = `<div class="dashboard"><div class="card"><h2>${t('contacts')}</h2><p style="color:var(--muted)">${t('helpText')}</p><h3>${t('support')}</h3><p>${esc(state.contacts[lang==='ru'?'support_text_ru':'support_text_en'] || '')}</p>${contactRow(t('email'), state.contacts.email)}${contactRow('Telegram', state.contacts.telegram_bot)}${contactRow(t('website') || 'Website', state.contacts.website)}</div></div>`;
  el.querySelectorAll('[data-copy]').forEach(btn => btn.onclick = async () => { await api.invoke('clipboard:write', btn.dataset.copy); btn.textContent = t('copied'); setTimeout(()=>btn.textContent=t('copy'), 900); });
}
function contactRow(label, value) { return `<div class="card" style="margin:8px 0"><b>${label}</b><div style="display:flex; gap:10px; align-items:center; margin-top:8px"><span style="flex:1; word-break:break-all">${esc(value||'—')}</span><button class="btn small" data-copy="${esc(value||'')}">${t('copy')}</button></div></div>`; }

function showPasswordModal(req) {
  const back = document.createElement('div'); back.className = 'modal-backdrop';
  back.innerHTML = `<div class="modal"><h3>${esc(req.title || t('passwordRequired'))}</h3><p>${esc(req.message || t('enterPassword'))}</p><input class="input" type="password" autofocus><div style="display:flex; justify-content:flex-end; gap:8px; margin-top:16px"><button class="btn cancel">${t('cancel')}</button><button class="btn primary ok">OK</button></div></div>`;
  document.querySelector('.pages').appendChild(back); const input = back.querySelector('input'); input.focus();
  const done = value => { api.sendPasswordResponse({ requestId:req.requestId, value }); back.remove(); };
  back.querySelector('.ok').onclick = () => done(input.value);
  back.querySelector('.cancel').onclick = () => done(null);
  input.onkeydown = e => { if (e.key === 'Enter') done(input.value); if (e.key === 'Escape') done(null); };
}

function updateTask(task) {
  state.tasks.set(task.id, task); renderTasks();
  if (task.state === 'done' || task.state === 'error') setTimeout(() => { state.tasks.delete(task.id); renderTasks(); }, 3500);
}
function renderTasks() {
  const box = $('#activity'); if (!box) return;
  box.innerHTML = [...state.tasks.values()].slice(-6).map(task => `<div class="task"><div class="task-head"><span class="spinner"></span><b>${esc(task.label)}</b><span style="margin-left:auto;color:${task.state==='error'?'var(--danger)':'var(--muted)'}">${task.state==='done'?t('taskDone'):task.state==='error'?t('taskError'):''}</span></div>${typeof task.progress === 'number' ? `<div class="progress"><div style="width:${task.progress}%"></div></div>` : ''}${task.error?`<div style="color:var(--danger); margin-top:6px">${esc(task.error)}</div>`:''}</div>`).join('');
}
