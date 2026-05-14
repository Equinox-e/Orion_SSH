const fs = require('fs');
const net = require('net');
const path = require('path');
const { spawn } = require('child_process');
const { Client } = require('ssh2');
const { StringDecoder } = require('string_decoder');

function parseForwardLine(line) {
  const raw = String(line || '').trim();
  if (!raw || raw.startsWith('#')) return null;
  const normalized = raw.replace('->', ' ');
  let parts = normalized.split(/\s+/);
  if (parts[0] && parts[0].toUpperCase() === 'L') parts = parts.slice(1);
  let local; let remote;
  if (parts.length === 2) [local, remote] = parts;
  else if (parts.length === 3) { local = `${parts[0]}:${parts[1]}`; remote = parts[2]; }
  else throw new Error('Expected: L 127.0.0.1:8080 127.0.0.1:80 or 8080 -> 127.0.0.1:80');
  const endpoint = (value, fallbackHost) => {
    if (!value.includes(':')) return { host: fallbackHost, port: Number(value) };
    const idx = value.lastIndexOf(':');
    return { host: value.slice(0, idx) || fallbackHost, port: Number(value.slice(idx + 1)) };
  };
  const l = endpoint(local, '127.0.0.1');
  const r = endpoint(remote, '127.0.0.1');
  if (!l.port || !r.port) throw new Error('Invalid port in tunnel line');
  return { localHost: l.host, localPort: l.port, remoteHost: r.host, remotePort: r.port, raw };
}

class LocalForwarder {
  constructor(manager, terminalId, client, config) {
    this.manager = manager;
    this.terminalId = terminalId;
    this.client = client;
    this.config = config;
    this.server = null;
  }

  start() {
    this.server = net.createServer(socket => this.handle(socket));
    this.server.listen(this.config.localPort, this.config.localHost, () => {
      this.manager.status(this.terminalId, 'task', `Tunnel ${this.config.localHost}:${this.config.localPort} → ${this.config.remoteHost}:${this.config.remotePort}`);
    });
    this.server.on('error', err => this.manager.status(this.terminalId, 'error', `Tunnel failed: ${err.message}`));
  }

  handle(socket) {
    const srcAddr = socket.remoteAddress || '127.0.0.1';
    const srcPort = socket.remotePort || 0;
    this.client.forwardOut(srcAddr, srcPort, this.config.remoteHost, this.config.remotePort, (err, stream) => {
      if (err) { socket.destroy(); return; }
      socket.pipe(stream).pipe(socket);
    });
  }

  close() {
    try { if (this.server) this.server.close(); } catch {}
  }
}

class TerminalConnectionManager {
  constructor({ send, task, credentialStore, passwordRequester, getSettings }) {
    this.send = send;
    this.task = task;
    this.credentialStore = credentialStore;
    this.passwordRequester = passwordRequester;
    this.getSettings = getSettings;
    this.terminals = new Map();
  }

  status(id, state, message, extra = {}) {
    this.send('terminal:status', { terminalId: id, state, message, ...extra });
  }

  data(id, data) {
    this.send('terminal:data', { terminalId: id, data: Buffer.isBuffer(data) ? data.toString('utf8') : String(data) });
  }

  async create({ terminalId, session, cols = 100, rows = 30 }) {
    this.disconnect(terminalId, true);
    const protocol = String(session.protocol || 'ssh').toLowerCase();
    if (protocol === 'ssh') return this.createSsh({ terminalId, session, cols, rows });
    if (protocol === 'telnet') return this.createTelnet({ terminalId, session });
    if (protocol === 'serial') return this.createSerial({ terminalId, session });
    if (protocol === 'rdp') return this.launchRdp({ terminalId, session });
    throw new Error(`Unknown protocol: ${protocol}`);
  }

