const fs = require('fs');
const path = require('path');
const { app } = require('electron');

const APP_NAME = 'OrionSSH';

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readJson(file, fallback) {
  try {
    if (!fs.existsSync(file)) return fallback;
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return fallback;
  }
}

function writeJson(file, value) {
  ensureDir(path.dirname(file));
  fs.writeFileSync(file, JSON.stringify(value, null, 2), 'utf8');
}

function userDataDir() {
  const dir = path.join(app.getPath('appData'), APP_NAME);
  ensureDir(dir);
  return dir;
}

function defaultSettings() {
  return {
    version: '2.0.0',
    language: 'en',
    theme: 'midnight',
    customTheme: null,
    fontSize: 13,
    cursorBlink: true,
    scrollback: 10000,
    reconnect: true,
    reconnectDelay: 5,
    connectTimeout: 15000,
    keepaliveInterval: 30000,
    pasteMode: 'bulk',
    sftpStartPath: '.',
    reduceMotion: false
  };
}

function normalizeSettings(settings = {}) {
  const clean = { ...defaultSettings(), ...(settings || {}) };
  clean.language = clean.language === 'ru' ? 'ru' : 'en';
  const validThemes = new Set(['midnight', 'graphite', 'nord', 'dracula', 'solarized', 'custom']);
  clean.theme = validThemes.has(clean.theme) ? clean.theme : 'midnight';
  clean.fontSize = Number(clean.fontSize || 13);
  clean.scrollback = Number(clean.scrollback || 10000);
  clean.reconnect = Boolean(clean.reconnect);
  clean.reduceMotion = Boolean(clean.reduceMotion);
  if (clean.theme === 'custom' && clean.customTheme && typeof clean.customTheme === 'object') {
    const hex = /^#[0-9a-fA-F]{6}$/;
    clean.customTheme = Object.fromEntries(Object.entries(clean.customTheme).filter(([, value]) => hex.test(String(value || ''))));
  } else {
    clean.customTheme = null;
  }
  return clean;
}


function normalizeSession(row, index = 0) {
  const id = String(row.id || cryptoRandomId());
  const group = String(row.group || row.category || (row.language === 'ru' ? 'Основные' : 'Default') || 'Default').trim() || 'Default';
  return {
    id,
    name: String(row.name || row.host || 'Untitled'),
    protocol: String(row.protocol || 'ssh').toLowerCase(),
    host: String(row.host || ''),
    port: Number(row.port || (row.protocol === 'rdp' ? 3389 : row.protocol === 'telnet' ? 23 : 22)),
    username: String(row.username || row.user || ''),
    authMode: String(row.authMode || row.auth_mode || 'password'),
    keyPath: String(row.keyPath || row.key_path || ''),
    startDir: String(row.startDir || row.start_dir || ''),
    group,
    groupColor: String(row.groupColor || row.group_color || row.color || '#38bdf8'),
    tags: String(row.tags || ''),
    notes: String(row.notes || ''),
    favorite: Boolean(row.favorite),
    order: Number(row.order ?? index * 10),
    groupOrder: Number(row.groupOrder ?? row.group_order ?? 0),
    savePassword: Boolean(row.savePassword ?? row.save_password),
    tunnels: String(row.tunnels || ''),
    serialPort: String(row.serialPort || row.serial_port || row.host || ''),
    serialBaud: Number(row.serialBaud || row.serial_baud || 9600)
  };
}

function normalizePreset(row) {
  return {
    id: String(row.id || cryptoRandomId()),
    name: String(row.name || ''),
    commands: String(row.commands || '')
  };
}

function cryptoRandomId() {
  try { return require('crypto').randomUUID(); }
  catch { return `${Date.now()}-${Math.random().toString(16).slice(2)}`; }
}

class Store {
  constructor() {
    this.dir = userDataDir();
    this.sessionsFile = path.join(this.dir, 'sessions.json');
    this.settingsFile = path.join(this.dir, 'settings.json');
    this.presetsFile = path.join(this.dir, 'presets.json');
  }

  getBootstrap() {
    return {
      settings: this.getSettings(),
      sessions: this.getSessions(),
      presets: this.getPresets(),
      contacts: this.getContacts(),
      userDataDir: this.dir
    };
  }

  getSettings() {
    return normalizeSettings(readJson(this.settingsFile, {}));
  }

  saveSettings(settings) {
    const clean = normalizeSettings(settings);
    writeJson(this.settingsFile, clean);
    return clean;
  }

  getSessions() {
    const data = readJson(this.sessionsFile, { sessions: [] });
    const rows = Array.isArray(data) ? data : (Array.isArray(data.sessions) ? data.sessions : []);
    return rows.map(normalizeSession).sort((a, b) => (a.groupOrder - b.groupOrder) || (a.order - b.order) || a.name.localeCompare(b.name));
  }

  saveSessions(sessions) {
    const clean = (Array.isArray(sessions) ? sessions : []).map(normalizeSession);
    writeJson(this.sessionsFile, { app: APP_NAME, version: '2.0.0', sessions: clean });
    return clean;
  }

  getPresets() {
    const data = readJson(this.presetsFile, { presets: [] });
    const rows = Array.isArray(data) ? data : (Array.isArray(data.presets) ? data.presets : []);
    return rows.map(normalizePreset).filter(p => p.name || p.commands).sort((a, b) => a.name.localeCompare(b.name));
  }

  savePresets(presets) {
    const clean = (Array.isArray(presets) ? presets : []).map(normalizePreset).sort((a, b) => a.name.localeCompare(b.name));
    writeJson(this.presetsFile, { app: APP_NAME, version: '2.0.0', presets: clean });
    return clean;
  }

  getContacts() {
    const builtin = {
      email: 'dev.equinox.e@gmail.com',
      telegram_bot: 'https://t.me/equinox_robot',
      website: 'https://github.com/Equinox-e/Orion_SSH',
      support_text_ru: 'Напишите нам, если нашли ошибку или нужна помощь с подключением.',
      support_text_en: 'Contact us if you found a bug or need help with a connection.'
    };
    const paths = [
      path.join(process.resourcesPath || '', 'contacts.json'),
      path.join(app.getAppPath(), 'contacts.json')
    ];
    for (const file of paths) {
      try {
        if (file && fs.existsSync(file)) return { ...builtin, ...JSON.parse(fs.readFileSync(file, 'utf8')) };
      } catch {}
    }
    return builtin;
  }

}

module.exports = { Store, normalizeSession, cryptoRandomId, defaultSettings };
