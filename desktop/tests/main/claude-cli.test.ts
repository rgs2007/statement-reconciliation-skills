/**
 * The Claude CLI manager.
 *
 * These are the highest-value tests in the app: argument construction and
 * stream parsing are where a silent mistake produces a chat that looks
 * plausible and is wrong, or a turn that never streams. The host is injected
 * so none of this needs a real CLI, a network, or a machine with Claude
 * installed — which also means CI can check it.
 */
import { EventEmitter } from 'node:events'
import { describe, expect, it, vi } from 'vitest'
import {
  ClaudeCli,
  CLI_PACKAGE,
  LineSplitter,
  buildTurnArgs,
  localBinPath,
  parseStreamLine,
  parseVersion,
  summariseToolInput,
  type CliHost
} from '../../src/main/services/claude-cli'
import type { ClaudeStreamEvent } from '../../src/shared/types'

function fakeHost(overrides: Partial<CliHost> = {}): CliHost {
  return {
    run: vi.fn().mockResolvedValue({ code: 1, stdout: '', stderr: 'not found' }),
    spawnStream: vi.fn(),
    exists: vi.fn().mockReturnValue(false),
    ...overrides
  }
}

/** A stand-in child process whose streams we can drive from the test. */
function fakeChild(): EventEmitter & {
  stdout: EventEmitter & { setEncoding?: () => void }
  stderr: EventEmitter
  kill: () => void
} {
  const child = new EventEmitter() as never as ReturnType<typeof fakeChild>
  const stdout = new EventEmitter() as (typeof child)['stdout']
  stdout.setEncoding = (): void => undefined
  Object.assign(child, { stdout, stderr: new EventEmitter(), kill: vi.fn() })
  return child
}

describe('buildTurnArgs', () => {
  it('always streams, and always passes --verbose with it', () => {
    // stream-json without --verbose fails with a confusing message; the two
    // must never be separated.
    const args = buildTurnArgs({ prompt: 'why does this not tie out?' })
    expect(args).toEqual(['-p', 'why does this not tie out?', '--output-format', 'stream-json', '--verbose'])
  })

  it('resumes the session so a reopened project continues the conversation', () => {
    const args = buildTurnArgs({ prompt: 'carry on', sessionId: 'sess-42' })
    expect(args).toContain('--resume')
    expect(args[args.indexOf('--resume') + 1]).toBe('sess-42')
  })

  it('omits --resume when there is no session yet', () => {
    expect(buildTurnArgs({ prompt: 'x', sessionId: null })).not.toContain('--resume')
  })

  it('passes each project directory separately', () => {
    const args = buildTurnArgs({ prompt: 'x', addDirs: ['/p/one', '/p/two'] })
    const dirs = args.filter((_, i) => args[i - 1] === '--add-dir')
    expect(dirs).toEqual(['/p/one', '/p/two'])
  })

  it('joins allowed tools into one comma-separated value', () => {
    const args = buildTurnArgs({ prompt: 'x', allowedTools: ['Read', 'Bash'] })
    expect(args[args.indexOf('--allowedTools') + 1]).toBe('Read,Bash')
  })

  it('keeps the prompt as a single argv entry even with newlines', () => {
    // Splitting a multi-line prompt would turn the rest into stray flags.
    const prompt = 'line one\nline two --not-a-flag'
    expect(buildTurnArgs({ prompt })[1]).toBe(prompt)
  })
})

describe('parseVersion', () => {
  it.each([
    ['1.2.3 (Claude Code)', '1.2.3'],
    ['claude version 0.14.7', '0.14.7'],
    ['2.0.0-beta.4', '2.0.0-beta.4']
  ])('reads %s', (input, expected) => {
    expect(parseVersion(input)).toBe(expected)
  })

  it('returns null when there is no version to read', () => {
    expect(parseVersion('command not found')).toBeNull()
  })
})

describe('parseStreamLine', () => {
  it('captures the session id so the project can resume later', () => {
    const ev = parseStreamLine(JSON.stringify({ type: 'system', session_id: 'abc' }))
    expect(ev).toEqual({ type: 'session', sessionId: 'abc' })
  })

  it('extracts assistant text', () => {
    const ev = parseStreamLine(
      JSON.stringify({ type: 'assistant', message: { content: [{ type: 'text', text: 'Hello' }] } })
    )
    expect(ev).toEqual({ type: 'text', text: 'Hello' })
  })

  it('joins multiple text parts rather than dropping any', () => {
    const ev = parseStreamLine(
      JSON.stringify({
        type: 'assistant',
        message: { content: [{ type: 'text', text: 'a' }, { type: 'text', text: 'b' }] }
      })
    )
    expect(ev).toEqual({ type: 'text', text: 'ab' })
  })

  it('surfaces tool use, so a computed figure is visibly computed', () => {
    const ev = parseStreamLine(
      JSON.stringify({
        type: 'assistant',
        message: {
          content: [{ type: 'tool_use', name: 'Bash', input: { command: 'python reconcile.py' } }]
        }
      })
    )
    expect(ev).toEqual({ type: 'tool', name: 'Bash', detail: 'python reconcile.py' })
  })

  it('reports a finished turn with its session id', () => {
    const ev = parseStreamLine(JSON.stringify({ type: 'result', session_id: 'xyz' }))
    expect(ev).toEqual({ type: 'done', sessionId: 'xyz' })
  })

  it('reports an errored result as an error, not a completion', () => {
    const ev = parseStreamLine(
      JSON.stringify({ type: 'result', is_error: true, result: 'rate limited' })
    )
    expect(ev).toEqual({ type: 'error', message: 'rate limited' })
  })

  it.each(['', '   ', 'not json at all', '{"broken":'])(
    'ignores the unusable line %j instead of throwing',
    (line) => {
      // One malformed line must not abort a turn that is otherwise fine.
      expect(() => parseStreamLine(line)).not.toThrow()
      expect(parseStreamLine(line)).toBeNull()
    }
  )

  it('ignores message types the UI has no use for', () => {
    expect(parseStreamLine(JSON.stringify({ type: 'user', message: {} }))).toBeNull()
  })
})

