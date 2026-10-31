# Phase 6 — Reporting

The report must let an accountant act and an auditor retrace. Write all narrative in the user's language; keep category codes, confidence labels, account keys and file names unchanged.

Write to `report.md`, regenerated from `decisions.jsonl` plus the latest run. Never hand-edit it — if something is wrong, fix the decision and re-run, so the numbers and the reasons can never disagree.

## Structure

### 1. Header
Period, entity, the two sides reconciled, run timestamp, materiality threshold, and the source files with row counts and sha256. If a hash differs from the previous run, flag it prominently — the inputs changed.

### 2. Result
- Accounts/items reconciled, as count and percentage
- Total gross open gap and total net gap, stated separately
- The three-way split: **explained** (HIGH), **probable** (MEDIUM), **unresolved or suspect** (LOW)
- Movement from the previous run, if any

Never quote a single "explained %" that folds LOW findings into it.

### 3. Findings
Ranked by gross amount, not by confidence. Each finding:

- **Category** (English code) and a one-line description in the user's language
- **Amount** — gross and net
- **Scope** — which accounts or items, with counts; list the largest few, not all
- **Evidence** — the concrete figures and rows the conclusion rests on
- **Rationale** — why this cause, in plain language
- **Alternatives considered** — what else fits, and why it was rejected
- **Confidence** — HIGH/MEDIUM/LOW
- **Remediation** — the specific action, and whether it has cash impact or is presentational
- **To raise confidence** — for MEDIUM and LOW, the evidence that would settle it

### 4. Open questions
Sorted by the amount each would resolve. Each states the question, the amount at stake, what the agent already checked, and the options. This is the user's work queue.

### 5. Decisions applied
Every decision from the log that affected these numbers: what, who (`user`/`agent`/`engine`), when, why, and the evidence. This is the audit trail — the reader can see precisely which human judgements shaped the result.

### 6. Method and limitations
The equation tested and how the sign convention was established; extraction rules and their coverage; attribution rate; what was excluded from scope and on whose authority; and what this reconciliation does **not** cover. State limitations plainly — a report that hides its own gaps is worse than useless in an audit.

### 7. Glossary
The English category and confidence codes used, with a one-line translation in the user's language.

## Tone

Factual, specific, quantified. No hedging adjectives where a number belongs. Do not editorialise about data quality; describe what was found and what it implies.

If the reconciliation is largely unexplained, say so directly and lead with what is needed to progress. A confident-sounding report over a mostly unexplained gap is the worst possible output.

## Companion files

Alongside `report.md`, write into the run folder:
- `breaks.csv` — every unreconciled key with gap, category, confidence
- `residual.csv` — unattributed items with candidates and scores
- `metrics.json` — the headline numbers, for run-over-run comparison

These let the user work in a spreadsheet without re-deriving anything, and let successive runs be diffed.
