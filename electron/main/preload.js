import { contextBridge } from 'electron';

const backendUrl = 'http://127.0.0.1:8000';

contextBridge.exposeInMainWorld('parisAPI', {
  backendUrl,
  appVersion: process.env.npm_package_version || '0.2.0'
});
