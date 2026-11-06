/**
 * The project store.
 *
 * This is what makes "continue where you left off" true, so the tests focus
 * on the properties that would silently lose a user's work: files being
 * overwritten, a project becoming unopenable, a session id not surviving, and
 * a path escaping the project folder.
 */
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  DECISIONS_FILE,
  MEMORY_FILE,
  NOTEBOOK_FILE,
  PROJECT_FILE,
  ProjectStore,
  countCsvRows,
  guessRole,
  slugify
} from '../../src/main/services/project-store'
import type { NotebookCell } from '../../src/shared/types'

let root: string
let store: ProjectStore

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'fsr-test-'))
  store = new ProjectStore()
})
afterEach(() => rmSync(root, { recursive: true, force: true }))

function sampleCsv(path: string, rows = 3): void {
  const lines = ['account,balance']
  for (let i = 1; i <= rows; i++) lines.push(`100${i},"1.2${i}0,50"`)
  writeFileSync(path, `${lines.join('\n')}\n`)
}

describe('slugify', () => {
  it.each([
    ['Acme Payables — January', 'acme-payables-january'],
    ['Conciliação 2026', 'conciliacao-2026'],
    ['   ', 'reconciliation'],
    ['///', 'reconciliation']
  ])('turns %j into a safe folder name', (input, expected) => {
    expect(slugify(input)).toBe(expected)
  })

  it('keeps the name short enough for a Windows path', () => {
    expect(slugify('x'.repeat(300)).length).toBeLessThanOrEqual(48)
  })
})

describe('guessRole', () => {
  it.each([
    ['initial_balance_table_raw.csv', 'opening'],
    ['final_balance_table_raw.csv', 'closing'],
    ['movement_table_raw.csv', 'movements'],
    ['saldo_inicial.csv', 'opening'],
    ['saldo_final.xlsx', 'closing'],
    ['lancamentos.csv', 'movements'],
    ['accounts_list.csv', 'accounts'],
    ['trial_balance.csv', 'opening']
  ])('reads %s as %s', (name, role) => {
    expect(guessRole(name)).toBe(role)
  })

  it('does not guess when the name says nothing', () => {
    expect(guessRole('export-2026-01-14.csv')).toBeNull()
  })

  it('prefers the specific word over the generic one', () => {
    // "initial_balance" contains "balance"; opening must win over the
    // generic balance rule or every opening file is mislabelled.
    expect(guessRole('initial_balance.csv')).toBe('opening')
    expect(guessRole('final_balance.csv')).toBe('closing')
  })
})

describe('countCsvRows', () => {
  it('counts data rows, not the header', () => {
    const p = join(root, 'a.csv')
    sampleCsv(p, 5)
    expect(countCsvRows(p)).toBe(5)
  })

  it('reports zero for a header-only file rather than -1', () => {
    const p = join(root, 'empty.csv')
    writeFileSync(p, 'a,b,c\n')
    expect(countCsvRows(p)).toBe(0)
  })

  it('returns null for a file it cannot read', () => {
    expect(countCsvRows(join(root, 'nope.csv'))).toBeNull()
  })
})

describe('create', () => {
  it('lays out everything a resumable project needs', () => {
    const st = store.create(root, 'Acme Payables')
    for (const f of [PROJECT_FILE, MEMORY_FILE, NOTEBOOK_FILE, DECISIONS_FILE]) {
      expect(existsSync(join(st.summary.folder, f))).toBe(true)
    }
    for (const d of ['sources', 'runs', 'reports', join('.claude', 'skills')]) {
      expect(existsSync(join(st.summary.folder, d))).toBe(true)
    }
  })

  it('never reuses a folder, so a second project cannot merge into the first', () => {
    const a = store.create(root, 'Same Name')
    const b = store.create(root, 'Same Name')
    expect(b.summary.folder).not.toBe(a.summary.folder)
    expect(existsSync(a.summary.folder)).toBe(true)
  })

  it('seeds MEMORY.md with the sections the AI reads on resume', () => {
    const st = store.create(root, 'Acme')
    const memory = readFileSync(join(st.summary.folder, MEMORY_FILE), 'utf8')
    expect(memory).toContain('# MEMORY — Acme')
    for (const section of ['## Scope', '## Decisions taken', '## Open questions', '## Session log']) {
      expect(memory).toContain(section)
    }
  })
})

describe('read', () => {
  it('refuses a folder that is not a project, with a usable message', () => {
    expect(() => store.read(root)).toThrow(/not a reconciliation project/)
  })

  it('re-creates folders a user deleted by hand instead of failing to open', () => {
    const st = store.create(root, 'Acme')
    rmSync(join(st.summary.folder, 'runs'), { recursive: true, force: true })
    expect(() => store.read(st.summary.folder)).not.toThrow()
    expect(existsSync(join(st.summary.folder, 'runs'))).toBe(true)
  })

  it('survives a corrupt notebook, because the figures live elsewhere', () => {
    const st = store.create(root, 'Acme')
    writeFileSync(join(st.summary.folder, NOTEBOOK_FILE), '{{{ not json')
    expect(store.read(st.summary.folder).notebook).toEqual([])
  })
})

