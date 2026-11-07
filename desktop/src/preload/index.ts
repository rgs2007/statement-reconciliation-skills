/**
 * The only bridge between the renderer and the main process.
 *
 * Context isolation is on and node integration is off, so this file defines
 * exactly what the UI can do. Each method maps to one named channel; nothing
 * generic like "invoke(channel, args)" is exposed, because that would hand a
 * compromised renderer the whole main process.
 */
import { contextBridge, ipcRenderer } from 'electron'
import type {
  ClaudeInstallState,
  ClaudeStreamEvent,
  DatasetRole,
  DesktopApi,
  NotebookCell
} from '../shared/types'

const api: DesktopApi = {
  claude: {
    status: () => ipcRenderer.invoke('claude:status'),
    install: () => ipcRenderer.invoke('claude:install'),
    onStatus: (cb: (s: ClaudeInstallState) => void) => {
      const h = (_e: unknown, s: ClaudeInstallState): void => cb(s)
      ipcRenderer.on('claude:status', h)
      return () => ipcRenderer.removeListener('claude:status', h)
    }
  },
  project: {
    create: (name: string, parentDir?: string) => ipcRenderer.invoke('project:create', name, parentDir),
    open: (folder: string) => ipcRenderer.invoke('project:open', folder),
    pickFolder: () => ipcRenderer.invoke('project:pickFolder'),
    pickFiles: () => ipcRenderer.invoke('project:pickFiles'),
    recent: () => ipcRenderer.invoke('project:recent'),
    addFiles: (folder: string, paths: string[]) => ipcRenderer.invoke('project:addFiles', folder, paths),
    setRole: (folder: string, relPath: string, role: DatasetRole | null) =>
      ipcRenderer.invoke('project:setRole', folder, relPath, role),
    saveNotebook: (folder: string, cells: NotebookCell[]) =>
      ipcRenderer.invoke('project:saveNotebook', folder, cells),
    readMemory: (folder: string) => ipcRenderer.invoke('project:readMemory', folder),
    appendMemory: (folder: string, entry: string) =>
      ipcRenderer.invoke('project:appendMemory', folder, entry),
    metrics: (folder: string) => ipcRenderer.invoke('project:metrics', folder),
    questions: (folder: string) => ipcRenderer.invoke('project:questions', folder),
    reports: (folder: string) => ipcRenderer.invoke('project:reports', folder),
    readReport: (folder: string, relPath: string) =>
      ipcRenderer.invoke('project:readReport', folder, relPath)
  },
  chat: {
    send: (folder: string, prompt: string) => ipcRenderer.invoke('chat:send', folder, prompt),
    cancel: () => ipcRenderer.invoke('chat:cancel'),
    onEvent: (cb: (e: ClaudeStreamEvent) => void) => {
      const h = (_e: unknown, ev: ClaudeStreamEvent): void => cb(ev)
      ipcRenderer.on('chat:event', h)
      return () => ipcRenderer.removeListener('chat:event', h)
    }
  }
}

contextBridge.exposeInMainWorld('api', api)
