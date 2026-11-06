/**
 * Finding, installing and driving the Claude CLI.
 *
 * The app does not require the user to install anything by hand: if `claude`
 * is already on PATH it is used, and otherwise the CLI is installed *locally*
 * into the app's own data directory. A local install is deliberate — a global
 * `npm -g` needs elevation on Windows often enough to be a support burden,
 * and it would mutate a machine the user did not ask us to change.
 *
 * Process spawning and filesystem access are injected rather than imported so
 * the argument construction and the stream parsing can be unit-tested without
 * a real CLI or a real network.
 */
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import type { ClaudeStreamEvent } from '../../shared/types'

export const CLI_PACKAGE = '@anthropic-ai/claude-code'

/** Everything the manager touches outside itself, so tests can replace it. */
export interface CliHost {
  run(
    cmd: string,
    args: string[],
    opts?: { cwd?: string; env?: Record<string, string | undefined> }
  ): Promise<{ code: number; stdout: string; stderr: string }>
  spawnStream(
    cmd: string,
    args: string[],
    opts?: { cwd?: string; env?: Record<string, string | undefined> }
  ): ChildProcessWithoutNullStreams
  exists(path: string): boolean
}

export const nodeHost: CliHost = {
  run: (cmd, args, opts) =>
    new Promise((resolve) => {
      const p = spawn(cmd, args, { ...opts, shell: process.platform === 'win32' })
      let stdout = ''
      let stderr = ''
      p.stdout?.on('data', (d) => (stdout += String(d)))
      p.stderr?.on('data', (d) => (stderr += String(d)))
      p.on('error', (e) => resolve({ code: -1, stdout, stderr: String(e) }))
      p.on('close', (code) => resolve({ code: code ?? -1, stdout, stderr }))
    }),
  spawnStream: (cmd, args, opts) =>
    spawn(cmd, args, {
      ...opts,
      shell: process.platform === 'win32'
    }) as ChildProcessWithoutNullStreams,
  exists: (p) => existsSync(p)
}

/** Where a local install puts the launcher, per platform. */
export function localBinPath(installDir: string, platform: string = process.platform): string {
  const bin = join(installDir, 'node_modules', '.bin')
  return platform === 'win32' ? join(bin, 'claude.cmd') : join(bin, 'claude')
}

/**
 * Build the argv for one non-interactive turn.
 *
 * `--output-format stream-json` is what makes the chat feel live; it also
 * requires `--verbose`, which is easy to forget and fails confusingly.
 * `--resume` is what lets a reopened project continue its conversation
 * instead of starting over.
 */
export function buildTurnArgs(opts: {
  prompt: string
  sessionId?: string | null
  model?: string
  addDirs?: string[]
  allowedTools?: string[]
  permissionMode?: 'default' | 'acceptEdits' | 'plan' | 'bypassPermissions'
}): string[] {
  const args = ['-p', opts.prompt, '--output-format', 'stream-json', '--verbose']
  if (opts.sessionId) args.push('--resume', opts.sessionId)
  if (opts.model) args.push('--model', opts.model)
  for (const d of opts.addDirs ?? []) args.push('--add-dir', d)
  if (opts.allowedTools?.length) args.push('--allowedTools', opts.allowedTools.join(','))
  if (opts.permissionMode) args.push('--permission-mode', opts.permissionMode)
  return args
}

/** Pull a semver out of `claude --version` output, which varies in wording. */
export function parseVersion(out: string): string | null {
  const m = out.match(/\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?/)
  return m ? m[0] : null
}

/**
 * Translate one stream-json line into an app event.
 *
 * Returns null for lines that carry nothing the UI needs, so the caller can
 * ignore them without special-casing. Unparseable lines return null rather
 * than throwing: a single malformed line must not abort a turn that is
 * otherwise producing good output.
 */
export function parseStreamLine(line: string): ClaudeStreamEvent | null {
  const trimmed = line.trim()
  if (!trimmed) return null

  let msg: Record<string, unknown>
  try {
    msg = JSON.parse(trimmed) as Record<string, unknown>
  } catch {
    return null
  }

  const type = msg.type as string | undefined

  if (type === 'system' && typeof msg.session_id === 'string') {
    return { type: 'session', sessionId: msg.session_id }
  }

  if (type === 'assistant') {
    const message = msg.message as { content?: unknown[] } | undefined
    const parts = Array.isArray(message?.content) ? message!.content : []
    const texts: string[] = []
    for (const part of parts as Record<string, unknown>[]) {
      if (part?.type === 'text' && typeof part.text === 'string') texts.push(part.text)
      if (part?.type === 'tool_use') {
        return {
          type: 'tool',
          name: String(part.name ?? 'tool'),
          detail: summariseToolInput(part.input)
        }
      }
    }
    if (texts.length) return { type: 'text', text: texts.join('') }
    return null
  }

  if (type === 'result') {
    if (msg.is_error) {
      return { type: 'error', message: String(msg.result ?? 'the turn failed') }
    }
    return {
      type: 'done',
      sessionId: typeof msg.session_id === 'string' ? msg.session_id : null
    }
  }

  return null
}

/** A one-line, non-leaky description of a tool call for the activity list. */
export function summariseToolInput(input: unknown): string {
  if (!input || typeof input !== 'object') return ''
  const o = input as Record<string, unknown>
  for (const key of ['command', 'file_path', 'path', 'pattern', 'query', 'description']) {
    const v = o[key]
    if (typeof v === 'string' && v.trim()) {
      return v.length > 160 ? `${v.slice(0, 157)}…` : v
    }
  }
  return ''
}

