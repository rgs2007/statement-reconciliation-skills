/**
 * Project rail: the install state, the files and their roles, and the reports.
 *
 * Roles are editable here because the engine needs to know which file is the
 * opening balance and which is the transaction extract, and the file name is
 * only a guess. Confirming a guess is one click; being asked in chat is a
 * round-trip.
 */
import type { DatasetRole, ProjectFile, ClaudeInstallState } from '@shared/types'
import { DATASET_ROLES } from '@shared/types'
import { ago, bytes } from '../lib/format'
import { ROLE_LABELS } from '../store/useApp'

export function InstallBadge({
  state,
  onInstall
}: {
  state: ClaudeInstallState
  onInstall: () => void
}): JSX.Element {
  if (state.status === 'ready') {
    return (
      <div className="flex items-center gap-2 text-xs text-ink-500" data-testid="install-ready">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        Claude {state.version}
        <span className="text-ink-700">({state.source})</span>
      </div>
    )
  }
  if (state.status === 'installing') {
    return (
      <div className="text-xs text-flow-300" data-testid="install-progress">
        <div className="mb-1 flex justify-between">
          <span>{state.step}</span>
          <span className="font-mono">{state.percent}%</span>
        </div>
        <div className="h-1 overflow-hidden rounded-full bg-ink-800">
          <div className="h-full bg-flow-500 transition-all" style={{ width: `${state.percent}%` }} />
        </div>
      </div>
    )
  }
  if (state.status === 'checking') {
    return <div className="text-xs text-ink-500">Looking for the Claude CLI…</div>
  }
  return (
    <div className="space-y-2" data-testid="install-needed">
      <p className="text-xs leading-relaxed text-amber-400">
        {state.status === 'error' ? state.message : state.reason}
      </p>
      <button type="button" onClick={onInstall} className="btn-primary w-full justify-center">
        Install Claude
      </button>
      <p className="text-[11px] leading-relaxed text-ink-600">
        Installed into this app&rsquo;s own folder — nothing on your machine is changed.
      </p>
    </div>
  )
}

export function FileList({
  files,
  onRole
}: {
  files: ProjectFile[]
  onRole: (relPath: string, role: DatasetRole | null) => void
}): JSX.Element {
  if (!files.length) {
    return (
      <p className="text-xs leading-relaxed text-ink-600">
        No files yet. Drop CSV, Excel or PDF statements anywhere in the window.
      </p>
    )
  }
  return (
    <ul className="space-y-2" data-testid="file-list">
      {files.map((f) => (
        <li key={f.relPath} className="rounded-md border border-ink-800 bg-ink-950/50 p-2.5">
          <div className="truncate text-xs font-medium text-ink-200" title={f.name}>
            {f.name}
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-[11px] text-ink-600">
            <span>{bytes(f.bytes)}</span>
            {f.rows !== null ? <span>{f.rows.toLocaleString()} rows</span> : null}
            <span>{ago(f.addedAt)}</span>
          </div>
          <select
            value={f.role ?? ''}
            aria-label={`Role for ${f.name}`}
            onChange={(e) => onRole(f.relPath, (e.target.value || null) as DatasetRole | null)}
            className="mt-2 w-full rounded border border-ink-800 bg-ink-900 px-2 py-1 text-[11px] text-ink-200 focus:border-flow-600 focus:outline-none"
          >
            <option value="">Role not set</option>
            {DATASET_ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
          <div className="mt-1 font-mono text-[10px] text-ink-700" title={f.sha256}>
            {f.sha256.slice(0, 16)}…
          </div>
        </li>
      ))}
    </ul>
  )
}

export function ReportList({
  reports,
  onOpen
}: {
  reports: { name: string; relPath: string }[]
  onOpen: (relPath: string) => void
}): JSX.Element {
  if (!reports.length) {
    return <p className="text-xs text-ink-600">No reports yet.</p>
  }
  return (
    <ul className="space-y-1" data-testid="report-list">
      {reports.map((r) => (
        <li key={r.relPath}>
          <button
            type="button"
            onClick={() => onOpen(r.relPath)}
            className="w-full truncate rounded px-2 py-1.5 text-left text-xs text-ink-300 transition-colors hover:bg-ink-800 hover:text-ink-100"
          >
            {r.name}
          </button>
        </li>
      ))}
    </ul>
  )
}
