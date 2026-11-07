/**
 * Main process: window lifecycle and the IPC surface.
 *
 * All privileged work happens here. The renderer runs with context isolation
 * and no node integration, so every filesystem read, process spawn and dialog
 * goes through a named channel declared in shared/types.ts.
 */
import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import { existsSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'
import type {
  ClaudeInstallState,
  ClaudeStreamEvent,
  DatasetRole,
  NotebookCell
} from '../shared/types'
import { ClaudeCli } from './services/claude-cli'
import { ProjectStore } from './services/project-store'
import { SkillsInstaller } from './services/skills-installer'

const store = new ProjectStore()
let mainWindow: BrowserWindow | null = null
let cli: ClaudeCli
let installer: SkillsInstaller
let installState: ClaudeInstallState = { status: 'checking' }

/** Where the locally installed CLI lives; outside the app bundle so it survives updates. */
function cliInstallDir(): string {
  const dir = join(app.getPath('userData'), 'claude-cli')
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
  return dir
}

/** Bundled skills: packaged under resources/, or the repo's own in development. */
function skillsSourceRoot(): string {
  const packaged = join(process.resourcesPath ?? '', 'skills')
  if (existsSync(packaged)) return packaged
  return join(app.getAppPath(), '..', 'skills')
}

function recentProjectsFile(): string {
  return join(app.getPath('userData'), 'recent-projects.json')
}

function pushState(s: ClaudeInstallState): void {
  installState = s
  mainWindow?.webContents.send('claude:status', s)
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 940,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    backgroundColor: '#0b0e14',
    title: 'FlowingSoft Reconciler',
    icon: join(__dirname, '../../resources/icon.png'),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

  mainWindow.on('ready-to-show', () => mainWindow?.show())

  // External links open in the real browser, never inside the app.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  const devUrl = process.env.ELECTRON_RENDERER_URL
  if (devUrl) void mainWindow.loadURL(devUrl)
  else void mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
}

function readRecent(): { id: string; name: string; folder: string; createdAt: string; lastOpenedAt: string }[] {
  try {
    const fs = require('node:fs') as typeof import('node:fs')
    if (!existsSync(recentProjectsFile())) return []
    return JSON.parse(fs.readFileSync(recentProjectsFile(), 'utf8'))
  } catch {
    return []
  }
}

function rememberRecent(summary: {
  id: string
  name: string
  folder: string
  createdAt: string
  lastOpenedAt: string
}): void {
  const fs = require('node:fs') as typeof import('node:fs')
  const list = readRecent().filter((p) => p.folder !== summary.folder)
  list.unshift(summary)
  fs.writeFileSync(recentProjectsFile(), JSON.stringify(list.slice(0, 12), null, 2))
}

/**
 * The system prompt appended to every turn.
 *
 * It tells Claude where the project is and that MEMORY.md is the resume
 * point. Without this the model would rediscover the project on every turn,
 * which is both slow and a good way to contradict an earlier decision.
 */
function projectSystemPrompt(folder: string): string {
  return [
    `You are working inside a FlowingSoft Reconciler project at: ${folder}`,
    '',
    'Project layout:',
    '  sources/        the files the user uploaded (copies; never edit them)',
    '  runs/run-NNN/   engine output: metrics.json, breaks.csv, residual.csv, questions.json',
    '  reports/        generated reports',
    '  decisions.jsonl the audit log of judgement calls',
    '  MEMORY.md       the narrative record — READ IT FIRST, and append to it',
    '  .claude/skills/ the reconciliation skills, installed project-scoped',
    '',
    'Read MEMORY.md before doing anything so you resume rather than restart.',
    'Write engine output into runs/ and reports into reports/, so the desktop',
    'app can display them in the notebook pane.',
    'When you take a judgement call, append it to decisions.jsonl.',
    'When you learn something a colleague would need to pick this up cold,',
    'append it to MEMORY.md.',
    'Follow the statement-reconciliation skill: compute before asking, and',
    'keep questions to the few that are worth a round-trip.'
  ].join('\n')
}

function registerIpc(): void {
  ipcMain.handle('claude:status', () => installState)

  ipcMain.handle('claude:install', async (): Promise<ClaudeInstallState> => {
    pushState({ status: 'installing', step: 'starting', percent: 5 })
    const res = await cli.install((step, percent) => pushState({ status: 'installing', step, percent }))
    if (res.ok) pushState({ status: 'ready', version: res.version, binPath: res.binPath, source: 'local' })
    else pushState({ status: 'error', message: res.reason })
    return installState
  })

  ipcMain.handle('project:pickFolder', async () => {
    const r = await dialog.showOpenDialog({
      properties: ['openDirectory', 'createDirectory'],
      title: 'Choose where to keep the project'
    })
    return r.canceled ? null : r.filePaths[0]
  })

  // Drag and drop was the only way in, which is undiscoverable: someone who
  // has not been told stands in front of a window with nowhere to click. The
  // filters are a convenience, not a gate — the engine decides what it can
  // read, so "All files" stays available for the odd .txt extract.
  ipcMain.handle('project:pickFiles', async () => {
    const r = await dialog.showOpenDialog({
      properties: ['openFile', 'multiSelections'],
      title: 'Add statement files',
      filters: [
        { name: 'Statements', extensions: ['csv', 'tsv', 'txt', 'xlsx', 'xls', 'xlsm', 'pdf'] },
        { name: 'All files', extensions: ['*'] }
      ]
    })
    return r.canceled ? [] : r.filePaths
  })

  ipcMain.handle('project:create', (_e, name: string, parentDir?: string) => {
    const parent = parentDir ?? join(app.getPath('documents'), 'FlowingSoft Reconciler')
    mkdirSync(parent, { recursive: true })
    const state = store.create(parent, name)
    installer.installInto(state.summary.folder)
    rememberRecent(state.summary)
    return store.read(state.summary.folder)
  })

  ipcMain.handle('project:open', (_e, folder: string) => {
    const state = store.read(folder)
    store.touch(folder)
    // Repair a project whose skills were removed or predate an app update.
    if (!installer.isInstalled(folder)) installer.installInto(folder)
    rememberRecent(state.summary)
    return store.read(folder)
  })

  ipcMain.handle('project:recent', () => readRecent())

  ipcMain.handle('project:addFiles', (_e, folder: string, paths: string[]) =>
    store.addFiles(folder, paths)
  )
  ipcMain.handle('project:setRole', (_e, folder: string, relPath: string, role: DatasetRole | null) =>
    store.setRole(folder, relPath, role)
  )
  ipcMain.handle('project:saveNotebook', (_e, folder: string, cells: NotebookCell[]) =>
    store.saveNotebook(folder, cells)
  )
  ipcMain.handle('project:readMemory', (_e, folder: string) => store.readMemory(folder))
  ipcMain.handle('project:appendMemory', (_e, folder: string, entry: string) =>
    store.appendMemory(folder, entry)
  )
  ipcMain.handle('project:metrics', (_e, folder: string) => store.latestMetrics(folder))
  ipcMain.handle('project:questions', (_e, folder: string) => store.latestQuestions(folder))
  ipcMain.handle('project:reports', (_e, folder: string) => store.reports(folder))
  ipcMain.handle('project:readReport', (_e, folder: string, relPath: string) =>
    store.readReport(folder, relPath)
  )

  ipcMain.handle('chat:send', async (_e, folder: string, prompt: string) => {
    const emit = (ev: ClaudeStreamEvent): void => {
      mainWindow?.webContents.send('chat:event', ev)
    }
    if (installState.status !== 'ready') {
      emit({ type: 'error', message: 'the Claude CLI is not installed yet' })
      return
    }
    const state = store.read(folder)
    await cli.runTurn(
      {
        prompt: `${projectSystemPrompt(folder)}\n\n---\n\n${prompt}`,
        sessionId: state.claudeSessionId,
        cwd: folder,
        addDirs: [folder],
        permissionMode: 'acceptEdits'
      },
      (ev) => {
        if (ev.type === 'session') store.setSessionId(folder, ev.sessionId)
        if (ev.type === 'done' && ev.sessionId) store.setSessionId(folder, ev.sessionId)
        emit(ev)
      }
    )
  })

  ipcMain.handle('chat:cancel', () => cli.cancel())
}

void app.whenReady().then(async () => {
  cli = new ClaudeCli(cliInstallDir())
  installer = new SkillsInstaller(skillsSourceRoot())
  registerIpc()
  createWindow()

  const found = await cli.detect()
  pushState(
    found.ok
      ? { status: 'ready', version: found.version, binPath: found.binPath, source: found.source }
      : { status: 'missing', reason: found.reason }
  )

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
