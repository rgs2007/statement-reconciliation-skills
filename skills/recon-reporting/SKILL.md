---
name: recon-reporting
description: Classify reconciliation breaks into root causes and produce an auditable report — every discrepancy with its evidence, rationale, alternatives considered, confidence level and remediation step, in the user's language. Use this skill to diagnose why accounts do not tie out (scope mismatch, missing movements, sub-account misattribution, decimal shift, duplicate postings, page-break artifacts, reversals, timing differences, FX), to rank findings by amount, or to generate the written reconciliation report an accountant acts on and an auditor reviews.
---

# Diagnosis and reporting

Name the cause of every break, grade it, and write it up so an accountant can
act and an auditor can retrace.

```bash
python scripts/make_report.py runs/run-001 \
    --decisions decisions.jsonl \
    --lang pt --entity "ACME Ltda" --period 2026-01 \
    --out report.md
```

Reads a run's `metrics.json`, `breaks.csv` and `residual.csv` plus the
decision log, and writes the report skeleton with correct figures, source
hashes, the confidence split and the decisions table.

**It deliberately leaves placeholders** for rationale, alternatives considered
and remediation. The script guarantees the arithmetic and the audit trail;
writing the reasoning from the evidence is the agent's job. Never deliver a
report with placeholders still in it.

Translated section headings exist for `en`, `pt` and `es`; any other `--lang`
falls back to English headings, which you then translate. Category codes and
confidence labels always stay in English, and the report carries a glossary.

`scripts/lib.py` is a vendored copy of the canonical core
(`recon-engine/scripts/lib.py`), so a report can be generated without the
other skills installed. Never edit it.

---

Every break gets exactly one primary category, plus optional secondary tags. Category codes stay in English; the explanation is written in the user's language.

Work down this list in order — earlier causes are usually larger and can mask later ones. Re-rank by amount once all are computed.

---

## SCOPE_MISMATCH
An account or item appears on one side only.

**Signature** · key present in closing but absent from opening and movements (or vice versa); frequently a small number of accounts carrying very large balances.
**Why it happens** · different extraction scopes, a filter applied to one export, accounts opened or closed mid-period, one side covering a different entity or date range.
**Check first** · this routinely dominates the total gap. Quantify and separate it before analysing anything else, or every other number will be distorted.
**Remediation** · re-export both sides with identical scope, or record a scope exclusion decision with justification.
**Confidence** · HIGH when the key is simply absent and control totals confirm it.

## MISSING_MOVEMENTS
Opening and closing both exist and differ, but no transactions explain the change.

**Signature** · gap equals the full opening-to-closing delta; zero or near-zero attributed movements.
**Why** · transaction extract filtered or truncated, a sub-ledger not included, postings made directly to the balance.
**Remediation** · obtain the complete transaction listing for the period.
**Confidence** · HIGH when movement count is zero; MEDIUM when some movements exist, because the true cause may be incomplete attribution rather than missing data — check the unattributed residual before concluding.

## MISSING_BALANCE_ROWS
Transactions exist for a key with no corresponding opening or closing row.

**Signature** · activity present, one balance side absent.
**Why** · zero-balance accounts suppressed in the balance report, or a key normalisation mismatch between files.
**Remediation** · confirm whether the account legitimately closed at zero, or re-export including zero balances.
**Confidence** · MEDIUM — a normalisation bug produces an identical signature. Rule that out first by checking whether a similar key exists on the other side.

## SUBACCOUNT_MISATTRIBUTION
Value posted to a sibling of the correct account.

**Signature** · two or more keys sharing a parent, with gaps that offset to approximately zero.
**Why** · data-entry or mapping error; the money is present, just in the wrong place.
**Remediation** · reclassification entry. No cash impact.
**Confidence** · HIGH when the offset is exact and the accounts share a parent; MEDIUM when approximate.
**Note** · report these as a *pair*, with the parent-level net, or the report will overstate the problem twice over.

## DECIMAL_SHIFT
A value keyed with the decimal point misplaced, typically by a factor of 10, 100 or 1000.

**Signature** · gap ≈ a transaction amount × (10ⁿ − 1); the suspect transaction's magnitude is a clean power-of-ten multiple of a plausible value, and often a later correcting entry exists.
**Remediation** · correcting journal entry.
**Confidence** · HIGH when the ratio is exact and the corrected value restores the balance; otherwise MEDIUM.

## DUPLICATE_POSTING
The same transaction recorded more than once.

**Signature** · identical amount, reference and account appearing multiple times; gap equals a multiple of the amount.
**Caution** · genuinely repeated instalments look identical. Never de-duplicate without confirmation.
**Remediation** · reverse the surplus entries.
**Confidence** · MEDIUM by default; HIGH only once the user confirms the repetition is not legitimate.

## PAGEBREAK_DUPLICATION
Rows repeated as an artifact of a paginated or printed source, not real transactions.

**Signature** · consecutive identical rows, often clustering at regular intervals corresponding to page length.
**Why this is dangerous** · it is indistinguishable by signature alone from legitimate repeated instalments, and it can be enormous. De-duplicating when the rows are real destroys a correct reconciliation; not de-duplicating when they are artifacts leaves a huge phantom gap.
**Remediation** · ask the user to compare a sample against the source document. Until answered, treat the amount as **suspect and quantified but unconfirmed**, and exclude it from the headline "explained" figure.
**Confidence** · LOW until the user confirms. Never resolve this one autonomously.

## REVERSAL_PAIR
A posting and its explicit reversal.

**Signature** · exact ± pairs on the same key and document; large gross, near-zero net.
**Remediation** · usually none — informational. Report as gross activity, not as a gap.
**Confidence** · HIGH when amounts and references match exactly.

## TIMING_DIFFERENCE / CUT_OFF
A transaction recorded in different periods on the two sides.

**Signature** · the item appears on the other side in the adjacent period; gap reverses next period.
**Remediation** · accrual or cut-off adjustment; frequently no error at all.
**Confidence** · HIGH when the matching item is located in the adjacent period; LOW when inferred only from timing proximity.

## UNATTRIBUTED
Transactions whose account could not be determined.

**Signature** · extraction rules produced no key.
**Remediation** · extend extraction rules, or map individually.
**Report** · count, net and gross, plus the largest items with candidate accounts.
**Confidence** · describes only the fact of non-attribution — HIGH — while any *proposed* mapping carries its own, usually MEDIUM or LOW.

## ITEM_LEVEL_BREAK
The balance breaks and item matching leaves a residue that fits none of the above.

Use this only as a genuine residual category, not as a default. If a large share of breaks land here, the more specific detectors are not firing — investigate that as a tooling gap and say so in the report rather than presenting it as an answer.

## FX_TRANSLATION
Multi-currency: the gap corresponds to a rate difference.

**Signature** · gap proportional to balance; consistent percentage across affected accounts.
**Remediation** · align translation rates and revaluation treatment.
**Confidence** · MEDIUM unless the implied rate matches a published rate for the date.

---

## Applying the taxonomy

- One primary cause per break, chosen by the strongest evidence, not the first that fits.
- Explicitly record the **alternatives considered and rejected**, with why. This is what makes a finding auditable rather than merely assertive.
- Test cheap deterministic signatures (exact offsets, exact ratios, exact duplicates) before reaching for judgement.
- Aggregate by category for the summary, ranked by gross amount, with confirmed and unconfirmed totals kept separate so a suspect figure never inflates the explained total.

---

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
