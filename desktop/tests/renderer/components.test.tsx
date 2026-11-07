/**
 * Component behaviour.
 *
 * These check what a user would notice: that a figure is rendered the way an
 * accountant needs to read it, that tool activity is visible, that Enter
 * sends and Shift+Enter does not, and that a file's role can be corrected
 * without a round-trip through the chat.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ChatPane, STARTERS } from '../../src/renderer/src/components/ChatPane'
import { Cell, MetricsGrid, NotebookPane } from '../../src/renderer/src/components/NotebookPane'
import { FileList, InstallBadge, ReportList } from '../../src/renderer/src/components/Sidebar'
import type { ChatMessage, NotebookCell, ProjectFile, ReconMetrics } from '../../src/shared/types'

const metrics: ReconMetrics = {
  keys_total: 12,
  reconciled: 7,
  reconciled_pct: 58.3,
  sign_convention: 'closing = opening + movements',
  gap_gross: 1991939.95,
  gap_net: -1974330.85,
  gap_gross_at_parent: 1990344.19,
  movements_unattributed: 1,
  attribution_rate_pct: 97.3,
  materiality: 0.01
}

describe('MetricsGrid', () => {
  it('shows gross and net separately, because they answer different questions', () => {
    render(<MetricsGrid metrics={metrics} />)
    expect(screen.getByText('1,991,939.95')).toBeInTheDocument()
    expect(screen.getByText('-1,974,330.85')).toBeInTheDocument()
    expect(screen.getByText('misposted activity')).toBeInTheDocument()
    expect(screen.getByText('unexplained value')).toBeInTheDocument()
  })

  it('shows the equation that was established, not an assumed one', () => {
    render(<MetricsGrid metrics={metrics} />)
    expect(screen.getByText('closing = opening + movements')).toBeInTheDocument()
  })

  it('surfaces caveats prominently — a cause not tested for is not ruled out', () => {
    render(
      <MetricsGrid
        metrics={{ ...metrics, caveats: ['detect-duplicates did not run', 'no decision log applied'] }}
      />
    )
    expect(screen.getByText(/detect-duplicates did not run/)).toBeInTheDocument()
    expect(screen.getByText(/no decision log applied/)).toBeInTheDocument()
  })

  it('renders without optional figures rather than showing NaN', () => {
    render(
      <MetricsGrid
        metrics={{
          keys_total: 1, reconciled: 1, reconciled_pct: 100,
          sign_convention: 'closing = opening', gap_gross: 0, gap_net: 0
        }}
      />
    )
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })
})

describe('Cell', () => {
  it('renders markdown, including tables', () => {
    const cell: NotebookCell = {
      id: 'c1', kind: 'markdown', title: 'Findings',
      body: '## Decimal shift\n\n| key | gap |\n|---|---|\n| 6652-04 | -1,944,943.11 |',
      createdAt: 'now'
    }
    render(<Cell cell={cell} />)
    expect(screen.getByText('Decimal shift')).toBeInTheDocument()
    expect(screen.getByText('-1,944,943.11')).toBeInTheDocument()
  })

  it('collapses and expands', async () => {
    const user = userEvent.setup()
    const cell: NotebookCell = {
      id: 'c1', kind: 'markdown', title: 'Scope', body: 'January 2026', createdAt: 'now'
    }
    render(<Cell cell={cell} />)
    expect(screen.getByText('January 2026')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Collapse' }))
    expect(screen.queryByText('January 2026')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Expand' }))
    expect(screen.getByText('January 2026')).toBeInTheDocument()
  })

  it('right-aligns numeric columns so figures line up', () => {
    const cell: NotebookCell = {
      id: 'c1', kind: 'table', title: 'Breaks',
      columns: ['key', 'gap'], rows: [['1000-01', '-5000.00']], createdAt: 'now'
    }
    render(<Cell cell={cell} />)
    const gapCell = screen.getByText('-5000.00')
    expect(gapCell.className).toContain('text-right')
    expect(screen.getByText('1000-01').className).not.toContain('text-right')
  })

  it('marks a skipped step rather than letting it look complete', () => {
    const cell: NotebookCell = {
      id: 'c1', kind: 'status', title: 'Run progress',
      steps: [
        { name: 'equation', state: 'done' },
        { name: 'detect-duplicates', state: 'skipped' }
      ],
      createdAt: 'now'
    }
    render(<Cell cell={cell} />)
    expect(screen.getByText('not tested for')).toBeInTheDocument()
  })

  it('can be removed', async () => {
    const user = userEvent.setup()
    const onRemove = vi.fn()
    render(
      <Cell
        cell={{ id: 'c9', kind: 'markdown', title: 'Temp', body: 'x', createdAt: 'now' }}
        onRemove={onRemove}
      />
    )
    await user.click(screen.getByRole('button', { name: 'Remove Temp' }))
    expect(onRemove).toHaveBeenCalledWith('c9')
  })

  it('says so plainly when a chart has nothing to show', () => {
    render(
      <Cell cell={{ id: 'c1', kind: 'chart', title: 'Gap', series: [], createdAt: 'now' }} />
    )
    expect(screen.getByText('Nothing to chart yet.')).toBeInTheDocument()
  })
})

describe('NotebookPane', () => {
  it('explains what to do when empty instead of showing a blank pane', () => {
    render(<NotebookPane cells={[]} />)
    expect(screen.getByText('The notebook is empty')).toBeInTheDocument()
    expect(screen.getByText(/Drop|Add your statement files/)).toBeInTheDocument()
  })

  it('renders cells in order', () => {
    render(
      <NotebookPane
        cells={[
          { id: 'a', kind: 'markdown', title: 'First', body: '1', createdAt: 'now' },
          { id: 'b', kind: 'metrics', title: 'Second', metrics, createdAt: 'now' }
        ]}
      />
    )
    const titles = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(titles).toEqual(['First', 'Second'])
  })
})

describe('ChatPane', () => {
  const noop = (): void => undefined

  it('offers starters before any conversation exists', () => {
    render(<ChatPane messages={[]} busy={false} onSend={noop} onCancel={noop} />)
    expect(screen.getByText(STARTERS[0])).toBeInTheDocument()
  })

  it('sends a starter in one click', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatPane messages={[]} busy={false} onSend={onSend} onCancel={noop} />)
    await user.click(screen.getByText(STARTERS[0]))
    expect(onSend).toHaveBeenCalledWith(STARTERS[0])
  })

  it('sends on Enter and clears the box', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatPane messages={[]} busy={false} onSend={onSend} onCancel={noop} />)
    const box = screen.getByLabelText('Message')
    await user.type(box, 'why does this not tie out?{Enter}')
    expect(onSend).toHaveBeenCalledWith('why does this not tie out?')
    expect(box).toHaveValue('')
  })

  it('keeps Shift+Enter as a newline, since pasted context is multi-line', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatPane messages={[]} busy={false} onSend={onSend} onCancel={noop} />)
    const box = screen.getByLabelText('Message')
    await user.type(box, 'line one{Shift>}{Enter}{/Shift}line two')
    expect(onSend).not.toHaveBeenCalled()
    expect(box).toHaveValue('line one\nline two')
  })

  it('does not send whitespace', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatPane messages={[]} busy={false} onSend={onSend} onCancel={noop} />)
    await user.type(screen.getByLabelText('Message'), '   {Enter}')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('shows tool activity, so a computed figure is visibly computed', () => {
    const messages: ChatMessage[] = [
      {
        id: 'a', role: 'assistant', text: 'The gross gap is 1,991,939.95.', at: 'now',
        tools: [{ name: 'Bash', detail: 'python reconcile.py datamap.json' }]
      }
    ]
    render(<ChatPane messages={messages} busy={false} onSend={noop} onCancel={noop} />)
    expect(screen.getByTestId('tool-activity')).toBeInTheDocument()
    expect(screen.getByText('Bash')).toBeInTheDocument()
    expect(screen.getByText('python reconcile.py datamap.json')).toBeInTheDocument()
  })

  it('offers Stop while a turn is running', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    render(<ChatPane messages={[]} busy onSend={noop} onCancel={onCancel} />)
    expect(screen.queryByRole('button', { name: 'Send' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Stop' }))
    expect(onCancel).toHaveBeenCalled()
  })

  it('explains why it is disabled rather than just being dead', () => {
    render(
      <ChatPane
        messages={[]} busy={false} disabled disabledReason="Install Claude to start."
        onSend={noop} onCancel={noop}
      />
    )
    expect(screen.getByRole('status')).toHaveTextContent('Install Claude to start.')
    expect(screen.getByLabelText('Message')).toBeDisabled()
  })

  it('renders an error turn distinctly from an answer', () => {
    render(
      <ChatPane
        messages={[{ id: 'e', role: 'system', text: 'authentication required', at: 'now' }]}
        busy={false} onSend={noop} onCancel={noop}
      />
    )
    expect(screen.getByTestId('msg-system')).toHaveTextContent('authentication required')
  })
})

describe('InstallBadge', () => {
  it('shows the version and where it came from once ready', () => {
    render(
      <InstallBadge
        state={{ status: 'ready', version: '1.2.3', binPath: 'claude', source: 'local' }}
        onInstall={() => undefined}
      />
    )
    expect(screen.getByTestId('install-ready')).toHaveTextContent('1.2.3')
    expect(screen.getByText('(local)')).toBeInTheDocument()
  })

  it('offers to install, and reassures that nothing on the machine changes', async () => {
    const user = userEvent.setup()
    const onInstall = vi.fn()
    render(<InstallBadge state={{ status: 'missing', reason: 'not found' }} onInstall={onInstall} />)
    expect(screen.getByText(/nothing on your machine is changed/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Install Claude' }))
    expect(onInstall).toHaveBeenCalled()
  })

  it('shows real progress rather than a spinner', () => {
    render(
      <InstallBadge
        state={{ status: 'installing', step: 'downloading the Claude CLI', percent: 35 }}
        onInstall={() => undefined}
      />
    )
    expect(screen.getByTestId('install-progress')).toHaveTextContent('downloading the Claude CLI')
    expect(screen.getByText('35%')).toBeInTheDocument()
  })

  it('shows the failure reason so it can be acted on', () => {
    render(
      <InstallBadge state={{ status: 'error', message: 'npm install failed: EACCES' }} onInstall={() => undefined} />
    )
    expect(screen.getByText(/EACCES/)).toBeInTheDocument()
  })
})

describe('FileList', () => {
  const file: ProjectFile = {
    relPath: 'sources/initial_balance.csv',
    name: 'initial_balance.csv',
    bytes: 2048,
    sha256: 'a'.repeat(64),
    addedAt: new Date().toISOString(),
    role: 'opening',
    rows: 7806
  }

  it('shows size, rows and a hash prefix for provenance', () => {
    render(<FileList files={[file]} onRole={() => undefined} />)
    expect(screen.getByText('initial_balance.csv')).toBeInTheDocument()
    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
    expect(screen.getByText('7,806 rows')).toBeInTheDocument()
    expect(screen.getByTitle('a'.repeat(64))).toBeInTheDocument()
  })

  it('lets the role be corrected without a chat round-trip', async () => {
    const user = userEvent.setup()
    const onRole = vi.fn()
    render(<FileList files={[file]} onRole={onRole} />)
    await user.selectOptions(screen.getByLabelText('Role for initial_balance.csv'), 'movements')
    expect(onRole).toHaveBeenCalledWith('sources/initial_balance.csv', 'movements')
  })

  it('allows clearing a wrong guess', async () => {
    const user = userEvent.setup()
    const onRole = vi.fn()
    render(<FileList files={[file]} onRole={onRole} />)
    await user.selectOptions(screen.getByLabelText('Role for initial_balance.csv'), '')
    expect(onRole).toHaveBeenCalledWith('sources/initial_balance.csv', null)
  })

  it('tells the user what to add when there are none', () => {
    render(<FileList files={[]} onRole={() => undefined} />)
    expect(screen.getByText(/CSV, Excel or PDF/)).toBeInTheDocument()
  })

  // Drag and drop alone is undiscoverable — the button has to be visible in
  // both states, or an empty project is a dead end and a populated one has
  // no way to grow.
  it('offers a visible way in when the project is empty', async () => {
    const user = userEvent.setup()
    const onAdd = vi.fn()
    render(<FileList files={[]} onRole={() => undefined} onAdd={onAdd} />)
    await user.click(screen.getByTestId('add-files'))
    expect(onAdd).toHaveBeenCalledOnce()
  })

  it('keeps that way in once files are listed', async () => {
    const user = userEvent.setup()
    const onAdd = vi.fn()
    render(<FileList files={[file]} onRole={() => undefined} onAdd={onAdd} />)
    await user.click(screen.getByTestId('add-files'))
    expect(onAdd).toHaveBeenCalledOnce()
    expect(screen.getByText('initial_balance.csv')).toBeInTheDocument()
  })

  it('renders without a button where adding is not offered', () => {
    render(<FileList files={[file]} onRole={() => undefined} />)
    expect(screen.queryByTestId('add-files')).toBeNull()
  })
})

describe('ReportList', () => {
  it('opens a report on click', async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(
      <ReportList reports={[{ name: 'reconciliation.md', relPath: 'reports/reconciliation.md' }]} onOpen={onOpen} />
    )
    await user.click(screen.getByText('reconciliation.md'))
    expect(onOpen).toHaveBeenCalledWith('reports/reconciliation.md')
  })

  it('says when there are none', () => {
    render(<ReportList reports={[]} onOpen={() => undefined} />)
    expect(screen.getByText('No reports yet.')).toBeInTheDocument()
  })
})
