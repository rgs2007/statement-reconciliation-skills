/**
 * The project folder — the whole state of a reconciliation, on disk.
 *
 * Everything lives in one folder the user can see, back up, copy to another
 * machine or hand to a colleague: uploaded sources, the engine's runs, the
 * decision log, the generated reports, the notebook and MEMORY.md. Nothing
 * important is held only in the app's own storage, so closing the app loses
 * nothing and reopening the folder resumes exactly where it stopped.
 *
 *   <project>/
 *     project.json          name, files and their roles, Claude session id
 *     MEMORY.md             the narrative record the AI reads on resume
 *     decisions.jsonl       the audit log (append-only, written by the skills)
 *     notebook.json         the notebook cells
 *     sources/              copies of the user's files, never the originals
 *     runs/run-NNN/         engine output: metrics, breaks, residual, questions
 *     reports/              generated reports
 *     .claude/skills/       the reconciliation skills, project-scoped
 *
 * Uploads are copied in rather than referenced. A reconciliation that points
 * at a file somewhere else silently changes meaning when that file moves or
 * is edited, and the sha256 recorded here is what makes a re-run provably the
 * same input.
 */
import { createHash } from 'node:crypto'
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync
} from 'node:fs'
import { basename, join } from 'node:path'
import type {
  DatasetRole,
  NotebookCell,
  ProjectFile,
  ProjectState,
  ReconMetrics,
  ReconQuestion
} from '../../shared/types'

export const PROJECT_FILE = 'project.json'
export const MEMORY_FILE = 'MEMORY.md'
export const NOTEBOOK_FILE = 'notebook.json'
export const DECISIONS_FILE = 'decisions.jsonl'
export const SOURCES_DIR = 'sources'
export const RUNS_DIR = 'runs'
export const REPORTS_DIR = 'reports'

interface ProjectJson {
  id: string
  name: string
  createdAt: string
  lastOpenedAt: string
  files: ProjectFile[]
  claudeSessionId: string | null
}

export function sha256File(path: string): string {
  return createHash('sha256').update(readFileSync(path)).digest('hex')
}

/** A filesystem-safe folder name that still resembles what the user typed. */
export function slugify(name: string): string {
  const slug = name
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
    .slice(0, 48)
  return slug || 'reconciliation'
}

/** Count data rows without loading the file into memory as one string. */
export function countCsvRows(path: string): number | null {
  try {
    const text = readFileSync(path, 'utf8')
    const lines = text.split('\n').filter((l) => l.trim() !== '')
    return Math.max(lines.length - 1, 0)
  } catch {
    return null
  }
}

/** Guess a file's role from its name, so the user usually just confirms. */
export function guessRole(fileName: string): DatasetRole | null {
  const n = fileName.toLowerCase()
  const has = (...words: string[]): boolean => words.some((w) => n.includes(w))
  // Checked before the balance words: "initial_balance" contains "balance".
  if (has('initial', 'opening', 'saldo_inicial', 'abertura')) return 'opening'
  if (has('final', 'closing', 'saldo_final', 'fechamento', 'encerramento')) return 'closing'
  if (has('movement', 'movimento', 'transaction', 'lancamento', 'lançamento', 'ledger', 'razao'))
    return 'movements'
  if (has('account', 'conta', 'chart', 'plano')) return 'accounts'
  if (has('balance', 'saldo', 'trial')) return 'opening'
  return null
}

const MEMORY_TEMPLATE = (name: string, when: string): string => `# MEMORY — ${name}

Created ${when} by FlowingSoft Reconciler.

This file is the project's narrative record. It is read at the start of every
session so work can resume without repeating the discovery, and it is appended
to as decisions are taken. Figures belong in \`runs/\` and reasons belong in
\`decisions.jsonl\`; what goes here is the story a colleague would need to pick
this up cold.

## Scope

_Not yet established._

## What the data looks like

_Not yet profiled._

## Decisions taken

_None yet. The authoritative log is \`decisions.jsonl\`._

## Open questions

_None yet._

## Session log

- ${when} — project created.
`

