# Statement Reconciliation — agent skill

[![tests](https://github.com/rgs2007/statement-reconciliation-skills/actions/workflows/tests.yml/badge.svg)](https://github.com/rgs2007/statement-reconciliation-skills/actions/workflows/tests.yml)

A portable skill that drives a user through reconciling financial statements that do not tie out, and produces an auditable report: every discrepancy with evidence, rationale, a confidence level, and a remediation step.

Built from a real reconciliation of a 111k-row sub-ledger, then validated against an independent public dataset. The traps listed in the skill are ones that actually cost time, not hypotheticals.

## What it does

- **Drives the conversation.** Asks the user the questions only they can answer, one at a time, always with the evidence that prompted the question and always ranked by the amount at stake.
- **Reads structure, not the corpus.** Profiles files and shows *masked* previews — digits become `#`, letters `X` — so the shape of the data is visible without exposing confidential figures. Works on samples and residuals rather than whole ledgers.
- **Explains, not just detects.** Each finding carries a root-cause category, the figures it rests on, the alternatives rejected, and a HIGH/MEDIUM/LOW confidence grade.
- **Stays auditable.** Every judgement call is appended to `decisions.jsonl` with who decided, when, why and on what evidence. Re-running replays the log, so the numbers and the stated reasons can never drift apart.
- **Speaks the user's language.** Replies in whatever language the user writes in. Category codes and confidence labels stay in English so tooling and audit trails stay stable, with a glossary in the report.

## Install

### Claude Code (VS Code, JetBrains or terminal)

Project-scoped — shared with anyone who clones the repo:

```bash
mkdir -p .claude/skills
cp -r statement-reconciliation .claude/skills/
```

Personal, available in every project:

```bash
mkdir -p ~/.claude/skills
cp -r statement-reconciliation ~/.claude/skills/
```

Restart the session, then ask something like *"these two statements don't tie out, can you help me work out why"* — the skill triggers on the description, no command needed. Verify it loaded with `/skills` if your client supports it.

### Other agent tools

`SKILL.md` is plain Markdown with YAML frontmatter, and the references are plain Markdown. Any assistant that can read project instructions can use this: point it at `statement-reconciliation/SKILL.md`, or paste that file in as system instructions and keep the folder alongside. The two scripts are ordinary Python and run standalone.

## Requirements

```bash
pip install pandas            # required
pip install openpyxl          # only for .xlsx intake
pip install pdfplumber        # only for .pdf intake
```

Python 3.10+. The scripts are deliberately dependency-light so they run in restricted or offline environments.

## Layout

```
statement-reconciliation/
  SKILL.md                      orchestrator: rules, workflow, traps
  references/
    discovery.md                profiling, tiered exposure, locating keys
    intake.md                   guided Excel/PDF/CSV → clean tabular
    matching.md                 sign convention, attribution, gaps, rollup
    taxonomy.md                 12 root causes with signatures + remediation
    confidence.md               HIGH/MEDIUM/LOW rubric
    reporting.md                auditable report structure
  scripts/
    profile_files.py            masked structural profiler (csv/xlsx/pdf)
    reconcile.py                deterministic engine + structural detectors
    match_items.py              item matching incl. bounded subset-sum
    decisions.py                decision log: validate/append/resolve/replay
    make_report.py              auditable report generator (en/pt/es headings)
    selftest.py                 control + fault-injection test suite
  templates/
    decisions.schema.json       append-only decision log, closed vocabulary

tests/                          golden-file regression suite — see tests/README.md
  run_tests.py                  regenerate and compare against expected output
  make_fixtures.py              reproducible fixture sources
  test_golden.py                pytest wrapper
  fixtures/NN-name/
    sources/                    committed input files
    datamap.json                how the engine reads them
    expected/                   the blessed expected report
```

The agent reads `SKILL.md` first and pulls in a reference only when it reaches that phase, so context stays small on simple jobs.

## Using the scripts directly

Profile anything before touching it:

```bash
python scripts/profile_files.py ledger.xlsx statement.pdf balances.csv
```

Reconcile once you have a datamap (shape documented at the top of the script):

```bash
python scripts/reconcile.py datamap.json --out runs/run-001 --materiality 0.01
```

Writes `breaks.csv`, `residual.csv` and `metrics.json`, and warns when attribution is below 95%, when consecutive duplicate rows appear, or when the sign convention is not clearly established.

Replay the decision log so results and reasons stay in lockstep:

```bash
python scripts/decisions.py validate decisions.jsonl
python scripts/reconcile.py datamap.json --out runs/run-002 --decisions decisions.jsonl
```

Match items for a key whose balance breaks — this is what finds lump payments settling several invoices:

```bash
python scripts/match_items.py open_items.csv statement.csv \
    --amount value --ref doc --date posted_on --out runs/run-002
```

Generate the report in the user's language:

```bash
python scripts/make_report.py runs/run-002 --decisions decisions.jsonl \
    --lang pt --entity "ACME Ltda" --period 2026-01 --out report.md
```

Verify the whole toolchain at any time:

```bash
python scripts/selftest.py
# PASSED · control clean, all five faults detected, replay and report OK
```

## Design decisions worth knowing

**The sign convention is solved, never assumed.** The engine tests `closing = opening + movements` against `closing = opening − movements` and adopts whichever reconciles more accounts, reporting both counts as evidence. Column names lie about this constantly.

**Generic key extraction is tried first.** Account keys are often embedded in description text, which tempts you into writing bespoke regex immediately. Skipping the plain case — key at the head of the field — is a genuine and expensive mistake; it was caught here only by testing against an unfamiliar chart of accounts.

**Duplicates are never removed automatically.** Repeated rows may be legitimate instalments or may be page-break artifacts of a printed source, and the two are indistinguishable from the data alone. The skill quantifies the amount, marks it LOW confidence, keeps it out of the "explained" total and asks.

**Net and gross are always reported separately.** They answer different questions — how much money is unexplained versus how much activity is misposted. A reconciliation can have a trivial net gap and a large gross one, and reporting only the net hides real control failures.

**Parent-level rollup separates misposting from missing money.** Offsetting sibling sub-accounts collapse to zero at the parent. The difference between leaf-level and parent-level totals is one of the most useful numbers in the report.

## Verification

Two independent suites, and they check different things.

**Golden-file regression** (`tests/`) pins exact expected output. Each fixture
commits its source files alongside a blessed `expected/` report; the runner
regenerates and reports the precise figure that moved.

```bash
python tests/run_tests.py       # check every fixture
pytest tests/ -v               # same, with per-fixture reporting
```

Six fixtures cover: a clean ledger that must reconcile 100% with **zero**
findings; five injected defects that must all surface; decision-log replay
including a superseded decision; scope mismatch and page-break duplication;
item matching with a lump payment settling three invoices; and the masked
profiler. Full detail in [`tests/README.md`](tests/README.md).

Alongside the goldens, each fixture declares **behavioural contracts** — what
it exists to prove. These are checked even during `--update`, so re-blessing
cannot silently erase the contract a fixture was written to defend.

**The skill's bundled self-test** ships inside the skill, so anyone who
installs it can verify their install with no repo checkout:

```bash
python statement-reconciliation/scripts/selftest.py
# PASSED · control clean, all five faults detected, replay and report OK
```

Writing these suites has repeatedly paid for itself. They caught unquoted
comma-decimals corrupting a CSV, decision keys silently matching nothing
because they were not canonicalised, duplicate detection defeated by a
differing row id, and — on a ledger that reconciled perfectly to zero — a
false-positive page-break warning. That last one produced a real improvement:
duplicate detection is now gated on break status, because **if an account ties
exactly, a repeated row cannot be a spurious extra posting**, so the rows are
legitimate instalments. It resolves the duplicate-vs-instalment ambiguity in
the common case; where the account does break, the ambiguity genuinely remains
and the user is asked.

### Changing behaviour deliberately

```bash
python tests/run_tests.py            # read the diff
python tests/run_tests.py --update   # then bless it
git diff tests/fixtures              # review before committing
```

Never run `--update` before reading the diff: it converts a regression into the
new expected truth, silently.

## Limitations

Single-currency by default; FX translation is in the taxonomy but the engine does not revalue. `make_report.py` has translated headings for `en`/`pt`/`es` and falls back to English elsewhere, which the agent should then translate — the narrative is written by the agent in the user's language regardless. Subset-sum matching is bounded by a node cap and a maximum subset size, so very large many-to-many settlements may not resolve; raise `--max-subset` and `--node-cap` deliberately. Duplicate detection deliberately does **not** act — it reports and asks, because legitimate instalments and page-break artifacts are indistinguishable in the data. PDF extraction quality varies wildly; when it is poor the skill says so rather than producing a confident wrong answer.
