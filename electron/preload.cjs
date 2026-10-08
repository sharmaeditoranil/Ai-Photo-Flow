const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('dialog:openDirectory'),
  getSamplePhotosPath: () => ipcRenderer.invoke('app:getSamplePhotosPath'),
  isElectron: true,
  platform: process.platform
});
