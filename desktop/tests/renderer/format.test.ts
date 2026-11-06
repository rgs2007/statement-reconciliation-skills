import { describe, expect, it } from 'vitest'
import { ago, bytes, health, money, percent } from '../../src/renderer/src/lib/format'

describe('money', () => {
  it('always shows two decimals with grouped thousands', () => {
    expect(money(1991939.95)).toBe('1,991,939.95')
    expect(money(0)).toBe('0.00')
    expect(money(1000)).toBe('1,000.00')
  })

  it('keeps the sign visible rather than relying on colour', () => {
    // Colour is not available to every reader; the sign of a gap is not optional.
    expect(money(-1974330.85)).toBe('-1,974,330.85')
  })

  it.each([null, undefined, NaN])('shows an em dash for %j', (v) => {
    expect(money(v as number)).toBe('—')
  })
})

describe('percent', () => {
  it('formats to one decimal by default', () => {
    expect(percent(58.333)).toBe('58.3%')
    expect(percent(97.3, 2)).toBe('97.30%')
  })
  it('handles missing values', () => {
    expect(percent(null)).toBe('—')
  })
})

describe('bytes', () => {
  it.each([
    [512, '512 B'],
    [2048, '2.0 KB'],
    [14 * 1024 * 1024, '14.0 MB']
  ])('formats %i as %s', (n, expected) => {
    expect(bytes(n)).toBe(expected)
  })
})

describe('ago', () => {
  const now = new Date('2026-11-06T12:00:00Z')
  it.each([
    ['2026-11-06T11:59:30Z', 'just now'],
    ['2026-11-06T11:30:00Z', '30m ago'],
    ['2026-11-06T09:00:00Z', '3h ago'],
    ['2026-11-04T12:00:00Z', '2d ago']
  ])('renders %s as %s', (iso, expected) => {
    expect(ago(iso, now)).toBe(expected)
  })

  it('returns empty for an unparseable date instead of NaN', () => {
    expect(ago('not a date', now)).toBe('')
  })
})

describe('health', () => {
  it('is deliberately strict: 90% reconciled is not nearly done', () => {
    // The remaining accounts are usually where the real problem is.
    expect(health(100)).toBe('good')
    expect(health(99.6)).toBe('good')
    expect(health(97)).toBe('warn')
    expect(health(90)).toBe('bad')
    expect(health(58.3)).toBe('bad')
  })
  it('treats unknown as needing attention', () => {
    expect(health(null)).toBe('warn')
  })
})
