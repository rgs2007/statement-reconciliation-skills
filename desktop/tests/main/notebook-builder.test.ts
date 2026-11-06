/**
 * Notebook builders.
 *
 * These are pure functions over the engine's own output, which is what keeps
 * the display honest. The CSV reader gets the most attention: reconciliation
 * data is full of quoted comma-decimal amounts, and splitting on commas would
 * corrupt every figure shown to the user.
 */
import { beforeEach, describe, expect, it } from 'vitest'
import {
  breaksCell,
  gapCompositionCell,
  markdownCell,
  metricsCell,
  parseCsv,
  questionsCell,
  resetCellIds,
  statusCell
} from '../../src/main/services/notebook-builder'
import type { ReconMetrics, ReconQuestion } from '../../src/shared/types'

const metrics: ReconMetrics = {
  keys_total: 12,
  reconciled: 7,
  reconciled_pct: 58.3,
  sign_convention: 'closing = opening + movements',
  gap_gross: 1991939.95,
  gap_net: -1974330.85,
  gap_gross_at_parent: 1990344.19,
  movements_unattributed: 1,
  attribution_rate_pct: 97.3
}

beforeEach(() => resetCellIds())

describe('parseCsv', () => {
  it('keeps a quoted comma-decimal amount intact', () => {
    // The whole point: "1.234,56" is one field, not two.
    const { columns, rows } = parseCsv('account,amount\n1000-01,"1.234,56"\n')
    expect(columns).toEqual(['account', 'amount'])
    expect(rows).toEqual([['1000-01', '1.234,56']])
  })

  it('handles an escaped quote inside a field', () => {
    const { rows } = parseCsv('name\n"say ""hi"" now"\n')
    expect(rows).toEqual([['say "hi" now']])
  })

  it('handles CRLF without leaving stray carriage returns', () => {
    const { rows } = parseCsv('a,b\r\n1,2\r\n')
    expect(rows).toEqual([['1', '2']])
  })

  it('reads the last row when the file has no trailing newline', () => {
    const { rows } = parseCsv('a,b\n1,2')
    expect(rows).toEqual([['1', '2']])
  })

  it('skips blank lines rather than emitting empty rows', () => {
    const { rows } = parseCsv('a,b\n1,2\n\n3,4\n')
    expect(rows).toEqual([['1', '2'], ['3', '4']])
  })

  it('returns empty structures for empty input', () => {
    expect(parseCsv('')).toEqual({ columns: [], rows: [] })
  })
})

describe('metricsCell', () => {
  it('carries the metrics through unchanged', () => {
    const cell = metricsCell(metrics)
    expect(cell.kind).toBe('metrics')
    if (cell.kind === 'metrics') expect(cell.metrics.gap_gross).toBe(1991939.95)
  })

  it('gives every cell a distinct id', () => {
    const ids = new Set([metricsCell(metrics).id, metricsCell(metrics).id, metricsCell(metrics).id])
    expect(ids.size).toBe(3)
  })
})

describe('gapCompositionCell', () => {
  it('sums by category and orders largest first', () => {
    const cell = gapCompositionCell([
      { category: 'DECIMAL_SHIFT', gross: 1944943.11 },
      { category: 'DUPLICATE_POSTING', gross: 37394.41 },
      { category: 'DECIMAL_SHIFT', gross: 1000 }
    ])
    if (cell.kind !== 'chart') throw new Error('expected a chart cell')
    expect(cell.series[0].label).toBe('DECIMAL_SHIFT')
    expect(cell.series[0].value).toBe(1945943.11)
    expect(cell.series[1].label).toBe('DUPLICATE_POSTING')
  })

  it('uses absolute values, so offsetting breaks do not cancel to nothing', () => {
    // A chart of net figures can look empty while a real control failure
    // sits underneath it.
    const cell = gapCompositionCell([
      { category: 'SUBACCOUNT_MISATTRIBUTION', gross: 797.88 },
      { category: 'SUBACCOUNT_MISATTRIBUTION', gross: -797.88 }
    ])
    if (cell.kind !== 'chart') throw new Error('expected a chart cell')
    expect(cell.series[0].value).toBe(1595.76)
  })

  it('produces an empty series for no breaks', () => {
    const cell = gapCompositionCell([])
    if (cell.kind !== 'chart') throw new Error('expected a chart cell')
    expect(cell.series).toEqual([])
  })
})

describe('questionsCell', () => {
  const q = (over: Partial<ReconQuestion> = {}): ReconQuestion => ({
    id: 'scope',
    topic: 'SCOPE_MISMATCH',
    amount_at_stake: 8048.92,
    share_of_gap: 0.004,
    why_it_matters: 'one side only',
    options: ['exclude', 'keep'],
    default_if_unanswered: 'keep in scope',
    risk_if_assumed: 'wrong',
    must_state_explicitly: true,
    ...over
  })

  it('marks a question that must be answered', () => {
    const cell = questionsCell([q()])
    if (cell.kind !== 'markdown') throw new Error('expected markdown')
    expect(cell.body).toContain('must be answered')
    expect(cell.body).toContain('8,048.92')
  })

  it('says a safe default can be assumed', () => {
    const cell = questionsCell([q({ risk_if_assumed: 'incomplete' })])
    if (cell.kind !== 'markdown') throw new Error('expected markdown')
    expect(cell.body).toContain('can be assumed')
  })

  it('says so plainly when nothing is outstanding', () => {
    const cell = questionsCell([])
    if (cell.kind !== 'markdown') throw new Error('expected markdown')
    expect(cell.title).toBe('Open questions')
    expect(cell.body).toContain('Nothing outstanding')
  })

  it('counts the questions in the title', () => {
    expect(questionsCell([q(), q({ id: 'b' })]).title).toBe('Open questions (2)')
  })
})

describe('breaksCell', () => {
  const csv = 'key,gap,status\n1000-01,100.00,BREAK\n2000-01,-5000.00,BREAK\n3000-01,25.00,BREAK\n'

  it('orders by absolute gap, so the biggest problem is first', () => {
    const cell = breaksCell(csv)
    if (cell.kind !== 'table') throw new Error('expected a table cell')
    expect(cell.rows.map((r) => r[0])).toEqual(['2000-01', '1000-01', '3000-01'])
  })

  it('caps the rows shown so a huge ledger cannot freeze the pane', () => {
    const many = ['key,gap', ...Array.from({ length: 500 }, (_, i) => `k${i},${i}`)].join('\n')
    const cell = breaksCell(many, 25)
    if (cell.kind !== 'table') throw new Error('expected a table cell')
    expect(cell.rows).toHaveLength(25)
  })

  it('still renders when there is no gap column to sort on', () => {
    const cell = breaksCell('a,b\n1,2\n')
    if (cell.kind !== 'table') throw new Error('expected a table cell')
    expect(cell.rows).toEqual([['1', '2']])
  })
})

describe('statusCell and markdownCell', () => {
  it('keeps the step list in order', () => {
    const cell = statusCell([
      { name: 'load', state: 'done' },
      { name: 'equation', state: 'running' },
      { name: 'detect-duplicates', state: 'skipped', detail: 'not tested for' }
    ])
    if (cell.kind !== 'status') throw new Error('expected a status cell')
    expect(cell.steps.map((s) => s.name)).toEqual(['load', 'equation', 'detect-duplicates'])
  })

  it('builds a markdown cell with its title and body', () => {
    const cell = markdownCell('Scope', 'January 2026')
    expect(cell).toMatchObject({ kind: 'markdown', title: 'Scope', body: 'January 2026' })
  })
})