/**
 * Split a byte stream into complete lines.
 *
 * stream-json arrives in arbitrary chunks, so a naive split loses the
 * half-line at a chunk boundary — which in practice means dropping whichever
 * message happened to straddle it. This keeps the remainder.
 */
export class LineSplitter {
  private buffer = ''

  push(chunk: string): string[] {
    this.buffer += chunk
    const parts = this.buffer.split('\n')
    this.buffer = parts.pop() ?? ''
    return parts
  }

  /** Any trailing partial line, for when the process closes without a newline. */
  flush(): string[] {
    const rest = this.buffer
    this.buffer = ''
    return rest.trim() ? [rest] : []
  }
}

export class ClaudeCli {
  private host: CliHost
  private installDir: string
  private resolvedBin: string | null = null
  private active: ChildProcessWithoutNullStreams | null = null

  constructor(installDir: string, host: CliHost = nodeHost) {
    this.installDir = installDir
    this.host = host
  }

  /** The launcher in use, once detected or installed. */
  get binPath(): string | null {
    return this.resolvedBin
  }

  /** Prefer a system install; fall back to our own local copy. */
  async detect(): Promise<
    { ok: true; version: string; binPath: string; source: 'system' | 'local' } | { ok: false; reason: string }
  > {
    const system = await this.host.run('claude', ['--version'])
    const sysVersion = system.code === 0 ? parseVersion(system.stdout) : null
    if (sysVersion) {
      this.resolvedBin = 'claude'
      return { ok: true, version: sysVersion, binPath: 'claude', source: 'system' }
    }

    const local = localBinPath(this.installDir)
    if (this.host.exists(local)) {
      const r = await this.host.run(local, ['--version'])
      const v = r.code === 0 ? parseVersion(r.stdout) : null
      if (v) {
        this.resolvedBin = local
        return { ok: true, version: v, binPath: local, source: 'local' }
      }
    }
    return { ok: false, reason: 'the Claude CLI was not found on PATH or in the app data folder' }
  }

  /**
   * Install the CLI into the app's own folder.
   *
   * `--no-audit --no-fund` keeps the output readable; `--omit=dev` keeps the
   * install small. We do not touch the global prefix.
   */
  async install(
    onProgress?: (step: string, percent: number) => void
  ): Promise<{ ok: true; version: string; binPath: string } | { ok: false; reason: string }> {
    onProgress?.('preparing the install folder', 10)
    const init = await this.host.run('npm', ['init', '-y'], { cwd: this.installDir })
    if (init.code !== 0 && !this.host.exists(join(this.installDir, 'package.json'))) {
      return { ok: false, reason: `could not prepare the install folder: ${init.stderr.trim()}` }
    }

    onProgress?.('downloading the Claude CLI', 35)
    const res = await this.host.run(
      'npm',
      ['install', CLI_PACKAGE, '--no-audit', '--no-fund', '--omit=dev'],
      { cwd: this.installDir }
    )
    if (res.code !== 0) {
      return { ok: false, reason: `npm install failed: ${(res.stderr || res.stdout).trim().slice(-400)}` }
    }

    onProgress?.('verifying the install', 85)
    const bin = localBinPath(this.installDir)
    if (!this.host.exists(bin)) {
      return { ok: false, reason: 'the CLI installed but its launcher is missing' }
    }
    const check = await this.host.run(bin, ['--version'])
    const version = parseVersion(check.stdout)
    if (!version) {
      return { ok: false, reason: 'the installed CLI did not report a version' }
    }
    this.resolvedBin = bin
    onProgress?.('ready', 100)
    return { ok: true, version, binPath: bin }
  }

  /** Run one turn, emitting events as they arrive. Resolves when it closes. */
  async runTurn(
    opts: Parameters<typeof buildTurnArgs>[0] & { cwd: string },
    onEvent: (e: ClaudeStreamEvent) => void
  ): Promise<void> {
    if (!this.resolvedBin) {
      onEvent({ type: 'error', message: 'the Claude CLI is not ready yet' })
      return
    }
    const args = buildTurnArgs(opts)
    const child = this.host.spawnStream(this.resolvedBin, args, { cwd: opts.cwd })
    this.active = child

    const splitter = new LineSplitter()
    let stderr = ''

    child.stdout?.setEncoding?.('utf8')
    child.stdout?.on('data', (chunk: string | Buffer) => {
      for (const line of splitter.push(String(chunk))) {
        const ev = parseStreamLine(line)
        if (ev) onEvent(ev)
      }
    })
    child.stderr?.on('data', (d: string | Buffer) => (stderr += String(d)))

    await new Promise<void>((resolve) => {
      child.on('error', (e: Error) => {
        onEvent({ type: 'error', message: e.message })
        resolve()
      })
      child.on('close', (code: number | null) => {
        for (const line of splitter.flush()) {
          const ev = parseStreamLine(line)
          if (ev) onEvent(ev)
        }
        if (code !== 0 && code !== null) {
          onEvent({
            type: 'error',
            message: stderr.trim() || `the CLI exited with code ${code}`
          })
        }
        this.active = null
        resolve()
      })
    })
  }

  /** Stop the running turn, if any. */
  cancel(): void {
    this.active?.kill()
    this.active = null
  }
}
