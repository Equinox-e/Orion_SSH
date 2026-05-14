const path = require('path');
const { app, BrowserWindow, ipcMain, dialog, clipboard, nativeTheme } = require('electron');
const { Store } = require('./store');
const { CredentialStore } = require('./credentials');
const { TerminalConnectionManager } = require('./ssh-manager');

let win = null;
let store = null;
let credentialStore = null;
let manager = null;
let passwordWaiters = new Map();

function createWindow() {
  store = new Store();
  credentialStore = new CredentialStore(store.dir);

  win = new BrowserWindow({
    width: 1360,
    height: 820,
    minWidth: 980,
    minHeight: 640,
    backgroundColor: '#0b1220',
    frame: false,
    show: false,
    title: 'OrionSSH',
    icon: path.join(app.getAppPath(), 'assets', 'orionssh.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  manager = new TerminalConnectionManager({
    credentialStore,
    getSettings: () => store.getSettings(),
    send: (channel, payload) => {
      if (win && !win.isDestroyed()) win.webContents.send(channel, payload);
    },
    task: payload => {
      if (win && !win.isDestroyed()) win.webContents.send('task:update', payload);
    },
    passwordRequester: requestPassword
  });

  const html = path.join(app.getAppPath(), 'dist-renderer', 'index.html');
  win.loadFile(html);
  win.once('ready-to-show', () => win.show());
  win.on('maximize', () => win.webContents.send('window:maximized', true));
  win.on('unmaximize', () => win.webContents.send('window:maximized', false));
}

function requestPassword(payload) {
  return new Promise(resolve => {
    const requestId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    passwordWaiters.set(requestId, resolve);
    win.webContents.send('terminal:password-request', { ...payload, requestId });
    setTimeout(() => {
      if (passwordWaiters.has(requestId)) {
        passwordWaiters.delete(requestId);
        resolve(null);
      }
    }, 120000);
  });
}

app.name = 'OrionSSH';
app.whenReady().then(() => {
  nativeTheme.themeSource = 'dark';
  registerIpc();
  createWindow();
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });

function registerIpc() {
  ipcMain.handle('app:get-bootstrap', () => store.getBootstrap());
  ipcMain.handle('settings:save', (_e, settings) => store.saveSettings(settings));
  ipcMain.handle('settings:restart', () => {
    // Electron relaunch is more reliable when we pass the current executable
    // explicitly. In dev mode process.argv[1] is the app folder; in packaged
    // mode there are usually no extra args.
    const args = process.argv.slice(1).filter(arg => arg !== '--restarted');
    app.relaunch({ execPath: process.execPath, args: [...args, '--restarted'] });
    app.exit(0);
    return { ok: true };
  });
  ipcMain.handle('sessions:save-all', (_e, sessions) => store.saveSessions(sessions));
  ipcMain.handle('presets:save-all', (_e, presets) => store.savePresets(presets));

  ipcMain.handle('credentials:get', (_e, session) => credentialStore.get(session));
  ipcMain.handle('credentials:set', (_e, { session, password }) => credentialStore.set(session, password));
  ipcMain.handle('credentials:delete', (_e, session) => credentialStore.delete(session));

  ipcMain.handle('terminal:create', (_e, payload) => manager.create(payload));
  ipcMain.handle('terminal:write', (_e, payload) => manager.write(payload));
  ipcMain.handle('terminal:resize', (_e, payload) => manager.resize(payload));
  ipcMain.handle('terminal:disconnect', (_e, payload) => manager.disconnect(payload.terminalId));
  ipcMain.on('terminal:password-response', (_e, { requestId, value }) => {
    const resolve = passwordWaiters.get(requestId);
    if (resolve) {
      passwordWaiters.delete(requestId);
      resolve(value);
    }
  });

  ipcMain.handle('sftp:list', (_e, payload) => manager.sftpList(payload));
  ipcMain.handle('sftp:mkdir', (_e, payload) => manager.sftpMkdir(payload));
  ipcMain.handle('sftp:upload', (_e, payload) => manager.sftpUpload(payload));
  ipcMain.handle('sftp:download', (_e, payload) => manager.sftpDownload(payload));

  ipcMain.handle('dialog:open-file', async (_e, options) => {
    const result = await dialog.showOpenDialog(win, options || { properties: ['openFile'] });
    return result.canceled ? [] : result.filePaths;
  });
  ipcMain.handle('dialog:save-file', async (_e, options) => {
    const result = await dialog.showSaveDialog(win, options || {});
    return result.canceled ? null : result.filePath;
  });
  ipcMain.handle('clipboard:read', () => clipboard.readText());
  ipcMain.handle('clipboard:write', (_e, text) => { clipboard.writeText(String(text || '')); return { ok: true }; });

  ipcMain.handle('window:minimize', () => { win.minimize(); return true; });
  ipcMain.handle('window:maximize', () => { win.isMaximized() ? win.unmaximize() : win.maximize(); return win.isMaximized(); });
  ipcMain.handle('window:close', () => { win.close(); return true; });
}
