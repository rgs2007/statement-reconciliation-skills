---
name: recon-decisions
description: Record, validate and replay the judgement calls behind a reconciliation, and grade each finding's confidence as HIGH, MEDIUM or LOW with the evidence that would raise it. Use this skill whenever a reconciliation decision needs recording or justifying — excluding an account from scope, mapping an unattributable transaction, setting materiality, fixing a sign convention, or classifying a break — and whenever an auditable trail is needed showing who decided what, when, why and on what evidence.
---

# Decisions and confidence

Every judgement call is appended to `decisions.jsonl` as one JSON object.
Never rewrite or delete a line; supersede it with a new one. This file plus
the source hashes is what makes a run reproducible and defensible.

```bash
python scripts/decisions.py validate decisions.jsonl   # before every run
python scripts/decisions.py show     decisions.jsonl   # effective set
python scripts/decisions.py history  decisions.jsonl   # chronological trail
python scripts/decisions.py resolve  decisions.jsonl   # effective set as JSON
python scripts/decisions.py append   decisions.jsonl \
    --actor user --kind exclude_scope \
    --statement '{"keys":["2432-01"]}' \
    --reason "Loans are maintained in treasury; out of scope here." \
    --evidence '{"balance":250000000}' --confidence HIGH
```

Required on every entry: `id`, `ts`, `actor` (`user` | `agent` | `engine`),
`kind`, `statement`, `reason`, `confidence`. Full schema and the closed list
of `kind` values: `templates/decisions.schema.json`.

**The vocabulary is closed on purpose.** If a decision does not fit one of the
allowed `kind` values, do not invent one — raise it as an open question
instead. A fixed vocabulary is what keeps the log reviewable.

Keys may be written in their natural form (`1400-01`); the engine
canonicalises them.

Replay is what ties figures to reasons: `reconcile.py --decisions
decisions.jsonl`, or the `decide` step in a sequenced run. The engine refuses
to run on an invalid log, so validate first.

`scripts/lib.py` is a vendored copy of the canonical core
(`recon-engine/scripts/lib.py`) and holds the read side — the vocabulary,
`load`, `validate` and `resolve`. This skill owns authoring. Never edit the
vendored copy; edit the canonical one and re-run `tools/sync_lib.py`.

---

Every finding carries a confidence label. The label is a claim about *evidence*, not about how plausible the story feels.

## The three levels

### HIGH — arithmetically proven
The evidence is deterministic and the explanation is the only one consistent with it.

Qualifies: an exact offsetting pair between sibling accounts; a gap equal to a transaction × exactly 1000 where correcting it closes the balance to zero; a key wholly absent from one side confirmed by control totals; an exact duplicate the user has confirmed is not a legitimate repeat.

Test: could a competent reviewer reproduce this from the same data and reach a different conclusion? If yes, it is not HIGH.

### MEDIUM — strong signature, alternatives survive
The pattern is clear and quantified, but at least one other explanation still fits.

Qualifies: a near-offsetting pair with residue; missing movements where attribution is incomplete, so the cause could be extraction rather than absent data; a fuzzy name match with a good score but no confirmation; a decimal shift whose correction leaves residue.

MEDIUM is the honest default for most findings before the user has answered anything. Do not inflate to HIGH because the story is tidy.

### LOW — pattern suggestive, unresolved
Something is visibly wrong and quantified, but the cause is genuinely undetermined.

Qualifies: consecutive duplicate rows that may be page-break artifacts or real instalments; a timing difference inferred only from proximity; any residual assigned a category by elimination rather than evidence.

LOW findings are still reported — they are often the largest amounts. They belong in the open-questions section, not in the explained total.

## Rules

**Never let confidence follow amount.** A large well-understood gap can be HIGH; a small mysterious one LOW. Size and certainty are independent.

**Downgrade on unresolved dependency.** If a finding rests on an assumption the user has not confirmed, it cannot exceed the confidence of that assumption.

**State what would raise it.** Every MEDIUM and LOW finding names the specific evidence that would settle it — a file to obtain, a sample to check, a question to answer. This turns the report into a work plan.

**Keep suspect amounts out of the explained total.** Report three figures: explained (HIGH), probable (MEDIUM), and unresolved/suspect (LOW). A single "explained %" that silently includes LOW findings is misleading.

**Re-grade after every answer.** Confidence moves as questions are answered. Record the change and its cause in the decision log rather than quietly overwriting.

## Expressing confidence to the user

Write the reasoning in the user's language; keep the label itself as the English token.

> **HIGH** — Accounts 1000-01 and 1000-02 show gaps of −7,118.55 and +7,118.55. They share a parent and offset exactly, so the value was posted to the wrong sibling. No cash impact; a reclassification corrects it.

> **LOW** — 698 consecutive duplicate rows totalling 183,600.00. This is either a page-break artifact of the printed source or genuine repeated instalments; the two are indistinguishable in the data. Checking ten of these rows against the original document would settle it. Until then this amount is excluded from the explained total.

Never present a MEDIUM as settled, and never bury a LOW because it is inconvenient — the unresolved items are usually where the real risk sits.