  async createSsh({ terminalId, session, cols, rows }) {
    const settings = this.getSettings();
    this.status(terminalId, 'connecting', 'Connecting…');
    const client = new Client();
    const record = { type: 'ssh', session, client, stream: null, cols, rows, manual: false, forwarders: [], decoder: new StringDecoder('utf8') };
    this.terminals.set(terminalId, record);

    const username = session.username || process.env.USERNAME || process.env.USER || 'root';
    const connectConfig = {
      host: session.host,
      port: Number(session.port || 22),
      username,
      readyTimeout: Number(settings.connectTimeout || 15000),
      keepaliveInterval: Number(settings.keepaliveInterval || 30000),
      tryKeyboard: true
    };

    if (session.authMode === 'key') {
      if (!session.keyPath) throw new Error('Private key path is empty');
      connectConfig.privateKey = fs.readFileSync(path.resolve(String(session.keyPath)));
      const phrase = await this.passwordRequester({ terminalId, title: 'Key passphrase', message: `Passphrase for ${path.basename(session.keyPath)}`, allowEmpty: true });
      if (phrase) connectConfig.passphrase = phrase;
    } else if (session.authMode === 'agent') {
      connectConfig.agent = process.env.SSH_AUTH_SOCK;
    } else {
      let password = await this.credentialStore.get(session);
      if (!password) {
        password = await this.passwordRequester({ terminalId, title: 'Password', message: `Password for ${username}@${session.host}`, allowEmpty: false });
        if (!password) throw new Error('Password was not provided');
        if (session.savePassword) await this.credentialStore.set(session, password);
      }
      connectConfig.password = password;
    }

    client.on('keyboard-interactive', (_name, _inst, _lang, prompts, finish) => {
      Promise.all(prompts.map(p => this.passwordRequester({ terminalId, title: 'Keyboard interactive', message: p.prompt, allowEmpty: false })))
        .then(answers => finish(answers.map(v => v || '')))
        .catch(() => finish([]));
    });

    client.on('ready', () => {
      const window = { term: 'xterm-256color', cols: Number(cols || 100), rows: Number(rows || 30), width: 0, height: 0 };
      client.shell(window, (err, stream) => {
        if (err) { this.status(terminalId, 'error', err.message); return; }
        record.stream = stream;
        try { stream.setWindow(Number(rows || 30), Number(cols || 100), 0, 0); } catch {}
        this.status(terminalId, 'connected', `${username}@${session.host}:${session.port}`);
        stream.on('data', data => this.send('terminal:data', { terminalId, data: record.decoder.write(data) }));
        stream.stderr?.on('data', data => this.send('terminal:data', { terminalId, data: record.decoder.write(data) }));
        stream.on('close', () => this.handleClosed(terminalId));
        if (session.startDir) stream.write(`cd ${shellQuote(session.startDir)}\r`);
        this.startForwarders(terminalId, client, session);
      });
    });
    client.on('error', err => this.status(terminalId, 'error', err.message));
    client.on('close', () => this.handleClosed(terminalId));
    client.connect(connectConfig);
    return { ok: true };
  }

  createTelnet({ terminalId, session }) {
    const socket = net.createConnection({ host: session.host, port: Number(session.port || 23) });
    const record = { type: 'telnet', session, socket, manual: false, decoder: new StringDecoder('utf8') };
    this.terminals.set(terminalId, record);
    socket.on('connect', () => this.status(terminalId, 'connected', `telnet://${session.host}:${session.port || 23}`));
    socket.on('data', data => this.send('terminal:data', { terminalId, data: record.decoder.write(data) }));
    socket.on('error', err => this.status(terminalId, 'error', err.message));
    socket.on('close', () => this.handleClosed(terminalId));
    return { ok: true };
  }

  createSerial({ terminalId, session }) {
    let SerialPort;
    try { SerialPort = require('serialport').SerialPort; }
    catch (err) { throw new Error(`serialport is not installed: ${err.message}`); }
    const port = new SerialPort({ path: session.serialPort || session.host, baudRate: Number(session.serialBaud || 9600), autoOpen: true });
    const record = { type: 'serial', session, serial: port, manual: false, decoder: new StringDecoder('utf8') };
    this.terminals.set(terminalId, record);
    port.on('open', () => this.status(terminalId, 'connected', `${session.serialPort || session.host} @ ${session.serialBaud || 9600}`));
    port.on('data', data => this.send('terminal:data', { terminalId, data: record.decoder.write(data) }));
    port.on('error', err => this.status(terminalId, 'error', err.message));
    port.on('close', () => this.handleClosed(terminalId));
    return { ok: true };
  }

  launchRdp({ terminalId, session }) {
    if (process.platform !== 'win32') throw new Error('RDP launch is available on Windows only');
    const target = `${session.host}:${session.port || 3389}`;
    spawn('mstsc.exe', [`/v:${target}`], { detached: true, stdio: 'ignore' }).unref();
    this.status(terminalId, 'connected', `mstsc.exe /v:${target}`);
    return { ok: true };
  }