describe('addFiles', () => {
  it('copies files in and records a hash for each', () => {
    const st = store.create(root, 'Acme')
    const src = join(root, 'initial_balance.csv')
    sampleCsv(src)

    const files = store.addFiles(st.summary.folder, [src])
    expect(files).toHaveLength(1)
    expect(files[0].relPath).toBe('sources/initial_balance.csv')
    expect(files[0].sha256).toMatch(/^[0-9a-f]{64}$/)
    expect(files[0].role).toBe('opening')
    expect(files[0].rows).toBe(3)
    expect(existsSync(join(st.summary.folder, 'sources', 'initial_balance.csv'))).toBe(true)
  })

  it('leaves the original untouched, so a re-run uses the copy', () => {
    const st = store.create(root, 'Acme')
    const src = join(root, 'a.csv')
    sampleCsv(src)
    const before = readFileSync(src, 'utf8')
    store.addFiles(st.summary.folder, [src])
    expect(readFileSync(src, 'utf8')).toBe(before)
  })

  it('suffixes a duplicate name rather than silently replacing a file', () => {
    // Receiving two different files called balance.csv is normal; losing one
    // would be the worst possible outcome.
    const st = store.create(root, 'Acme')
    const one = join(root, 'one', 'balance.csv')
    const two = join(root, 'two', 'balance.csv')
    mkdirSync(join(root, 'one'))
    mkdirSync(join(root, 'two'))
    sampleCsv(one, 2)
    sampleCsv(two, 7)

    store.addFiles(st.summary.folder, [one])
    const files = store.addFiles(st.summary.folder, [two])

    expect(files.map((f) => f.name).sort()).toEqual(['balance-2.csv', 'balance.csv'])
    expect(files.find((f) => f.name === 'balance.csv')?.rows).toBe(2)
    expect(files.find((f) => f.name === 'balance-2.csv')?.rows).toBe(7)
  })

  it('skips a path that no longer exists instead of failing the batch', () => {
    const st = store.create(root, 'Acme')
    const good = join(root, 'good.csv')
    sampleCsv(good)
    const files = store.addFiles(st.summary.folder, [join(root, 'ghost.csv'), good])
    expect(files).toHaveLength(1)
  })

  it('persists across a reopen', () => {
    const st = store.create(root, 'Acme')
    const src = join(root, 'movement_table.csv')
    sampleCsv(src)
    store.addFiles(st.summary.folder, [src])
    expect(store.read(st.summary.folder).files).toHaveLength(1)
  })
})

describe('setRole', () => {
  it('overrides the guess and keeps it', () => {
    const st = store.create(root, 'Acme')
    const src = join(root, 'export.csv')
    sampleCsv(src)
    store.addFiles(st.summary.folder, [src])

    store.setRole(st.summary.folder, 'sources/export.csv', 'movements')
    expect(store.read(st.summary.folder).files[0].role).toBe('movements')

    store.setRole(st.summary.folder, 'sources/export.csv', null)
    expect(store.read(st.summary.folder).files[0].role).toBeNull()
  })
})

describe('session id', () => {
  it('survives a reopen, so the conversation resumes', () => {
    const st = store.create(root, 'Acme')
    expect(st.claudeSessionId).toBeNull()
    store.setSessionId(st.summary.folder, 'sess-123')
    expect(store.read(st.summary.folder).claudeSessionId).toBe('sess-123')
  })
})

describe('notebook', () => {
  it('round-trips cells through disk', () => {
    const st = store.create(root, 'Acme')
    const cells: NotebookCell[] = [
      { id: 'c1', kind: 'markdown', title: 'Scope', body: 'Jan 2026', createdAt: 'now' },
      { id: 'c2', kind: 'table', title: 'Breaks', columns: ['key'], rows: [['1000-01']], createdAt: 'now' }
    ]
    store.saveNotebook(st.summary.folder, cells)
    expect(store.read(st.summary.folder).notebook).toEqual(cells)
  })
})

describe('memory', () => {
  it('appends newest-first under the session log', () => {
    const st = store.create(root, 'Acme')
    store.appendMemory(st.summary.folder, 'first entry')
    const text = store.appendMemory(st.summary.folder, 'second entry')
    expect(text).toContain('first entry')
    expect(text).toContain('second entry')
    expect(text.indexOf('second entry')).toBeLessThan(text.indexOf('first entry'))
  })

  it('adds the section when a user has removed it', () => {
    const st = store.create(root, 'Acme')
    writeFileSync(join(st.summary.folder, MEMORY_FILE), '# MEMORY\n\nNotes.\n')
    const text = store.appendMemory(st.summary.folder, 'an entry')
    expect(text).toContain('## Session log')
    expect(text).toContain('an entry')
  })

  it('does not accumulate blank lines over many appends', () => {
    const st = store.create(root, 'Acme')
    for (let i = 0; i < 6; i++) store.appendMemory(st.summary.folder, `entry ${i}`)
    expect(store.readMemory(st.summary.folder)).not.toMatch(/\n{3,}/)
  })
})

