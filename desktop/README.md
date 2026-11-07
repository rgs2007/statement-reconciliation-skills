# FlowingSoft Reconciler — Windows desktop app

A desktop interface for the reconciliation skills. It installs Claude for you,
installs the skills into each project, and gives you a notebook on the left and
a chat on the right. Everything a project produces is saved in one folder you
can back up, move or hand to a colleague.

```
┌──────────────────────────────────────────────────────────────┐
│  FlowingSoft Reconciler          12 decisions · Claude 1.x   │
├────────┬──────────────────────────────┬──────────────────────┤
│ Files  │  Notebook                    │  Chat                │
│ Roles  │  metrics · tables · charts   │  questions           │
│ Reports│  reports · run status        │  tool activity       │
└────────┴──────────────────────────────┴──────────────────────┘
```

## Running it

```bash
cd desktop
npm install
npm run dev          # development, with hot reload
npm test             # 187 unit tests
npm run typecheck
npm run dist:win     # build the Windows installer (NSIS) into release/
```

`dist:win` produces an installer that bundles the skills from `../skills`, so
the app ships with them rather than fetching them.

## What happens on first run

1. The app looks for `claude` on PATH.
2. If it is not there, **Install Claude** fetches it with npm into the app's
   own data folder — not globally. A global install needs elevation on Windows
   often enough to be a support burden, and it would change a machine the user
   did not ask us to change.
3. Creating a project copies all six skills into `<project>/.claude/skills/`.

Installing the skills **per project** rather than into the home directory is
deliberate: a project folder is then self-describing, and copying it to another
machine reconciles the same way against the same skill version. A home-directory
install would silently upgrade old projects to new skill behaviour, which for an
auditable process is the wrong default.

## The project folder

```
<project>/
  project.json          name, files and their roles, Claude session id
  MEMORY.md             the narrative record the AI reads on resume
  decisions.jsonl       the audit log of judgement calls
  notebook.json         the notebook cells
  sources/              copies of your files — the originals are never touched
  runs/run-NNN/         metrics.json, breaks.csv, residual.csv, questions.json
  reports/              generated reports
  .claude/skills/       the six skills, project-scoped
```

Uploads are **copied in**, not referenced. A reconciliation that points at a
file elsewhere silently changes meaning when that file moves or is edited, and
the sha256 recorded for each file is what makes a re-run provably the same
input.

Resuming is the normal case: reopening a project restores the notebook, the
files and their roles, and the Claude session id, so the conversation continues
rather than restarting. `MEMORY.md` is what the AI reads first.

## Architecture

| Layer | Choice | Why |
|---|---|---|
| Shell | Electron | Ships Node, which is what runs the Claude CLI |
| Build | electron-vite | Fast HMR, standard three-target layout |
| UI | React 18 + TypeScript | — |
| Styling | Tailwind | Tokens live in `tailwind.config.js` + `theme/brand.ts` |
| State | Zustand | State here is small and mostly a cache of disk |
| Markdown | react-markdown + remark-gfm | Reports are markdown, with tables |
| Charts | Recharts | Declarative, React-native, no imperative canvas |
| Tests | Vitest + Testing Library | Same transform pipeline as the build |
| Installer | electron-builder (NSIS) | — |

**Security.** Context isolation on, node integration off, sandboxed renderer,
and a CSP that forbids remote script. The renderer never touches the
filesystem or spawns a process: every privileged action is one named IPC
channel declared in `src/shared/types.ts`. Project-relative paths are resolved
through a guard that refuses anything escaping the project folder, even though
the renderer is our own code.

## Tests

```bash
npm test                  # 187 tests
npm run test:coverage
```

| Suite | Covers |
|---|---|
| `tests/main/claude-cli` | argv construction, version parsing, stream-json parsing, chunk splitting, detection, local install, turn streaming |
| `tests/main/project-store` | folder layout, file copy and hashing, duplicate names, roles, session resume, MEMORY.md, run/metrics/questions reading, path traversal |
| `tests/main/skills-installer` | the full required set, per-project install, incomplete bundles |
| `tests/main/notebook-builder` | CSV parsing with quoted comma-decimals, gap composition, question rendering, break ordering |
| `tests/renderer/store` | streamed text landing in one bubble, tool activity, project switching |
| `tests/renderer/format` | money signs, percentages, relative time, the health thresholds |
| `tests/renderer/components` | metrics display, collapse, numeric alignment, Enter vs Shift+Enter, install states, role editing |

The CLI tests inject a fake host, so none of them need Claude installed, a
network, or a real child process — which is what lets CI run them.

Two of these are worth knowing about if you change the code:

- **CSV parsing is hand-rolled on purpose.** Reconciliation data is full of quoted comma-decimal amounts like `"1.234,56"`. Splitting on commas corrupts every figure, so the parser handles quotes, escaped quotes and CRLF, and there are tests for each.
- **`LineSplitter` exists because stream-json arrives in arbitrary chunks.** A naive split loses whichever message straddles a chunk boundary. There is a test for exactly that.

## Branding

`src/renderer/src/theme/brand.ts` is the single place to rebrand, alongside the
`flow` palette in `tailwind.config.js`. Nothing else hard-codes a colour.

**www.flowingsoft.com could not be reached from the build environment, so the
current tokens are a coherent identity built around the name rather than a copy
of the live site.** The flow-mark — three strands converging — is inline SVG in
the same file, and `resources/icon.{svg,png}` is the app icon. Replace the
hexes, the mark and the icon with the real assets and the whole app follows.
