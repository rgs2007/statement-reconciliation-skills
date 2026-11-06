/**
 * The notebook — the left pane, and the project's visible working record.
 *
 * It is a cell list rather than a fixed dashboard because a reconciliation is
 * a narrative: profile, run, break down, ask, re-run, report. A dashboard
 * shows the latest state and loses the sequence; cells keep the sequence,
 * which is what makes a reconciliation reviewable afterwards.
 */
import { useMemo, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'
import type { NotebookCell, ReconMetrics } from '@shared/types'
import { health, money, percent } from '../lib/format'
import { BRAND } from '../theme/brand'

export function MetricsGrid({ metrics }: { metrics: ReconMetrics }): JSX.Element {
  const tone = health(metrics.reconciled_pct)
  const toneClass =
    tone === 'good' ? 'text-emerald-400' : tone === 'warn' ? 'text-amber-400' : 'text-red-400'

  const tiles: { label: string; value: string; className?: string; hint?: string }[] = [
    {
      label: 'Reconciled',
      value: `${metrics.reconciled} / ${metrics.keys_total}`,
      className: toneClass,
      hint: percent(metrics.reconciled_pct)
    },
    { label: 'Gross gap', value: money(metrics.gap_gross), hint: 'misposted activity' },
    { label: 'Net gap', value: money(metrics.gap_net), hint: 'unexplained value' },
    {
      label: 'At parent level',
      value: money(metrics.gap_gross_at_parent),
      hint: 'the rest is misposting'
    },
    { label: 'Attribution', value: percent(metrics.attribution_rate_pct, 2) },
    {
      label: 'Unattributed',
      value: String(metrics.movements_unattributed ?? '—'),
      hint: 'need a decision'
    }
  ]

  return (
    <div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-md border border-ink-800 bg-ink-950/60 p-3">
            <div className="label">{t.label}</div>
            <div className={`mt-1 font-mono text-lg ${t.className ?? 'text-ink-100'}`}>
              {t.value}
            </div>
            {t.hint ? <div className="mt-0.5 text-[11px] text-ink-500">{t.hint}</div> : null}
          </div>
        ))}
      </div>

      <p className="mt-3 text-xs text-ink-400">
        Equation: <span className="font-mono text-ink-200">{metrics.sign_convention}</span>
        {metrics.materiality !== undefined ? (
          <>
            {' · '}materiality <span className="font-mono">{metrics.materiality}</span>
          </>
        ) : null}
      </p>

      {metrics.caveats?.length ? (
        <ul className="mt-3 space-y-1 rounded-md border border-amber-900/60 bg-amber-950/30 p-3 text-xs text-amber-200">
          {metrics.caveats.map((c) => (
            <li key={c}>• {c}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

function StatusList({ steps }: { steps: NonNullable<Extract<NotebookCell, { kind: 'status' }>['steps']> }): JSX.Element {
  const dot: Record<string, string> = {
    pending: 'bg-ink-600',
    running: 'bg-flow-400 animate-pulse',
    done: 'bg-emerald-400',
    failed: 'bg-red-400',
    skipped: 'bg-amber-400'
  }
  return (
    <ol className="space-y-1.5">
      {steps.map((s) => (
        <li key={s.name} className="flex items-center gap-2.5 text-sm">
          <span className={`h-2 w-2 shrink-0 rounded-full ${dot[s.state] ?? 'bg-ink-600'}`} />
          <span className="font-mono text-ink-200">{s.name}</span>
          {s.detail ? <span className="truncate text-xs text-ink-500">{s.detail}</span> : null}
          {s.state === 'skipped' ? (
            <span className="ml-auto shrink-0 text-[11px] text-amber-400">not tested for</span>
          ) : null}
        </li>
      ))}
    </ol>
  )
}

function DataTable({
  columns,
  rows
}: {
  columns: string[]
  rows: string[][]
}): JSX.Element {
  const numericCols = useMemo(() => {
    const set = new Set<number>()
    columns.forEach((_, i) => {
      const vals = rows.slice(0, 20).map((r) => r[i])
      if (vals.length && vals.every((v) => v === '' || !Number.isNaN(Number(v)))) set.add(i)
    })
    return set
  }, [columns, rows])

  if (!columns.length) {
    return <p className="text-sm text-ink-500">No columns to show.</p>
  }

  return (
    <div className="max-h-80 overflow-auto rounded-md border border-ink-800">
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 bg-ink-900">
          <tr>
            {columns.map((c) => (
              <th
                key={c}
                className="border-b border-ink-800 px-2.5 py-2 text-left font-semibold text-ink-300"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="odd:bg-ink-950/40">
              {columns.map((_, j) => (
                <td
                  key={j}
                  className={`border-b border-ink-900 px-2.5 py-1.5 ${
                    numericCols.has(j) ? 'text-right font-mono' : ''
                  } text-ink-300`}
                >
                  {r[j] ?? ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Cell({
  cell,
  onRemove
}: {
  cell: NotebookCell
  onRemove?: (id: string) => void
}): JSX.Element {
  const [open, setOpen] = useState(true)

  return (
    <section className="card p-4" data-testid={`cell-${cell.kind}`}>
      <header className="mb-3 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="text-ink-500 transition-colors hover:text-ink-200"
          aria-label={open ? 'Collapse' : 'Expand'}
          aria-expanded={open}
        >
          {open ? '▾' : '▸'}
        </button>
        <h3 className="text-sm font-semibold text-ink-100">{cell.title}</h3>
        <span className="ml-auto text-[11px] uppercase tracking-wider text-ink-600">
          {cell.kind}
        </span>
        {onRemove ? (
          <button
            type="button"
            onClick={() => onRemove(cell.id)}
            className="text-ink-600 transition-colors hover:text-red-400"
            aria-label={`Remove ${cell.title}`}
          >
            ✕
          </button>
        ) : null}
      </header>

      {open ? (
        <div>
          {cell.kind === 'markdown' ? (
            <div className="prose-sm max-w-none text-sm leading-relaxed text-ink-300 [&_code]:rounded [&_code]:bg-ink-950 [&_code]:px-1 [&_h2]:mb-1 [&_h2]:mt-3 [&_h2]:font-semibold [&_h2]:text-ink-100 [&_h3]:mb-1 [&_h3]:mt-3 [&_h3]:font-semibold [&_h3]:text-ink-100 [&_strong]:text-ink-100 [&_table]:w-full [&_td]:border-b [&_td]:border-ink-800 [&_td]:py-1 [&_th]:py-1 [&_th]:text-left">
              <Markdown remarkPlugins={[remarkGfm]}>{cell.body}</Markdown>
            </div>
          ) : null}

          {cell.kind === 'metrics' ? <MetricsGrid metrics={cell.metrics} /> : null}

          {cell.kind === 'table' ? <DataTable columns={cell.columns} rows={cell.rows} /> : null}

          {cell.kind === 'status' ? <StatusList steps={cell.steps} /> : null}

          {cell.kind === 'chart' ? (
            cell.series.length ? (
              <div className="h-60">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={cell.series} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#373d4a" horizontal={false} />
                    <XAxis type="number" tick={{ fill: '#818da2', fontSize: 11 }} />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={190}
                      tick={{ fill: '#aeb6c4', fontSize: 11 }}
                    />
                    <Tooltip
                      formatter={(v: number) => money(v)}
                      contentStyle={{
                        background: BRAND.colors.surfaceRaised,
                        border: `1px solid ${BRAND.colors.border}`,
                        borderRadius: 6,
                        fontSize: 12
                      }}
                    />
                    <Bar dataKey="value" fill={BRAND.colors.primary} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-ink-500">Nothing to chart yet.</p>
            )
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

export function NotebookPane({
  cells,
  onRemove
}: {
  cells: NotebookCell[]
  onRemove?: (id: string) => void
}): JSX.Element {
  if (!cells.length) {
    return (
      <div className="flex h-full items-center justify-center p-10">
        <div className="max-w-md text-center">
          <h2 className="text-base font-semibold text-ink-200">The notebook is empty</h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-500">
            Add your statement files, then ask on the right why they do not tie out. Findings,
            tables, charts and reports appear here as the reconciliation progresses, and they
            are saved with the project.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 p-5" data-testid="notebook">
      {cells.map((c) => (
        <Cell key={c.id} cell={c} onRemove={onRemove} />
      ))}
    </div>
  )
}
