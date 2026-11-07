/**
 * The shell: notebook on the left, chat on the right.
 *
 * The split is deliberate and fixed rather than a free-form workspace. The
 * notebook is where the reconciliation accumulates and the chat is where it
 * is driven; keeping them side by side means the figures stay visible while
 * the questions are answered, which is exactly the moment someone would
 * otherwise lose track of what they are confirming.
 */
import { useCallback, useEffect, useState } from 'react'
import type { DatasetRole } from '@shared/types'
import { ChatPane } from './components/ChatPane'
import { NotebookPane } from './components/NotebookPane'
import { FileList, InstallBadge, ReportList } from './components/Sidebar'
import { useApp } from './store/useApp'
import { BRAND, FLOW_MARK_SVG } from './theme/brand'

function Logo(): JSX.Element {
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-7 w-7 shrink-0" dangerouslySetInnerHTML={{ __html: FLOW_MARK_SVG }} />
      <div className="leading-tight">
        <div className="text-sm font-semibold tracking-tight text-ink-100">
          {BRAND.company}
          <span className="font-normal text-flow-400"> {BRAND.product}</span>
        </div>
        <div className="text-[10px] text-ink-600">{BRAND.tagline}</div>
      </div>
    </div>
  )
}

function Welcome({
  onCreate,
  onOpen
}: {
  onCreate: () => void
  onOpen: () => void
}): JSX.Element {
  const recent = useApp((s) => s.recent)
  const setProject = useApp((s) => s.setProject)

  return (
    <div className="flex h-full items-center justify-center p-10">
      <div className="w-full max-w-lg">
        <div
          className="mx-auto mb-5 h-14 w-14"
          dangerouslySetInnerHTML={{ __html: FLOW_MARK_SVG }}
        />
        <h1 className="text-center text-xl font-semibold text-ink-100">{BRAND.productFull}</h1>
        <p className="mt-2 text-center text-sm leading-relaxed text-ink-500">
          Work out why two sets of figures disagree, with the evidence, the confidence level and
          the remediation for each difference.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <button type="button" onClick={onCreate} className="btn-primary">
            New reconciliation
          </button>
          <button type="button" onClick={onOpen} className="btn-ghost">
            Open a project
          </button>
        </div>

        {recent.length ? (
          <div className="mt-8">
            <div className="label mb-2">Recent</div>
            <ul className="space-y-1" data-testid="recent-list">
              {recent.map((p) => (
                <li key={p.folder}>
                  <button
                    type="button"
                    onClick={() =>
                      void window.api.project.open(p.folder).then((s) => setProject(s))
                    }
                    className="w-full rounded-md border border-ink-800 px-3 py-2 text-left transition-colors hover:bg-ink-900"
                  >
                    <div className="text-sm text-ink-200">{p.name}</div>
                    <div className="truncate text-[11px] text-ink-600">{p.folder}</div>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function App(): JSX.Element {
  const s = useApp()
  const [dragging, setDragging] = useState(false)

  // Refresh the notebook's data sources after a turn: the AI writes files,
  // so the pane has to re-read rather than be told what changed.
  const refreshDerived = useCallback(async (folder: string) => {
    const [metrics, questions, reports] = await Promise.all([
      window.api.project.metrics(folder),
      window.api.project.questions(folder),
      window.api.project.reports(folder)
    ])
    useApp.getState().setMetrics(metrics)
    useApp.getState().setQuestions(questions)
    useApp.getState().setReports(reports)
  }, [])

  useEffect(() => {
    void window.api.claude.status().then((st) => useApp.getState().setInstall(st))

    // Reopen the project that was last worked on. A reconciliation spans
    // days and the whole point of the project folder is that it continues
    // where it stopped, so landing on a welcome screen every launch would
    // put a click between the user and their own work. If the folder has
    // since been moved or deleted, fall back to the welcome screen rather
    // than failing to start.
    void window.api.project.recent().then(async (r) => {
      useApp.getState().setRecent(r)
      const last = r[0]
      if (!last || useApp.getState().project) return
      try {
        const st = await window.api.project.open(last.folder)
        useApp.getState().setProject(st)
        await refreshDerived(last.folder)
      } catch {
        // Its folder is gone; the welcome screen lists the rest.
      }
    })
    const offStatus = window.api.claude.onStatus((st) => useApp.getState().setInstall(st))

    const offChat = window.api.chat.onEvent((ev) => {
      const app = useApp.getState()
      switch (ev.type) {
        case 'text':
          app.appendToPending(ev.text)
          break
        case 'tool':
          app.addToolActivity(ev.name, ev.detail)
          break
        case 'notebook':
          app.addCell(ev.cell)
          break
        case 'error':
          app.addMessage({
            id: `e-${Date.now()}`,
            role: 'system',
            text: ev.message,
            at: new Date().toISOString()
          })
          app.finishPending()
          break
        case 'done': {
          app.finishPending()
          const folder = app.project?.summary.folder
          if (folder) {
            void refreshDerived(folder)
            void window.api.project.saveNotebook(folder, useApp.getState().notebook)
          }
          break
        }
        default:
          break
      }
    })

    return () => {
      offStatus()
      offChat()
    }
  }, [refreshDerived])

  const project = s.project

  const createProject = async (): Promise<void> => {
    const name = `Reconciliation ${new Date().toISOString().slice(0, 10)}`
    const st = await window.api.project.create(name)
    s.setProject(st)
    await refreshDerived(st.summary.folder)
  }

  const openProject = async (): Promise<void> => {
    const folder = await window.api.project.pickFolder()
    if (!folder) return
    try {
      const st = await window.api.project.open(folder)
      s.setProject(st)
      await refreshDerived(folder)
    } catch (e) {
      s.setError(e instanceof Error ? e.message : String(e))
    }
  }

  const onDrop = async (e: React.DragEvent): Promise<void> => {
    e.preventDefault()
    setDragging(false)
    if (!project) return
    const paths = Array.from(e.dataTransfer.files)
      .map((f) => (f as File & { path?: string }).path)
      .filter((p): p is string => Boolean(p))
    if (!paths.length) return
    const files = await window.api.project.addFiles(project.summary.folder, paths)
    s.setFiles(files)
  }

  const pickFiles = async (): Promise<void> => {
    if (!project) return
    const paths = await window.api.project.pickFiles()
    if (!paths.length) return
    const files = await window.api.project.addFiles(project.summary.folder, paths)
    s.setFiles(files)
  }

  const send = async (text: string): Promise<void> => {
    if (!project) return
    s.addMessage({ id: `u-${Date.now()}`, role: 'user', text, at: new Date().toISOString() })
    s.setBusy(true)
    await window.api.chat.send(project.summary.folder, text)
  }

  const openReport = async (relPath: string): Promise<void> => {
    if (!project) return
    const body = await window.api.project.readReport(project.summary.folder, relPath)
    s.addCell({
      id: `r-${Date.now()}`,
      kind: 'markdown',
      title: relPath,
      body,
      createdAt: new Date().toISOString()
    })
  }

  const setRole = async (relPath: string, role: DatasetRole | null): Promise<void> => {
    if (!project) return
    const files = await window.api.project.setRole(project.summary.folder, relPath, role)
    s.setFiles(files)
  }

  const notReady = s.install.status !== 'ready'

  return (
    <div
      className="flex h-screen flex-col bg-ink-950"
      onDragOver={(e) => {
        e.preventDefault()
        if (project) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => void onDrop(e)}
    >
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-ink-800 px-4">
        <Logo />
        {project ? (
          <div className="min-w-0">
            <div className="truncate text-xs font-medium text-ink-300">{project.summary.name}</div>
            <div className="truncate text-[10px] text-ink-700">{project.summary.folder}</div>
          </div>
        ) : null}
        <div className="ml-auto flex items-center gap-4">
          {project ? (
            <span className="text-[11px] text-ink-600">
              {project.decisionCount} decision{project.decisionCount === 1 ? '' : 's'} recorded
            </span>
          ) : null}
          <InstallBadge
            state={s.install}
            onInstall={() => void window.api.claude.install()}
          />
        </div>
      </header>

      {s.error ? (
        <div className="border-b border-red-900/60 bg-red-950/40 px-4 py-2 text-xs text-red-200">
          {s.error}
        </div>
      ) : null}

      {!project ? (
        <main className="flex-1 overflow-hidden">
          <Welcome onCreate={() => void createProject()} onOpen={() => void openProject()} />
        </main>
      ) : (
        <main className="flex min-h-0 flex-1">
          <aside className="w-60 shrink-0 space-y-5 overflow-y-auto border-r border-ink-800 p-4">
            <section>
              <div className="label mb-2">Files</div>
              <FileList
                files={project.files}
                onRole={(p, r) => void setRole(p, r)}
                onAdd={() => void pickFiles()}
              />
            </section>
            <section>
              <div className="label mb-2">Reports</div>
              <ReportList reports={s.reports} onOpen={(p) => void openReport(p)} />
            </section>
            {s.questions.length ? (
              <section>
                <div className="label mb-2">Open questions</div>
                <p className="text-xs leading-relaxed text-ink-500">
                  {s.questions.length} outstanding, worth{' '}
                  {s.questions
                    .reduce((a, q) => a + q.amount_at_stake, 0)
                    .toLocaleString('en-US', { maximumFractionDigits: 0 })}
                </p>
              </section>
            ) : null}
          </aside>

          <section className="min-w-0 flex-1 overflow-y-auto" data-testid="notebook-pane">
            {s.metrics && !s.notebook.some((c) => c.kind === 'metrics') ? (
              <div className="p-5 pb-0">
                <div className="card p-4">
                  <h3 className="mb-3 text-sm font-semibold text-ink-100">
                    Latest run
                  </h3>
                  <NotebookPane
                    cells={[
                      {
                        id: 'live-metrics',
                        kind: 'metrics',
                        title: 'Reconciliation result',
                        metrics: s.metrics,
                        createdAt: new Date().toISOString()
                      }
                    ]}
                  />
                </div>
              </div>
            ) : null}
            <NotebookPane cells={s.notebook} onRemove={(id) => s.removeCell(id)} />
          </section>

          <aside className="flex w-[30rem] shrink-0 flex-col border-l border-ink-800">
            <ChatPane
              messages={s.messages}
              busy={s.busy}
              disabled={notReady}
              disabledReason={notReady ? 'Install Claude to start the conversation.' : undefined}
              onSend={(t) => void send(t)}
              onCancel={() => void window.api.chat.cancel()}
            />
          </aside>
        </main>
      )}

      {dragging ? (
        <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-flow-950/70 backdrop-blur-sm">
          <div className="rounded-lg border-2 border-dashed border-flow-500 px-10 py-7 text-sm font-medium text-flow-200">
            Drop statement files to add them to the project
          </div>
        </div>
      ) : null}
    </div>
  )
}