describe('summariseToolInput', () => {
  it('prefers the most descriptive field available', () => {
    expect(summariseToolInput({ file_path: '/p/a.csv' })).toBe('/p/a.csv')
    expect(summariseToolInput({ command: 'ls', file_path: '/p/a.csv' })).toBe('ls')
  })

  it('truncates something long rather than flooding the activity list', () => {
    const out = summariseToolInput({ command: 'x'.repeat(400) })
    expect(out.length).toBeLessThanOrEqual(160)
    expect(out.endsWith('…')).toBe(true)
  })

  it.each([null, undefined, 42, 'text', {}])('handles %j safely', (input) => {
    expect(summariseToolInput(input)).toBe('')
  })
})

describe('LineSplitter', () => {
  it('keeps a line that straddles two chunks', () => {
    // Without this, whichever message lands on a chunk boundary is lost.
    const s = new LineSplitter()
    expect(s.push('{"a":1}\n{"b":')).toEqual(['{"a":1}'])
    expect(s.push('2}\n')).toEqual(['{"b":2}'])
  })

  it('returns a trailing partial line on flush', () => {
    const s = new LineSplitter()
    s.push('{"a":1}')
    expect(s.flush()).toEqual(['{"a":1}'])
    expect(s.flush()).toEqual([])
  })

  it('returns nothing to flush when the stream ended cleanly', () => {
    const s = new LineSplitter()
    s.push('{"a":1}\n')
    expect(s.flush()).toEqual([])
  })
})

describe('localBinPath', () => {
  it('uses the .cmd launcher on Windows', () => {
    expect(localBinPath('C:\\data', 'win32')).toContain('claude.cmd')
  })

  it('uses the plain launcher elsewhere', () => {
    const p = localBinPath('/data', 'linux')
    expect(p).toContain('claude')
    expect(p).not.toContain('.cmd')
  })
})

describe('ClaudeCli.detect', () => {
  it('prefers a system install when one works', async () => {
    const host = fakeHost({
      run: vi.fn().mockResolvedValue({ code: 0, stdout: '1.2.3', stderr: '' })
    })
    const res = await new ClaudeCli('/data', host).detect()
    expect(res).toMatchObject({ ok: true, version: '1.2.3', source: 'system' })
  })

  it('falls back to the local install when PATH has nothing', async () => {
    const local = localBinPath('/data')
    const host = fakeHost({
      run: vi.fn(async (cmd: string) =>
        cmd === 'claude'
          ? { code: 127, stdout: '', stderr: 'not found' }
          : { code: 0, stdout: '9.9.9', stderr: '' }
      ),
      exists: vi.fn((p: string) => p === local)
    })
    const res = await new ClaudeCli('/data', host).detect()
    expect(res).toMatchObject({ ok: true, version: '9.9.9', source: 'local' })
  })

  it('reports not-found rather than throwing, so the UI can offer to install', async () => {
    const res = await new ClaudeCli('/data', fakeHost()).detect()
    expect(res.ok).toBe(false)
  })

  it('treats an installed-but-broken local binary as not found', async () => {
    const host = fakeHost({
      run: vi.fn().mockResolvedValue({ code: 1, stdout: 'garbage', stderr: '' }),
      exists: vi.fn().mockReturnValue(true)
    })
    expect((await new ClaudeCli('/data', host).detect()).ok).toBe(false)
  })
})

