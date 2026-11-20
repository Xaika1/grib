const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('gribDesktop', { platform: process.platform });
