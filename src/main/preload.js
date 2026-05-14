const { contextBridge, ipcRenderer } = require('electron');

const validInvoke = new Set([
  'app:get-bootstrap', 'settings:save', 'settings:restart',
  'sessions:save-all', 'presets:save-all',
  'credentials:set', 'credentials:get', 'credentials:delete',
  'terminal:create', 'terminal:write', 'terminal:resize', 'terminal:disconnect',
  'sftp:list', 'sftp:mkdir', 'sftp:upload', 'sftp:download',
  'dialog:open-file', 'dialog:save-file', 'clipboard:read', 'clipboard:write',
  'window:minimize', 'window:maximize', 'window:close'
]);
const validEvents = new Set([
  'terminal:data', 'terminal:status', 'terminal:closed', 'terminal:password-request',
  'task:update', 'window:maximized'
]);

contextBridge.exposeInMainWorld('orion', {
  platform: process.platform,
  invoke(channel, payload) {
    if (!validInvoke.has(channel)) throw new Error(`Blocked IPC channel: ${channel}`);
    return ipcRenderer.invoke(channel, payload);
  },
  on(channel, callback) {
    if (!validEvents.has(channel)) throw new Error(`Blocked IPC event: ${channel}`);
    const listener = (_event, data) => callback(data);
    ipcRenderer.on(channel, listener);
    return () => ipcRenderer.removeListener(channel, listener);
  },
  sendPasswordResponse(payload) {
    ipcRenderer.send('terminal:password-response', payload);
  }
});
