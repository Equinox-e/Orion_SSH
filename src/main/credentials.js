const fs = require('fs');
const path = require('path');
const { safeStorage } = require('electron');

const SERVICE = 'OrionSSH';
let KeyringEntry = null;
try {
  KeyringEntry = require('@napi-rs/keyring').Entry;
} catch {
  KeyringEntry = null;
}

function readJson(file, fallback) {
  try { return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : fallback; }
  catch { return fallback; }
}
function writeJson(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2), 'utf8');
}

class CredentialStore {
  constructor(userDataDir) {
    this.file = path.join(userDataDir, 'credentials-fallback.json');
  }

  makeKey(session) {
    const user = session.username || 'user';
    return `${session.id}:${user}@${session.host}:${session.port}`;
  }

  async get(session) {
    const key = this.makeKey(session);
    if (KeyringEntry) {
      try {
        const entry = new KeyringEntry(SERVICE, key);
        const value = entry.getPassword();
        if (value) return value;
      } catch {}
    }
    const data = readJson(this.file, {});
    const encrypted = data[key];
    if (!encrypted || !safeStorage.isEncryptionAvailable()) return null;
    try { return safeStorage.decryptString(Buffer.from(encrypted, 'base64')); }
    catch { return null; }
  }

  async set(session, password) {
    const key = this.makeKey(session);
    if (KeyringEntry) {
      try {
        const entry = new KeyringEntry(SERVICE, key);
        entry.setPassword(String(password));
        return { ok: true, backend: 'Windows Credential Manager / OS keyring' };
      } catch {}
    }
    if (!safeStorage.isEncryptionAvailable()) return { ok: false, backend: 'none' };
    const data = readJson(this.file, {});
    data[key] = safeStorage.encryptString(String(password)).toString('base64');
    writeJson(this.file, data);
    return { ok: true, backend: 'Electron safeStorage fallback' };
  }

  async delete(session) {
    const key = this.makeKey(session);
    if (KeyringEntry) {
      try { new KeyringEntry(SERVICE, key).deletePassword(); } catch {}
    }
    const data = readJson(this.file, {});
    delete data[key];
    writeJson(this.file, data);
    return { ok: true };
  }
}

module.exports = { CredentialStore };