export class ProjectStore {
  /**
   * Create a new project folder. Does not overwrite an existing one: a
   * second project with the same name gets a suffix rather than silently
   * merging into the first.
   */
  create(parentDir: string, name: string): ProjectState {
    const now = new Date().toISOString()
    let folder = join(parentDir, slugify(name))
    let n = 2
    while (existsSync(folder)) folder = join(parentDir, `${slugify(name)}-${n++}`)

    for (const d of ['', SOURCES_DIR, RUNS_DIR, REPORTS_DIR, join('.claude', 'skills')]) {
      mkdirSync(join(folder, d), { recursive: true })
    }

    const json: ProjectJson = {
      id: `${slugify(name)}-${Date.now().toString(36)}`,
      name,
      createdAt: now,
      lastOpenedAt: now,
      files: [],
      claudeSessionId: null
    }
    writeFileSync(join(folder, PROJECT_FILE), JSON.stringify(json, null, 2))
    writeFileSync(join(folder, MEMORY_FILE), MEMORY_TEMPLATE(name, now.slice(0, 10)))
    writeFileSync(join(folder, NOTEBOOK_FILE), JSON.stringify([], null, 2))
    if (!existsSync(join(folder, DECISIONS_FILE))) writeFileSync(join(folder, DECISIONS_FILE), '')

    return this.read(folder)
  }

  /** Read a project folder into state, repairing anything missing. */
  read(folder: string): ProjectState {
    const pPath = join(folder, PROJECT_FILE)
    if (!existsSync(pPath)) {
      throw new Error(`that folder is not a reconciliation project (no ${PROJECT_FILE})`)
    }
    const json = JSON.parse(readFileSync(pPath, 'utf8')) as ProjectJson

    // Re-create anything a user may have deleted by hand, rather than
    // failing to open a project over a missing empty folder.
    for (const d of [SOURCES_DIR, RUNS_DIR, REPORTS_DIR]) {
      if (!existsSync(join(folder, d))) mkdirSync(join(folder, d), { recursive: true })
    }

    return {
      summary: {
        id: json.id,
        name: json.name,
        folder,
        createdAt: json.createdAt,
        lastOpenedAt: json.lastOpenedAt
      },
      files: json.files ?? [],
      notebook: this.readNotebook(folder),
      claudeSessionId: json.claudeSessionId ?? null,
      memory: this.readMemory(folder),
      decisionCount: this.countDecisions(folder)
    }
  }

  private write(folder: string, mutate: (j: ProjectJson) => void): ProjectJson {
    const pPath = join(folder, PROJECT_FILE)
    const json = JSON.parse(readFileSync(pPath, 'utf8')) as ProjectJson
    mutate(json)
    writeFileSync(pPath, JSON.stringify(json, null, 2))
    return json
  }

  touch(folder: string): void {
    this.write(folder, (j) => {
      j.lastOpenedAt = new Date().toISOString()
    })
  }

  setSessionId(folder: string, sessionId: string | null): void {
    this.write(folder, (j) => {
      j.claudeSessionId = sessionId
    })
  }

  /**
   * Copy files into the project and record their hashes.
   *
   * A name that already exists is suffixed rather than overwritten: two
   * different files called `balance.csv` are a normal thing to receive, and
   * losing one of them silently would be the worst possible outcome.
   */
  addFiles(folder: string, paths: string[]): ProjectFile[] {
    const added: ProjectFile[] = []
    const json = JSON.parse(readFileSync(join(folder, PROJECT_FILE), 'utf8')) as ProjectJson
    const taken = new Set(json.files.map((f) => basename(f.relPath)))

    for (const src of paths) {
      if (!existsSync(src)) continue
      let name = basename(src)
      if (taken.has(name)) {
        const dot = name.lastIndexOf('.')
        const stem = dot > 0 ? name.slice(0, dot) : name
        const ext = dot > 0 ? name.slice(dot) : ''
        let i = 2
        while (taken.has(`${stem}-${i}${ext}`)) i++
        name = `${stem}-${i}${ext}`
      }
      taken.add(name)

      const relPath = `${SOURCES_DIR}/${name}`
      const dest = join(folder, SOURCES_DIR, name)
      copyFileSync(src, dest)

      added.push({
        relPath,
        name,
        bytes: statSync(dest).size,
        sha256: sha256File(dest),
        addedAt: new Date().toISOString(),
        role: guessRole(name),
        rows: name.toLowerCase().endsWith('.csv') ? countCsvRows(dest) : null
      })
    }

    this.write(folder, (j) => {
      j.files = [...j.files, ...added]
    })
    return this.read(folder).files
  }

  setRole(folder: string, relPath: string, role: DatasetRole | null): ProjectFile[] {
    this.write(folder, (j) => {
      const f = j.files.find((x) => x.relPath === relPath)
      if (f) f.role = role
    })
    return this.read(folder).files
  }

