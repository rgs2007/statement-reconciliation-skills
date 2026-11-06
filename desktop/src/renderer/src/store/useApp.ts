/**
 * Application state.
 *
 * Zustand rather than Redux: the state here is small and mostly derived from
 * disk, so the ceremony of actions and reducers would not buy anything. The
 * rule the store enforces is that the project folder is the source of truth —
 * state is a cache of it, and every mutation writes through.
 */
import { create } from 'zustand'
import type {
  ChatMessage,
  ClaudeInstallState,
  DatasetRole,
  NotebookCell,
  ProjectFile,
  ProjectState,
  ProjectSummary,
  ReconMetrics,
  ReconQuestion
} from '@shared/types'

export interface AppState {
  install: ClaudeInstallState
  project: ProjectState | null
  recent: ProjectSummary[]
  messages: ChatMessage[]
  notebook: NotebookCell[]
  metrics: ReconMetrics | null
  questions: ReconQuestion[]
  reports: { name: string; relPath: string }[]
  busy: boolean
  error: string | null

  setInstall(s: ClaudeInstallState): void
  setProject(p: ProjectState | null): void
  setRecent(r: ProjectSummary[]): void
  setFiles(files: ProjectFile[]): void
  addMessage(m: ChatMessage): void
  /** Append streamed text to the open assistant turn, creating it if needed. */
  appendToPending(text: string): void
  addToolActivity(name: string, detail: string): void
  finishPending(): void
  setNotebook(cells: NotebookCell[]): void
  addCell(cell: NotebookCell): void
  removeCell(id: string): void
  setMetrics(m: ReconMetrics | null): void
  setQuestions(q: ReconQuestion[]): void
  setReports(r: { name: string; relPath: string }[]): void
  setBusy(b: boolean): void
  setError(e: string | null): void
  reset(): void
}

const newId = (): string => `m-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`

export const useApp = create<AppState>((set) => ({
  install: { status: 'checking' },
  project: null,
  recent: [],
  messages: [],
  notebook: [],
  metrics: null,
  questions: [],
  reports: [],
  busy: false,
  error: null,

  setInstall: (install) => set({ install }),
  setProject: (project) =>
    set({ project, notebook: project?.notebook ?? [], messages: [], error: null }),
  setRecent: (recent) => set({ recent }),
  setFiles: (files) =>
    set((s) => (s.project ? { project: { ...s.project, files } } : {})),

  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),

  appendToPending: (text) =>
    set((s) => {
      const last = s.messages[s.messages.length - 1]
      if (last && last.role === 'assistant' && last.pending) {
        const updated = { ...last, text: last.text + text }
        return { messages: [...s.messages.slice(0, -1), updated] }
      }
      return {
        messages: [
          ...s.messages,
          { id: newId(), role: 'assistant', text, at: new Date().toISOString(), pending: true }
        ]
      }
    }),

  addToolActivity: (name, detail) =>
    set((s) => {
      const last = s.messages[s.messages.length - 1]
      const entry = { name, detail }
      if (last && last.role === 'assistant' && last.pending) {
        const updated = { ...last, tools: [...(last.tools ?? []), entry] }
        return { messages: [...s.messages.slice(0, -1), updated] }
      }
      return {
        messages: [
          ...s.messages,
          {
            id: newId(),
            role: 'assistant',
            text: '',
            at: new Date().toISOString(),
            pending: true,
            tools: [entry]
          }
        ]
      }
    }),

  finishPending: () =>
    set((s) => {
      const last = s.messages[s.messages.length - 1]
      if (!last?.pending) return { busy: false }
      return {
        messages: [...s.messages.slice(0, -1), { ...last, pending: false }],
        busy: false
      }
    }),

  setNotebook: (notebook) => set({ notebook }),
  addCell: (cell) => set((s) => ({ notebook: [...s.notebook, cell] })),
  removeCell: (id) => set((s) => ({ notebook: s.notebook.filter((c) => c.id !== id) })),
  setMetrics: (metrics) => set({ metrics }),
  setQuestions: (questions) => set({ questions }),
  setReports: (reports) => set({ reports }),
  setBusy: (busy) => set({ busy }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      project: null,
      messages: [],
      notebook: [],
      metrics: null,
      questions: [],
      reports: [],
      busy: false,
      error: null
    })
}))

/** Role options for the file list, kept here so the UI and tests agree. */
export const ROLE_LABELS: Record<DatasetRole, string> = {
  opening: 'Opening balance',
  closing: 'Closing balance',
  movements: 'Transactions',
  accounts: 'Chart of accounts',
  other: 'Other'
}
