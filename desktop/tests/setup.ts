/**
 * Test setup.
 *
 * jsdom has no window.api, so renderer tests get a fully stubbed desktop API.
 * Node tests touch neither, so the guard keeps this file usable by both.
 */
import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

if (typeof window !== 'undefined') {
  const noop = (): (() => void) => () => undefined
  ;(window as unknown as { api: unknown }).api = {
    claude: {
      status: vi.fn().mockResolvedValue({ status: 'ready', version: '1.0.0', binPath: 'claude', source: 'system' }),
      install: vi.fn(),
      onStatus: vi.fn(noop)
    },
    project: {
      create: vi.fn(),
      open: vi.fn(),
      pickFolder: vi.fn(),
      recent: vi.fn().mockResolvedValue([]),
      addFiles: vi.fn().mockResolvedValue([]),
      setRole: vi.fn().mockResolvedValue([]),
      saveNotebook: vi.fn().mockResolvedValue(undefined),
      readMemory: vi.fn().mockResolvedValue(''),
      appendMemory: vi.fn().mockResolvedValue(''),
      metrics: vi.fn().mockResolvedValue(null),
      questions: vi.fn().mockResolvedValue([]),
      reports: vi.fn().mockResolvedValue([]),
      readReport: vi.fn().mockResolvedValue('')
    },
    chat: { send: vi.fn(), cancel: vi.fn(), onEvent: vi.fn(noop) }
  }

  // jsdom implements neither of these, and both are normal browser APIs the
  // components rely on. Stubbing them is the standard fix, not a workaround
  // for a defect.
  Element.prototype.scrollIntoView = vi.fn()

  // Recharts measures its container; jsdom reports zero, so charts never render.
  global.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  } as unknown as typeof ResizeObserver
}
