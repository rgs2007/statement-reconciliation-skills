---
name: statement-reconciliation
description: Reconcile financial statements, ledgers, trial balances, bank statements, sub-ledgers or account extracts that do not tie out, and explain every discrepancy with evidence, rationale and a confidence level. Drives the user through discovery, guided file intake, matching and root-cause diagnosis, then produces an auditable report. Use this skill whenever the user mentions reconciliation, "doesn't balance", "doesn't tie out", "out of balance", a gap/variance/difference between two sets of figures, opening vs closing balances, statement vs ledger differences, month-end or year-end close, unexplained variances, or hands over ledger/balance/transaction files and asks why the numbers disagree — even if they never use the word "reconciliation".
---

# Statement Reconciliation

Find why two sets of figures disagree, prove each cause with evidence, and report it so an accountant can act on it and an auditor can follow it.

<!-- shared:core-rules -->
## Non-negotiable rules

**1. Mirror the user's language.** Detect the language of the user's message and reply in that language — every question, explanation and report narrative. Switch immediately if the user switches. Do **not** translate these, they stay stable for tooling and audit: category codes (`MISSING_MOVEMENTS`, `SCOPE_MISMATCH`, …), confidence labels (`HIGH`/`MEDIUM`/`LOW`), JSON keys, column names, account keys, file names. Everything a human reads is in their language; everything a machine reads stays in English. The report gets a short English glossary of the codes used.

**2. Never guess a number.** Every figure in the output must come from a computation actually run on the data. If something cannot be computed, say so.

**3. The user owns every judgement call.** Recording an assumption as a decision is fine. Inventing one is not. When the data is ambiguous, ask.

**4. Deterministic first, model last.** Arithmetic, regex and set logic resolve the overwhelming majority of rows. Reserve judgement for the residue that survives them.

**5. Read structure, not the corpus.** Profile files and work on samples, aggregates and residuals. Never load an entire large ledger into the conversation — it costs far more and produces worse answers than a targeted slice. See `references/discovery.md`.
<!-- /shared:core-rules -->

<!-- shared:workflow -->
## Workflow

Work in order. Do not skip ahead to a verdict — an unexplained gap is almost always several causes stacked on top of each other, and the big one hides the rest.

| Phase | Goal | Reference |
|---|---|---|
| 0 · Frame | What reconciles against what, over what period | below |
| 1 · Discover | Profile the files, locate keys and amounts | `references/discovery.md` |
| 2 · Intake | Get non-CSV sources into clean tabular form | `references/intake.md` |
| 3 · Match | Build the balance equation, attribute transactions | `references/matching.md` |
| 4 · Diagnose | Classify every break by root cause | `references/taxonomy.md` |
| 5 · Grade | Assign confidence and alternatives | `references/confidence.md` |
| 6 · Report | Auditable output | `references/reporting.md` |
<!-- /shared:workflow -->

### Phase 0 — Frame the reconciliation

Before touching data, establish and write down:

- **The two sides.** Ledger vs statement? Opening + movements vs closing? Sub-ledger vs control account? System A vs system B?
- **The period**, and whether both sides cover exactly it.
- **The unit of reconciliation** — per account, per document, per counterparty, per invoice.
- **Materiality** — what size difference is worth chasing. Ask; do not assume zero.

Ask these as a short numbered list in the user's language. If the user does not know, propose a default and let them correct it.

State the equation you intend to test, for example `closing = opening + movements` — and mark the sign convention as **unverified** until Phase 3 proves it.

## Setting up the workspace

On first use create, in the user's project folder:

```
reconciliation/
  sources/        # untouched copies or pointers to originals — never edited
  working/        # normalised CSVs produced during intake
  decisions.jsonl # append-only decision log (see templates/decisions.schema.json)
  runs/           # one folder per run: metrics.json, breaks.csv, residual.csv
  report.md       # regenerated from decisions + latest run
```

Originals are never modified. Every transformation writes a new file into `working/` and appends a decision explaining it.

<!-- shared:decision-log -->
## The decision log — how auditability actually works

Every judgement call is appended to `decisions.jsonl` as one JSON object. Never rewrite or delete a line; supersede it with a new one. This file plus the source hashes is what makes a run reproducible and defensible.

Required on every entry: `id`, `ts`, `actor` (`user` | `agent` | `engine`), `kind`, `statement`, `reason`, `evidence`, `confidence`. Full schema and the closed list of `kind` values: `templates/decisions.schema.json`.

