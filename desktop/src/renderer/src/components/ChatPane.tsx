/**
 * The chat — the right pane.
 *
 * Tool activity is shown inline rather than hidden, because the value of this
 * tool is that every figure came from a step that actually ran. A chat that
 * only shows prose makes a computed answer and an invented one look identical.
 */
import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '@shared/types'

export const STARTERS = [
  'These files do not tie out — what is wrong with the data?',
  'Profile the files and tell me what you can see before computing anything.',
  'What is the largest single cause of the difference?',
  'Write the reconciliation report.'
] as const

function ToolActivity({ tools }: { tools: { name: string; detail: string }[] }): JSX.Element {
  return (
    <ul className="mb-2 space-y-1" data-testid="tool-activity">
      {tools.map((t, i) => (
        <li key={i} className="flex items-start gap-2 text-[11px] text-ink-500">
          <span className="mt-[3px] h-1.5 w-1.5 shrink-0 rounded-full bg-flow-500" />
          <span className="font-mono text-ink-400">{t.name}</span>
          {t.detail ? <span className="truncate">{t.detail}</span> : null}
        </li>
      ))}
    </ul>
  )
}

function Bubble({ m }: { m: ChatMessage }): JSX.Element {
  const isUser = m.role === 'user'
  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
      data-testid={`msg-${m.role}`}
    >
      <div
        className={`max-w-[92%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
          isUser
            ? 'bg-flow-600 text-white'
            : m.role === 'system'
              ? 'border border-red-900/60 bg-red-950/40 text-red-200'
              : 'border border-ink-800 bg-ink-900 text-ink-200'
        }`}
      >
        {m.tools?.length ? <ToolActivity tools={m.tools} /> : null}
        {m.text ? (
          isUser ? (
            <p className="whitespace-pre-wrap">{m.text}</p>
          ) : (
            <div className="[&_code]:rounded [&_code]:bg-ink-950 [&_code]:px-1 [&_li]:ml-4 [&_li]:list-disc [&_p]:mb-2 [&_p:last-child]:mb-0 [&_strong]:text-ink-100">
              <Markdown remarkPlugins={[remarkGfm]}>{m.text}</Markdown>
            </div>
          )
        ) : m.pending ? (
          <span className="text-xs text-ink-500">working…</span>
        ) : null}
      </div>
    </div>
  )
}

export function ChatPane({
  messages,
  busy,
  disabled,
  disabledReason,
  onSend,
  onCancel
}: {
  messages: ChatMessage[]
  busy: boolean
  disabled?: boolean
  disabledReason?: string
  onSend: (text: string) => void
  onCancel: () => void
}): JSX.Element {
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  const submit = (): void => {
    const text = draft.trim()
    if (!text || busy || disabled) return
    onSend(text)
    setDraft('')
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="space-y-2">
            <p className="text-xs leading-relaxed text-ink-500">
              Ask in any language — the answer, the questions and the report come back in the
              same one.
            </p>
            {STARTERS.map((s) => (
              <button
                key={s}
                type="button"
                disabled={disabled}
                onClick={() => onSend(s)}
                className="w-full rounded-md border border-ink-800 px-3 py-2 text-left text-xs text-ink-300 transition-colors hover:border-flow-700 hover:bg-ink-900 disabled:opacity-40"
              >
                {s}
              </button>
            ))}
          </div>
        ) : (
          messages.map((m) => <Bubble key={m.id} m={m} />)
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t border-ink-800 p-3">
        {disabled && disabledReason ? (
          <p className="mb-2 text-xs text-amber-400" role="status">
            {disabledReason}
          </p>
        ) : null}
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              // Enter sends; Shift+Enter is a newline. Accountants paste
              // multi-line context often enough that this matters.
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
            rows={3}
            disabled={disabled}
            placeholder="Ask about the reconciliation…"
            aria-label="Message"
            className="flex-1 resize-none rounded-md border border-ink-800 bg-ink-950 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-600 focus:border-flow-600 focus:outline-none disabled:opacity-50"
          />
          {busy ? (
            <button type="button" onClick={onCancel} className="btn-ghost">
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={disabled || !draft.trim()}
              className="btn-primary"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