  write({ terminalId, data }) {
    const rec = this.terminals.get(terminalId);
    if (!rec) return { ok: false, error: 'Terminal is not connected' };
    const buffer = Buffer.from(String(data), 'binary');
    try {
      if (rec.stream) rec.stream.write(buffer);
      else if (rec.socket) rec.socket.write(buffer);
      else if (rec.serial) rec.serial.write(buffer);
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  }

  resize({ terminalId, cols, rows }) {
    const rec = this.terminals.get(terminalId);
    if (!rec) return { ok: false };
    rec.cols = cols; rec.rows = rows;
    try { if (rec.stream?.setWindow) rec.stream.setWindow(Number(rows), Number(cols), 0, 0); } catch {}
    return { ok: true };
  }

  disconnect(terminalId, silent = false) {
    const rec = this.terminals.get(terminalId);
    if (!rec) return { ok: true };
    rec.manual = true;
    for (const f of rec.forwarders || []) f.close();
    try { rec.stream?.end(); } catch {}
    try { rec.client?.end(); } catch {}
    try { rec.socket?.destroy(); } catch {}
    try { rec.serial?.close(); } catch {}
    this.terminals.delete(terminalId);
    if (!silent) this.status(terminalId, 'closed', 'Disconnected');
    return { ok: true };
  }

  handleClosed(terminalId) {
    const rec = this.terminals.get(terminalId);
    if (!rec) return;
    for (const f of rec.forwarders || []) f.close();
    const settings = this.getSettings();
    this.terminals.delete(terminalId);
    this.status(terminalId, 'closed', 'Connection closed');
    if (!rec.manual && settings.reconnect && ['ssh', 'telnet', 'serial'].includes(rec.type)) {
      const delay = Number(settings.reconnectDelay || 5);
      this.status(terminalId, 'reconnect', `Reconnect in ${delay}s…`, { delay });
      setTimeout(() => {
        if (!this.terminals.has(terminalId)) this.create({ terminalId, session: rec.session, cols: rec.cols || 100, rows: rec.rows || 30 }).catch(err => this.status(terminalId, 'error', err.message));
      }, delay * 1000);
    }
  }

  startForwarders(terminalId, client, session) {
    const rec = this.terminals.get(terminalId);
    if (!rec) return;
    const lines = String(session.tunnels || '').split(/\r?\n/);
    for (const line of lines) {
      try {
        const cfg = parseForwardLine(line);
        if (!cfg) continue;
        const f = new LocalForwarder(this, terminalId, client, cfg);
        f.start();
        rec.forwarders.push(f);
      } catch (err) {
        this.status(terminalId, 'error', `Tunnel error: ${err.message}`);
      }
    }
  }

  getSftp(terminalId) {
    const rec = this.terminals.get(terminalId);
    if (!rec || rec.type !== 'ssh' || !rec.client) throw new Error('SSH terminal is not connected');
    return new Promise((resolve, reject) => {
      if (rec.sftp) return resolve(rec.sftp);
      rec.client.sftp((err, sftp) => {
        if (err) reject(err);
        else { rec.sftp = sftp; resolve(sftp); }
      });
    });
  }

  async sftpList({ terminalId, remotePath = '.' }) {
    const sftp = await this.getSftp(terminalId);
    return new Promise((resolve, reject) => {
      sftp.readdir(remotePath, (err, list) => {
        if (err) return reject(err);
        const items = list.map(item => ({
          name: item.filename,
          path: posixJoin(remotePath, item.filename),
          isDirectory: item.longname?.startsWith('d') || Boolean(item.attrs?.isDirectory?.()),
          size: item.attrs?.size || 0,
          mtime: item.attrs?.mtime || 0,
          mode: item.attrs?.mode || 0
        })).sort((a, b) => Number(b.isDirectory) - Number(a.isDirectory) || a.name.localeCompare(b.name));
        resolve({ path: remotePath, items });
      });
    });
  }

  async sftpMkdir({ terminalId, remotePath }) {
    const sftp = await this.getSftp(terminalId);
    const taskId = `mkdir:${terminalId}:${Date.now()}`;
    this.task({ id: taskId, type: 'mkdir', label: `Creating ${remotePath}`, progress: null, state: 'running' });
    return new Promise((resolve, reject) => {
      sftp.mkdir(remotePath, err => {
        this.task({ id: taskId, type: 'mkdir', label: `Created ${remotePath}`, progress: 100, state: err ? 'error' : 'done', error: err?.message });
        if (err) reject(err); else resolve({ ok: true });
      });
    });
  }

  async sftpUpload({ terminalId, localPath, remotePath }) {
    const sftp = await this.getSftp(terminalId);
    const taskId = `upload:${terminalId}:${Date.now()}`;
    const label = `Upload ${path.basename(localPath)}`;
    this.task({ id: taskId, type: 'upload', label, progress: 0, state: 'running' });
    return new Promise((resolve, reject) => {
      sftp.fastPut(localPath, remotePath, {
        step: (transferred, _chunk, total) => this.task({ id: taskId, type: 'upload', label, progress: total ? Math.round(transferred / total * 100) : null, state: 'running' })
      }, err => {
        this.task({ id: taskId, type: 'upload', label, progress: err ? null : 100, state: err ? 'error' : 'done', error: err?.message });
        if (err) reject(err); else resolve({ ok: true, remotePath });
      });
    });
  }

  async sftpDownload({ terminalId, remotePath, localPath }) {
    const sftp = await this.getSftp(terminalId);
    const taskId = `download:${terminalId}:${Date.now()}`;
    const label = `Download ${path.basename(remotePath)}`;
    this.task({ id: taskId, type: 'download', label, progress: 0, state: 'running' });
    return new Promise((resolve, reject) => {
      sftp.fastGet(remotePath, localPath, {
        step: (transferred, _chunk, total) => this.task({ id: taskId, type: 'download', label, progress: total ? Math.round(transferred / total * 100) : null, state: 'running' })
      }, err => {
        this.task({ id: taskId, type: 'download', label, progress: err ? null : 100, state: err ? 'error' : 'done', error: err?.message });
        if (err) reject(err); else resolve({ ok: true, localPath });
      });
    });
  }
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}
function posixJoin(base, name) {
  const b = String(base || '.');
  if (b === '/' || b.endsWith('/')) return `${b}${name}`.replace(/\/+/g, '/');
  return `${b}/${name}`.replace(/\/+/g, '/');
}

module.exports = { TerminalConnectionManager };
