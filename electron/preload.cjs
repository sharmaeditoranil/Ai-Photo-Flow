const { contextBridge, ipcRenderer } = require('electron');

let backendPort = 8000;
try {
  backendPort = ipcRenderer.sendSync('backend:port') || 8000;
} catch (e) {}

contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('dialog:openDirectory'),
  getSamplePhotosPath: () => ipcRenderer.invoke('app:getSamplePhotosPath'),
  getBackendStatus: () => ipcRenderer.invoke('backend:status'),
  openExternal: (url) => ipcRenderer.invoke('app:openExternal', url),
  backendPort,
  isElectron: true,
  platform: process.platform
});
