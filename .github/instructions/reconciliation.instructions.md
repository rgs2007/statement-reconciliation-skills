---
applyTo: "**/*.csv,**/datamap.json,**/decisions.jsonl,statement-reconciliation/**,tests/**"
description: "Reconciliation method, decision-log rules and script usage"
---

<!-- GENERATED FILE — DO NOT EDIT.
     Source: statement-reconciliation/SKILL.md
     Regenerate: python tools/sync_adapters.py
     CI fails if this file is stale. -->

# Reconciliation work in this repository

These instructions apply when touching ledger data, a datamap, a decision log,
the skill itself, or its tests.

File references are not expanded in this kind of instructions file, so open
these yourself when you need them:
`statement-reconciliation/SKILL.md` for the full method, and
`statement-reconciliation/references/<phase>.md` for discovery, intake, matching, taxonomy,
confidence and reporting.

## Non-negotiable rules

**1. Mirror the user's language.** Detect the language of the user's message and reply in that language — every question, explanation and report narrative. Switch immediately if the user switches. Do **not** translate these, they stay stable for tooling and audit: category codes (`MISSING_MOVEMENTS`, `SCOPE_MISMATCH`, …), confidence labels (`HIGH`/`MEDIUM`/`LOW`), JSON keys, column names, account keys, file names. Everything a human reads is in their language; everything a machine reads stays in English. The report gets a short English glossary of the codes used.

**2. Never guess a number.** Every figure in the output must come from a computation actually run on the data. If something cannot be computed, say so.

**3. The user owns every judgement call.** Recording an assumption as a decision is fine. Inventing one is not. When the data is ambiguous, ask.

**4. Deterministic first, model last.** Arithmetic, regex and set logic resolve the overwhelming majority of rows. Reserve judgement for the residue that survives them.

**5. Read structure, not the corpus.** Profile files and work on samples, aggregates and residuals. Never load an entire large ledger into the conversation — it costs far more and produces worse answers than a targeted slice. See `statement-reconciliation/references/discovery.md`.

## Workflow

Work in order. Do not skip ahead to a verdict — an unexplained gap is almost always several causes stacked on top of each other, and the big one hides the rest.

| Phase | Goal | Reference |
|---|---|---|
| 0 · Frame | What reconciles against what, over what period | below |
| 1 · Discover | Profile the files, locate keys and amounts | `statement-reconciliation/references/discovery.md` |
| 2 · Intake | Get non-CSV sources into clean tabular form | `statement-reconciliation/references/intake.md` |
| 3 · Match | Build the balance equation, attribute transactions | `statement-reconciliation/references/matching.md` |
| 4 · Diagnose | Classify every break by root cause | `statement-reconciliation/references/taxonomy.md` |
| 5 · Grade | Assign confidence and alternatives | `statement-reconciliation/references/confidence.md` |
| 6 · Report | Auditable output | `statement-reconciliation/references/reporting.md` |

## The decision log — how auditability actually works

Every judgement call is appended to `decisions.jsonl` as one JSON object. Never rewrite or delete a line; supersede it with a new one. This file plus the source hashes is what makes a run reproducible and defensible.

Required on every entry: `id`, `ts`, `actor` (`user` | `agent` | `engine`), `kind`, `statement`, `reason`, `evidence`, `confidence`. Full schema and the closed list of `kind` values: `statement-reconciliation/templates/decisions.schema.json`.

If a proposed decision does not fit one of the allowed `kind` values, do not invent a new one — report it as an open question instead. The fixed vocabulary is what keeps the log reviewable.

Re-running replays the log from the top, so the numbers always match the stated reasons: `reconcile.py --decisions decisions.jsonl`. Validate with `decisions.py validate` before every run — the engine refuses to run on an invalid log.

Keys in decisions may be written in their natural form (`1400-01`); the engine canonicalises them.

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
python statement-reconciliation/scripts/profile_files.py sources/*            # phase 1
python statement-reconciliation/scripts/reconcile.py datamap.json --out runs/run-001 \
       --decisions decisions.jsonl                   # phase 3
python statement-reconciliation/scripts/match_items.py left.csv right.csv --amount value --ref doc \
       --out runs/run-001                            # phase 3, broken keys only
python statement-reconciliation/scripts/decisions.py append decisions.jsonl --actor user --kind ... # phase 4-5
python statement-reconciliation/scripts/make_report.py runs/run-001 --decisions decisions.jsonl \
       --lang <user language> --out report.md        # phase 6
```

Run `selftest.py` after changing any script. All are dependency-light (pandas; openpyxl and pdfplumber only for those formats). Run them; do not reimplement their logic inline.

**`make_report.py` leaves placeholders** for rationale, alternatives considered and remediation. The script guarantees the figures and the audit trail; writing the reasoning from the evidence is the agent's job, in the user's language. Never deliver a report with placeholders still in it.

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
