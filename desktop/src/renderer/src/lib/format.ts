/**
 * Formatting helpers.
 *
 * Money is always shown with two decimals and grouped thousands, and a
 * negative is shown with a minus rather than parentheses or red alone —
 * colour is not available to every reader, and an accountant reading a gap
 * needs the sign unambiguously.
 */
export function money(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function percent(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return `${n.toFixed(digits)}%`
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

/** Short relative time, for file and run timestamps. */
export function ago(iso: string, now: Date = new Date()): string {
  const diff = now.getTime() - new Date(iso).getTime()
  if (Number.isNaN(diff)) return ''
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return days < 30 ? `${days}d ago` : new Date(iso).toLocaleDateString()
}

/**
 * How reconciled a run is, as a traffic light.
 *
 * Deliberately conservative: anything under 95% is "attention", because a
 * reconciliation that is 90% done is not nearly finished — the remaining
 * accounts are usually where the real problem is.
 */
export function health(pct: number | null | undefined): 'good' | 'warn' | 'bad' {
  if (pct === null || pct === undefined) return 'warn'
  if (pct >= 99.5) return 'good'
  if (pct >= 95) return 'warn'
  return 'bad'
}
