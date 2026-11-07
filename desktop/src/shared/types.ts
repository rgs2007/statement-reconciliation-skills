/**
 * The contract between the main process and the renderer.
 *
 * Everything that crosses the IPC boundary is declared here so both sides are
 * type-checked against one definition. The renderer never touches the
 * filesystem, never spawns a process and never sees an absolute path it did
 * not receive from main: Electron's security model only holds if the boundary
 * is narrow and explicit.
 */

/** Where the Claude CLI came from, and whether it is usable. */
export type ClaudeInstallState =
  | { status: 'checking' }
  | { status: 'missing'; reason: string }
  | { status: 'installing'; step: string; percent: number }
  | { status: 'ready'; version: string; binPath: string; source: 'system' | 'local' }
  | { status: 'error'; message: string }

/** A file the user added to the project. Copied in, never referenced in place. */
export interface ProjectFile {
  /** Path relative to the project folder, e.g. "sources/opening.csv". */
  relPath: string
  name: string
  bytes: number
  sha256: string
  addedAt: string
  /** What this file is to the reconciliation; null until assigned. */
  role: DatasetRole | null
  rows: number | null
}

export type DatasetRole = 'opening' | 'closing' | 'movements' | 'accounts' | 'other'

export const DATASET_ROLES: DatasetRole[] = [
  'opening',
  'closing',
  'movements',
  'accounts',
  'other'
]

/** One notebook cell. The notebook is the project's visible working record. */
export type NotebookCell =
  | { id: string; kind: 'markdown'; title: string; body: string; createdAt: string }
  | { id: string; kind: 'table'; title: string; columns: string[]; rows: string[][]; createdAt: string }
  | {
      id: string
      kind: 'metrics'
      title: string
      metrics: ReconMetrics
      createdAt: string
    }
  | {
      id: string
      kind: 'chart'
      title: string
      series: { label: string; value: number }[]
      createdAt: string
    }
  | { id: string; kind: 'status'; title: string; steps: RunStep[]; createdAt: string }

export interface RunStep {
  name: string
  state: 'pending' | 'running' | 'done' | 'failed' | 'skipped'
  detail?: string
}

/** The engine's headline figures. Mirrors metrics.json from recon-engine. */
export interface ReconMetrics {
  keys_total: number
  reconciled: number
  reconciled_pct: number
  sign_convention: string
  gap_gross: number
  gap_net: number
  gap_gross_at_parent?: number
  movements_total?: number
  movements_unattributed?: number
  attribution_rate_pct?: number
  materiality?: number
  caveats?: string[]
  coverage?: { steps_executed: string[]; detectors_skipped: string[] }
}

/** A question the engine priced, as produced by questions.py. */
export interface ReconQuestion {
  id: string
  topic: string
  amount_at_stake: number
  share_of_gap: number
  why_it_matters: string
  options: string[]
  default_if_unanswered: string
  risk_if_assumed: 'wrong' | 'incomplete'
  must_state_explicitly: boolean
}

export interface ProjectSummary {
  id: string
  name: string
  folder: string
  createdAt: string
  lastOpenedAt: string
}

export interface ProjectState {
  summary: ProjectSummary
  files: ProjectFile[]
  notebook: NotebookCell[]
  /** Claude session id, so a reopened project resumes rather than restarts. */
  claudeSessionId: string | null
  memory: string
  decisionCount: number
}

/** A chat turn as the renderer stores it. */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  at: string
  /** Tool activity surfaced alongside the text, for transparency. */
  tools?: { name: string; detail: string }[]
  pending?: boolean
}

/** Events streamed from a running Claude turn. */
export type ClaudeStreamEvent =
  | { type: 'session'; sessionId: string }
  | { type: 'text'; text: string }
  | { type: 'tool'; name: string; detail: string }
  | { type: 'notebook'; cell: NotebookCell }
  | { type: 'done'; sessionId: string | null }
  | { type: 'error'; message: string }

/** The API the preload script exposes on window.api. */
export interface DesktopApi {
  claude: {
    status(): Promise<ClaudeInstallState>
    install(): Promise<ClaudeInstallState>
    onStatus(cb: (s: ClaudeInstallState) => void): () => void
  }
  project: {
    create(name: string, parentDir?: string): Promise<ProjectState>
    open(folder: string): Promise<ProjectState>
    pickFolder(): Promise<string | null>
    pickFiles(): Promise<string[]>
    recent(): Promise<ProjectSummary[]>
    addFiles(folder: string, paths: string[]): Promise<ProjectFile[]>
    setRole(folder: string, relPath: string, role: DatasetRole | null): Promise<ProjectFile[]>
    saveNotebook(folder: string, cells: NotebookCell[]): Promise<void>
    readMemory(folder: string): Promise<string>
    appendMemory(folder: string, entry: string): Promise<string>
    metrics(folder: string): Promise<ReconMetrics | null>
    questions(folder: string): Promise<ReconQuestion[]>
    reports(folder: string): Promise<{ name: string; relPath: string }[]>
    readReport(folder: string, relPath: string): Promise<string>
  }
  chat: {
    send(folder: string, prompt: string): Promise<void>
    cancel(): Promise<void>
    onEvent(cb: (e: ClaudeStreamEvent) => void): () => void
  }
}
