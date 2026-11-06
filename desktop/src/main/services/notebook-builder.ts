/**
 * Turning engine output into notebook cells.
 *
 * The notebook is the left pane: the visible record of what the
 * reconciliation found. These builders are pure functions over the engine's
 * own JSON and CSV, which keeps the display honest — a cell can only show a
 * figure the engine actually produced, and the same run always renders the
 * same cells.
 */
import type { NotebookCell, ReconMetrics, ReconQuestion, RunStep } from '../../shared/types'

let counter = 0
/** Ids only need to be unique within a project's notebook. */
export function cellId(prefix: string): string {
  counter += 1
  return `${prefix}-${Date.now().toString(36)}-${counter.toString(36)}`
}

/** Reset between tests so ids are predictable. */
export function resetCellIds(): void {
  counter = 0
}

export function metricsCell(metrics: ReconMetrics, title = 'Reconciliation result'): NotebookCell {
  return { id: cellId('metrics'), kind: 'metrics', title, metrics, createdAt: new Date().toISOString() }
}

/**
 * Gap composition, for the chart cell.
 *
 * Shows gross per category rather than net: net hides offsetting activity,
 * and a chart of net figures can show almost nothing while a real control
 * failure sits underneath it.
 */
export function gapCompositionCell(
  breaks: { category: string; gross: number }[],
  title = 'Where the gap is'
): NotebookCell {
  const byCategory = new Map<string, number>()
  for (const b of breaks) {
    byCategory.set(b.category, (byCategory.get(b.category) ?? 0) + Math.abs(b.gross))
  }
  const series = [...byCategory.entries()]
    .map(([label, value]) => ({ label, value: Math.round(value * 100) / 100 }))
    .sort((a, b) => b.value - a.value)
  return { id: cellId('chart'), kind: 'chart', title, series, createdAt: new Date().toISOString() }
}

export function questionsCell(questions: ReconQuestion[]): NotebookCell {
  if (!questions.length) {
    return {
      id: cellId('md'),
      kind: 'markdown',
      title: 'Open questions',
      body: 'Nothing outstanding — every difference has a determined cause.',
      createdAt: new Date().toISOString()
    }
  }
  const lines = questions.map((q) => {
    const risk =
      q.risk_if_assumed === 'wrong'
        ? '**must be answered** — assuming a default here could make the figure wrong'
        : 'can be assumed — the default reports it as unexplained'
    return [
      `### ${q.topic} — ${q.amount_at_stake.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })}`,
      '',
      q.why_it_matters,
      '',
      `- Options: ${q.options.join(' · ')}`,
      `- If unanswered: ${q.default_if_unanswered}`,
      `- Risk: ${risk}`,
      ''
    ].join('\n')
  })
  return {
    id: cellId('md'),
    kind: 'markdown',
    title: `Open questions (${questions.length})`,
    body: lines.join('\n'),
    createdAt: new Date().toISOString()
  }
}

/** The breaks table, largest absolute gap first. */
export function breaksCell(csv: string, limit = 50, title = 'Accounts that do not tie'): NotebookCell {
  const { columns, rows } = parseCsv(csv)
  const gapIdx = columns.findIndex((c) => c.toLowerCase() === 'gap')
  const sorted =
    gapIdx >= 0
      ? [...rows].sort(
          (a, b) => Math.abs(Number(b[gapIdx] ?? 0)) - Math.abs(Number(a[gapIdx] ?? 0))
        )
      : rows
  return {
    id: cellId('table'),
    kind: 'table',
    title,
    columns,
    rows: sorted.slice(0, limit),
    createdAt: new Date().toISOString()
  }
}

export function statusCell(steps: RunStep[], title = 'Run progress'): NotebookCell {
  return { id: cellId('status'), kind: 'status', title, steps, createdAt: new Date().toISOString() }
}

export function markdownCell(title: string, body: string): NotebookCell {
  return { id: cellId('md'), kind: 'markdown', title, body, createdAt: new Date().toISOString() }
}

/**
 * A small CSV reader that handles quoted fields and embedded separators.
 *
 * Reconciliation data routinely contains quoted comma-decimal amounts like
 * `"1.234,56"`, so splitting on commas would corrupt every figure. Worth the
 * few lines rather than a dependency.
 */
export function parseCsv(text: string): { columns: string[]; rows: string[][] } {
  const rows: string[][] = []
  let field = ''
  let row: string[] = []
  let inQuotes = false

  const pushField = (): void => {
    row.push(field)
    field = ''
  }
  const pushRow = (): void => {
    if (row.length > 1 || row[0] !== '') rows.push(row)
    row = []
  }

  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (inQuotes) {
      if (c === '"') {
        // A doubled quote inside a quoted field is one literal quote.
        if (text[i + 1] === '"') {
          field += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        field += c
      }
      continue
    }
    if (c === '"') {
      inQuotes = true
    } else if (c === ',') {
      pushField()
    } else if (c === '\n') {
      pushField()
      pushRow()
    } else if (c !== '\r') {
      field += c
    }
  }
  if (field !== '' || row.length) {
    pushField()
    pushRow()
  }

  const [header = [], ...body] = rows
  return { columns: header, rows: body }
}
