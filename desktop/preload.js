const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('finai', {
  platform: process.platform,
  version: '1.0.0',
  isDesktop: true,
});