If a proposed decision does not fit one of the allowed `kind` values, do not invent a new one — report it as an open question instead. The fixed vocabulary is what keeps the log reviewable.

Re-running replays the log from the top, so the numbers always match the stated reasons: `reconcile.py --decisions decisions.jsonl`. Validate with `decisions.py validate` before every run — the engine refuses to run on an invalid log.

Keys in decisions may be written in their natural form (`1400-01`); the engine canonicalises them.
<!-- /shared:decision-log -->

## Interviewing the user

The user can see the data; the agent mostly sees structure. That asymmetry shapes every question.

- Ask about **one thing at a time**, with the masked evidence that prompted it visible.
- Always offer a **default** and a **don't know** path.
- Prefer questions whose answer moves the most money. Sort open questions by the gap they would explain.
- Never ask what can be computed. Compute it and confirm.

Good: "Rows 4–9 repeat the same amount and reference. Are these genuinely separate instalments, or is one row duplicated by the export? This affects 183,600.00."

Bad: "Is your data clean?"

## Reporting

Produce `report.md` covering: scope and control totals, the headline gap, findings ranked by amount, and open questions. Every finding carries evidence, rationale, confidence, alternative explanations and a remediation step. Never present a single explanation as settled when another fits the same evidence. Format and section order: `references/reporting.md`.

<!-- shared:scripts -->
## Scripts

| Script | Does |
|---|---|
| `profile_files.py` | Structure and masked previews for csv/xlsx/pdf — understand a file without exposing values |
| `reconcile.py` | Engine: normalise, attribute, solve the sign convention, compute gaps, detect structural signatures, replay decisions |
| `match_items.py` | Item-level matching for a broken key: exact → amount → bounded subset-sum → timing |
| `decisions.py` | Validate, append, resolve and replay the decision log |
| `make_report.py` | Generate `report.md` skeleton with correct figures, audit trail and glossary |
| `selftest.py` | Prove the toolchain: clean ledger must reconcile 100%; five injected faults must all surface |

Typical sequence:

```bash
python scripts/profile_files.py sources/*            # phase 1
python scripts/reconcile.py datamap.json --out runs/run-001 \
       --decisions decisions.jsonl                   # phase 3
python scripts/match_items.py left.csv right.csv --amount value --ref doc \
       --out runs/run-001                            # phase 3, broken keys only
python scripts/decisions.py append decisions.jsonl --actor user --kind ... # phase 4-5
python scripts/make_report.py runs/run-001 --decisions decisions.jsonl \
       --lang <user language> --out report.md        # phase 6
```

Run `selftest.py` after changing any script. All are dependency-light (pandas; openpyxl and pdfplumber only for those formats). Run them; do not reimplement their logic inline.

**`make_report.py` leaves placeholders** for rationale, alternatives considered and remediation. The script guarantees the figures and the audit trail; writing the reasoning from the evidence is the agent's job, in the user's language. Never deliver a report with placeholders still in it.
<!-- /shared:scripts -->

<!-- shared:traps -->
## Known traps

These cost real time when they are missed. Details in the references.

- Sign convention is an **empirical question**. Test `closing = opening + movements` and `closing = opening − movements` and adopt whichever reconciles more accounts. Never assume from column names.
- Try the **plain** key extraction first (key at the head of the description), before any client-specific pattern. A generic fallback catches most ordinary exports.
- **Duplicate-looking rows may be legitimate** repeated instalments. Blanket de-duplication can make a reconciliation worse. Always ask. One discriminator is decisive: if the account ties exactly, a repeated row cannot be a spurious extra posting, so the rows are real. Where the account breaks, the ambiguity genuinely remains.
- **Scope mismatch usually dominates.** Accounts present on one side only will swamp every other cause. Quantify and separate it before analysing anything else.
- **Offsetting sibling sub-accounts** are posting errors, not missing money. Roll up to the parent to see the true residual.
- Under **pandas ≥ 3**, `.astype(str)` preserves NaN — a blank cell will hand a float to a regex. Use `.fillna("").astype(str)`.
- **Comma-decimal values must be quoted** when writing CSV, or `1.234,56` splits into two columns and every total silently changes.
- A genuine **duplicate posting usually carries a different row id**, so id-like columns must be excluded from any duplicate signature or nothing is found.
- **Canonicalise keys on both sides before comparing.** A key normaliser that guesses will silently merge unrelated accounts in an unfamiliar chart; prefer one that returns nothing over one that collides.
<!-- /shared:traps -->
