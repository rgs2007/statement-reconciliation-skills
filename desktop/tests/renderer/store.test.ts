/**
 * The app store.
 *
 * The streaming behaviour is what these protect: text arrives in many small
 * events and has to land in ONE assistant bubble, not one bubble per token.
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { useApp } from '../../src/renderer/src/store/useApp'
import type { ReconMetrics } from '../../src/shared/types'

beforeEach(() => useApp.getState().reset())

const metrics: ReconMetrics = {
  keys_total: 12, reconciled: 7, reconciled_pct: 58.3,
  sign_convention: 'closing = opening + movements', gap_gross: 100, gap_net: -100
}

describe('streaming text', () => {
  it('accumulates into one bubble instead of one per chunk', () => {
    const s = useApp.getState()
    s.appendToPending('The ')
    s.appendToPending('gap is ')
    s.appendToPending('1,991,939.95')
    const msgs = useApp.getState().messages
    expect(msgs).toHaveLength(1)
    expect(msgs[0].text).toBe('The gap is 1,991,939.95')
    expect(msgs[0].pending).toBe(true)
  })

  it('starts a new bubble after the previous turn finished', () => {
    const s = useApp.getState()
    s.appendToPending('first')
    s.finishPending()
    useApp.getState().appendToPending('second')
    const msgs = useApp.getState().messages
    expect(msgs).toHaveLength(2)
    expect(msgs.map((m) => m.text)).toEqual(['first', 'second'])
  })

  it('does not append onto a user message', () => {
    const s = useApp.getState()
    s.addMessage({ id: 'u1', role: 'user', text: 'why?', at: 'now' })
    useApp.getState().appendToPending('because')
    const msgs = useApp.getState().messages
    expect(msgs).toHaveLength(2)
    expect(msgs[0].text).toBe('why?')
  })

  it('clears busy when the turn finishes', () => {
    useApp.getState().setBusy(true)
    useApp.getState().appendToPending('x')
    useApp.getState().finishPending()
    expect(useApp.getState().busy).toBe(false)
  })

  it('clears busy even when no turn was open', () => {
    useApp.getState().setBusy(true)
    useApp.getState().finishPending()
    expect(useApp.getState().busy).toBe(false)
  })
})

describe('tool activity', () => {
  it('attaches to the open turn so the work is visibly computed', () => {
    const s = useApp.getState()
    s.appendToPending('Running the engine')
    useApp.getState().addToolActivity('Bash', 'python reconcile.py')
    useApp.getState().addToolActivity('Read', 'metrics.json')
    const msg = useApp.getState().messages[0]
    expect(msg.tools?.map((t) => t.name)).toEqual(['Bash', 'Read'])
    expect(msg.text).toBe('Running the engine')
  })

  it('opens a turn when a tool runs before any text', () => {
    useApp.getState().addToolActivity('Bash', 'ls')
    const msgs = useApp.getState().messages
    expect(msgs).toHaveLength(1)
    expect(msgs[0].tools).toHaveLength(1)
    expect(msgs[0].text).toBe('')
  })
})

describe('notebook', () => {
  it('adds and removes cells', () => {
    const s = useApp.getState()
    s.addCell({ id: 'c1', kind: 'markdown', title: 'A', body: 'x', createdAt: 'now' })
    s.addCell({ id: 'c2', kind: 'metrics', title: 'B', metrics, createdAt: 'now' })
    expect(useApp.getState().notebook).toHaveLength(2)
    useApp.getState().removeCell('c1')
    expect(useApp.getState().notebook.map((c) => c.id)).toEqual(['c2'])
  })
})

describe('project', () => {
  it('loads the saved notebook and clears the previous conversation', () => {
    const s = useApp.getState()
    s.appendToPending('stale turn from the last project')
    s.setProject({
      summary: { id: 'p', name: 'Acme', folder: '/p', createdAt: 'now', lastOpenedAt: 'now' },
      files: [],
      notebook: [{ id: 'c1', kind: 'markdown', title: 'Saved', body: 'x', createdAt: 'now' }],
      claudeSessionId: 'sess-1',
      memory: '# MEMORY',
      decisionCount: 3
    })
    const st = useApp.getState()
    expect(st.notebook).toHaveLength(1)
    expect(st.messages).toEqual([])
    expect(st.project?.claudeSessionId).toBe('sess-1')
  })

  it('replaces the file list without disturbing the rest of the project', () => {
    const s = useApp.getState()
    s.setProject({
      summary: { id: 'p', name: 'Acme', folder: '/p', createdAt: 'now', lastOpenedAt: 'now' },
      files: [], notebook: [], claudeSessionId: null, memory: '', decisionCount: 0
    })
    useApp.getState().setFiles([
      { relPath: 'sources/a.csv', name: 'a.csv', bytes: 10, sha256: 'x', addedAt: 'now', role: 'opening', rows: 5 }
    ])
    const st = useApp.getState()
    expect(st.project?.files).toHaveLength(1)
    expect(st.project?.summary.name).toBe('Acme')
  })

  it('ignores setFiles when no project is open', () => {
    expect(() => useApp.getState().setFiles([])).not.toThrow()
    expect(useApp.getState().project).toBeNull()
  })
})