  readNotebook(folder: string): NotebookCell[] {
    const p = join(folder, NOTEBOOK_FILE)
    if (!existsSync(p)) return []
    try {
      const parsed = JSON.parse(readFileSync(p, 'utf8'))
      return Array.isArray(parsed) ? (parsed as NotebookCell[]) : []
    } catch {
      // A corrupt notebook must not make the project unopenable; the
      // reconciliation itself lives in runs/ and decisions.jsonl.
      return []
    }
  }

  saveNotebook(folder: string, cells: NotebookCell[]): void {
    writeFileSync(join(folder, NOTEBOOK_FILE), JSON.stringify(cells, null, 2))
  }

  readMemory(folder: string): string {
    const p = join(folder, MEMORY_FILE)
    return existsSync(p) ? readFileSync(p, 'utf8') : ''
  }

  /** Append a timestamped entry under "## Session log". */
  appendMemory(folder: string, entry: string): string {
    const p = join(folder, MEMORY_FILE)
    const stamp = new Date().toISOString().replace('T', ' ').slice(0, 16)
    const line = `- ${stamp} — ${entry.trim()}\n`
    let text = existsSync(p) ? readFileSync(p, 'utf8') : MEMORY_TEMPLATE('Reconciliation', stamp)
    if (text.includes('## Session log')) {
      text = text.replace(/## Session log\n/, `## Session log\n\n${line}`)
    } else {
      text = `${text.trimEnd()}\n\n## Session log\n\n${line}`
    }
    text = text.replace(/\n{3,}/g, '\n\n')
    writeFileSync(p, text)
    return text
  }

  countDecisions(folder: string): number {
    const p = join(folder, DECISIONS_FILE)
    if (!existsSync(p)) return 0
    return readFileSync(p, 'utf8')
      .split('\n')
      .filter((l) => l.trim().startsWith('{')).length
  }

  /** Run folders, newest first. */
  runs(folder: string): string[] {
    const dir = join(folder, RUNS_DIR)
    if (!existsSync(dir)) return []
    return readdirSync(dir)
      .filter((d) => statSync(join(dir, d)).isDirectory())
      .sort()
      .reverse()
  }

  /** The newest run's metrics, or null when nothing has been run. */
  latestMetrics(folder: string): ReconMetrics | null {
    for (const run of this.runs(folder)) {
      const p = join(folder, RUNS_DIR, run, 'metrics.json')
      if (existsSync(p)) {
        try {
          return JSON.parse(readFileSync(p, 'utf8')) as ReconMetrics
        } catch {
          continue
        }
      }
    }
    return null
  }

  /** The newest run's priced questions, ask-list first. */
  latestQuestions(folder: string): ReconQuestion[] {
    for (const run of this.runs(folder)) {
      const p = join(folder, RUNS_DIR, run, 'questions.json')
      if (existsSync(p)) {
        try {
          const parsed = JSON.parse(readFileSync(p, 'utf8')) as {
            ask?: ReconQuestion[]
            assume?: ReconQuestion[]
          }
          return [...(parsed.ask ?? []), ...(parsed.assume ?? [])]
        } catch {
          continue
        }
      }
    }
    return []
  }

  reports(folder: string): { name: string; relPath: string }[] {
    const out: { name: string; relPath: string }[] = []
    for (const dir of [REPORTS_DIR, '.']) {
      const abs = join(folder, dir)
      if (!existsSync(abs)) continue
      for (const f of readdirSync(abs)) {
        if (!/\.(md|markdown)$/i.test(f)) continue
        if (f === MEMORY_FILE) continue
        out.push({ name: f, relPath: dir === '.' ? f : `${dir}/${f}` })
      }
    }
    return out
  }

  readReport(folder: string, relPath: string): string {
    const abs = this.resolveInside(folder, relPath)
    return existsSync(abs) ? readFileSync(abs, 'utf8') : ''
  }

  /**
   * Resolve a project-relative path, refusing anything that escapes.
   *
   * The renderer supplies these paths, so a traversal like `../../secrets`
   * must not be able to read outside the project folder even though the
   * renderer is our own code.
   */
  resolveInside(folder: string, relPath: string): string {
    const clean = relPath.replace(/\\/g, '/')
    if (clean.split('/').some((part) => part === '..')) {
      throw new Error('that path leaves the project folder')
    }
    return join(folder, clean)
  }
}