describe('decisions', () => {
  it('counts only JSON entries, ignoring blanks and comments', () => {
    const st = store.create(root, 'Acme')
    writeFileSync(
      join(st.summary.folder, DECISIONS_FILE),
      ['{"id":"d-1"}', '', '// a note', '{"id":"d-2"}', '   '].join('\n')
    )
    expect(store.countDecisions(st.summary.folder)).toBe(2)
  })

  it('reports zero on a new project', () => {
    const st = store.create(root, 'Acme')
    expect(store.read(st.summary.folder).decisionCount).toBe(0)
  })
})

describe('runs, metrics and questions', () => {
  function writeRun(folder: string, run: string, files: Record<string, string>): void {
    const dir = join(folder, 'runs', run)
    mkdirSync(dir, { recursive: true })
    for (const [name, body] of Object.entries(files)) writeFileSync(join(dir, name), body)
  }

  it('reads the newest run, not the first', () => {
    const st = store.create(root, 'Acme')
    writeRun(st.summary.folder, 'run-001', {
      'metrics.json': JSON.stringify({ keys_total: 10, reconciled: 5, reconciled_pct: 50, sign_convention: 'x', gap_gross: 100, gap_net: 100 })
    })
    writeRun(st.summary.folder, 'run-002', {
      'metrics.json': JSON.stringify({ keys_total: 10, reconciled: 9, reconciled_pct: 90, sign_convention: 'x', gap_gross: 10, gap_net: 10 })
    })
    expect(store.latestMetrics(st.summary.folder)?.reconciled).toBe(9)
  })

  it('skips a corrupt newest run and falls back to a readable one', () => {
    const st = store.create(root, 'Acme')
    writeRun(st.summary.folder, 'run-001', {
      'metrics.json': JSON.stringify({ keys_total: 1, reconciled: 1, reconciled_pct: 100, sign_convention: 'x', gap_gross: 0, gap_net: 0 })
    })
    writeRun(st.summary.folder, 'run-002', { 'metrics.json': '{ broken' })
    expect(store.latestMetrics(st.summary.folder)?.reconciled).toBe(1)
  })

  it('returns null when nothing has been run yet', () => {
    const st = store.create(root, 'Acme')
    expect(store.latestMetrics(st.summary.folder)).toBeNull()
  })

  it('returns ask questions before assumed ones', () => {
    const st = store.create(root, 'Acme')
    writeRun(st.summary.folder, 'run-001', {
      'questions.json': JSON.stringify({
        ask: [{ id: 'a', topic: 'SCOPE_MISMATCH', amount_at_stake: 100, share_of_gap: 0.5, why_it_matters: 'w', options: ['x', 'y'], default_if_unanswered: 'd', risk_if_assumed: 'wrong', must_state_explicitly: true }],
        assume: [{ id: 'b', topic: 'UNATTRIBUTED', amount_at_stake: 10, share_of_gap: 0.05, why_it_matters: 'w', options: ['x', 'y'], default_if_unanswered: 'd', risk_if_assumed: 'incomplete', must_state_explicitly: false }]
      })
    })
    const qs = store.latestQuestions(st.summary.folder)
    expect(qs.map((q) => q.id)).toEqual(['a', 'b'])
  })
})

describe('reports', () => {
  it('lists markdown reports but never MEMORY.md', () => {
    const st = store.create(root, 'Acme')
    writeFileSync(join(st.summary.folder, 'reports', 'reconciliation.md'), '# Report')
    writeFileSync(join(st.summary.folder, 'report.md'), '# Root level')

    const names = store.reports(st.summary.folder).map((r) => r.name)
    expect(names).toContain('reconciliation.md')
    expect(names).toContain('report.md')
    // MEMORY.md is the AI's working notes, not a deliverable.
    expect(names).not.toContain(MEMORY_FILE)
  })

  it('reads a report by its relative path', () => {
    const st = store.create(root, 'Acme')
    writeFileSync(join(st.summary.folder, 'reports', 'r.md'), '# Hello')
    expect(store.readReport(st.summary.folder, 'reports/r.md')).toBe('# Hello')
  })

  it('returns empty for a report that is not there', () => {
    const st = store.create(root, 'Acme')
    expect(store.readReport(st.summary.folder, 'reports/ghost.md')).toBe('')
  })
})

describe('resolveInside', () => {
  it.each(['../../etc/passwd', 'reports/../../escape.md', '..\\..\\windows'])(
    'refuses %j',
    (bad) => {
      // The renderer supplies these paths, so traversal must be blocked even
      // though the renderer is our own code.
      expect(() => store.resolveInside('/projects/acme', bad)).toThrow(/leaves the project/)
    }
  )

  it('allows an ordinary nested path', () => {
    expect(store.resolveInside('/projects/acme', 'reports/r.md')).toContain('reports')
  })
})
