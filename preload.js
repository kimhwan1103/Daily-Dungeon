const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('widget', {
  moveWindow: (dx, dy) => ipcRenderer.send('window-move', { deltaX: dx, deltaY: dy }),
  toggleVisibility: () => ipcRenderer.send('toggle-visibility'),
  toggleDesktopMode: () => ipcRenderer.send('toggle-desktop-mode'),
  setAlwaysOnTop: (v) => ipcRenderer.send('set-always-on-top', v),
  setOpacity: (v) => ipcRenderer.send('set-opacity', v),
  toggleClickThrough: (v) => ipcRenderer.send('toggle-click-through', v),
  selectAvatar: () => ipcRenderer.invoke('select-avatar'),
  selectProofImage: () => ipcRenderer.invoke('select-proof-image'),
  onDesktopModeChanged: (cb) => ipcRenderer.on('desktop-mode-changed', (_, v) => cb(v)),
  onClickThroughChanged: (cb) => ipcRenderer.on('click-through-changed', (_, v) => cb(v)),
});