describe('ClaudeCli.install', () => {
  it('installs locally and never touches the global prefix', async () => {
    const calls: string[][] = []
    const host = fakeHost({
      run: vi.fn(async (cmd: string, args: string[]) => {
        calls.push([cmd, ...args])
        return { code: 0, stdout: '1.0.0', stderr: '' }
      }),
      exists: vi.fn().mockReturnValue(true)
    })
    const res = await new ClaudeCli('/data', host).install()
    expect(res.ok).toBe(true)

    const install = calls.find((c) => c[1] === 'install')
    expect(install).toBeDefined()
    expect(install).toContain(CLI_PACKAGE)
    // A global install needs elevation on Windows and mutates the machine.
    expect(calls.flat()).not.toContain('-g')
    expect(calls.flat()).not.toContain('--global')
  })

  it('reports progress so the installer is not a blank wait', async () => {
    const host = fakeHost({
      run: vi.fn().mockResolvedValue({ code: 0, stdout: '1.0.0', stderr: '' }),
      exists: vi.fn().mockReturnValue(true)
    })
    const steps: number[] = []
    await new ClaudeCli('/data', host).install((_s, pct) => steps.push(pct))
    expect(steps.length).toBeGreaterThan(1)
    expect(steps.at(-1)).toBe(100)
    expect([...steps].sort((a, b) => a - b)).toEqual(steps)
  })

  it('returns the npm failure instead of claiming success', async () => {
    const host = fakeHost({
      run: vi.fn(async (_c: string, args: string[]) =>
        args[0] === 'install'
          ? { code: 1, stdout: '', stderr: 'EACCES' }
          : { code: 0, stdout: '', stderr: '' }
      ),
      exists: vi.fn().mockReturnValue(true)
    })
    const res = await new ClaudeCli('/data', host).install()
    expect(res.ok).toBe(false)
    if (!res.ok) expect(res.reason).toContain('EACCES')
  })

  it('fails when the launcher is missing after a reported success', async () => {
    const host = fakeHost({
      run: vi.fn().mockResolvedValue({ code: 0, stdout: '1.0.0', stderr: '' }),
      exists: vi.fn((p: string) => p.endsWith('package.json'))
    })
    expect((await new ClaudeCli('/data', host).install()).ok).toBe(false)
  })
})

describe('ClaudeCli.runTurn', () => {
  it('streams events in order and ends with done', async () => {
    const child = fakeChild()
    const host = fakeHost({
      run: vi.fn().mockResolvedValue({ code: 0, stdout: '1.0.0', stderr: '' }),
      spawnStream: vi.fn().mockReturnValue(child)
    })
    const cli = new ClaudeCli('/data', host)
    await cli.detect()

    const events: ClaudeStreamEvent[] = []
    const turn = cli.runTurn({ prompt: 'go', cwd: '/p' }, (e) => events.push(e))

    child.stdout.emit('data', `${JSON.stringify({ type: 'system', session_id: 's1' })}\n`)
    child.stdout.emit(
      'data',
      `${JSON.stringify({ type: 'assistant', message: { content: [{ type: 'text', text: 'hi' }] } })}\n`
    )
    child.stdout.emit('data', `${JSON.stringify({ type: 'result', session_id: 's1' })}\n`)
    child.emit('close', 0)
    await turn

    expect(events.map((e) => e.type)).toEqual(['session', 'text', 'done'])
  })

  it('parses a final line that arrived without a trailing newline', async () => {
    const child = fakeChild()
    const host = fakeHost({
      run: vi.fn().mockResolvedValue({ code: 0, stdout: '1.0.0', stderr: '' }),
      spawnStream: vi.fn().mockReturnValue(child)
    })
    const cli = new ClaudeCli('/data', host)
    await cli.detect()

    const events: ClaudeStreamEvent[] = []
    const turn = cli.runTurn({ prompt: 'go', cwd: '/p' }, (e) => events.push(e))
    child.stdout.emit('data', JSON.stringify({ type: 'result', session_id: 's9' }))
    child.emit('close', 0)
    await turn

    expect(events).toEqual([{ type: 'done', sessionId: 's9' }])
  })

  it('reports a non-zero exit with whatever stderr said', async () => {
    const child = fakeChild()
    const host = fakeHost({
      run: vi.fn().mockResolvedValue({ code: 0, stdout: '1.0.0', stderr: '' }),
      spawnStream: vi.fn().mockReturnValue(child)
    })
    const cli = new ClaudeCli('/data', host)
    await cli.detect()

    const events: ClaudeStreamEvent[] = []
    const turn = cli.runTurn({ prompt: 'go', cwd: '/p' }, (e) => events.push(e))
    child.stderr.emit('data', 'authentication required')
    child.emit('close', 1)
    await turn

    expect(events).toEqual([{ type: 'error', message: 'authentication required' }])
  })

  it('refuses to run before the CLI is ready, rather than spawning nothing', async () => {
    const events: ClaudeStreamEvent[] = []
    await new ClaudeCli('/data', fakeHost()).runTurn({ prompt: 'x', cwd: '/p' }, (e) =>
      events.push(e)
    )
    expect(events[0]?.type).toBe('error')
  })

  it('runs in the project folder so relative paths resolve there', async () => {
    const child = fakeChild()
    const spawnStream = vi.fn().mockReturnValue(child)
    const host = fakeHost({
      run: vi.fn().mockResolvedValue({ code: 0, stdout: '1.0.0', stderr: '' }),
      spawnStream
    })
    const cli = new ClaudeCli('/data', host)
    await cli.detect()
    const turn = cli.runTurn({ prompt: 'x', cwd: '/projects/acme' }, () => undefined)
    child.emit('close', 0)
    await turn
    expect(spawnStream.mock.calls[0]?.[2]).toMatchObject({ cwd: '/projects/acme' })
  })
})
