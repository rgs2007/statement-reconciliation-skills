# Phase 1 — Discovery

Goal: learn the shape of each file, find where the account key and the amount live, and write extraction rules — without reading the whole corpus.

## Tiered exposure

Work outward from cheap to expensive. Stop as soon as the question is answered.

| Tier | What | Size | Used for |
|---|---|---|---|
| 0 | Schema + row counts + masked preview | tiny | Is this file what we think it is? |
| 1 | Stratified sample, ~200 rows/file | small | Writing extraction rules |
| 2 | Aggregates: totals, per-key sums, gap composition | small | Narrative and ranking |
| 3 | Residual: only rows that failed to resolve | medium | Judgement calls |
| ✗ | The full corpus | huge | Never |

A full ledger can be a thousand times larger than the residual that actually needs attention, and feeding it in wholesale degrades accuracy as well as cost. The residual is the part with signal.

## Masked previews

`scripts/profile_files.py` returns previews with values masked — digits become `#`, letters become `X`, punctuation is kept. This reveals the *shape* of a field without disclosing its contents.

```
row3: XXXXXXX_XX[text] | XXXXXXX_XXXXXXXXXXX[text] | XXXXX_X[text]
row4: ####[number]     | ######-## -XXXXXXX[mixed] | ####,##[number]
```

That is enough to see there is a header on row 3, an account code embedded at the start of a description, and a comma-decimal amount — all without exposing a single real figure. Use masked previews by default, especially with client data. Ask the user to confirm interpretations against what they can see.

## Stratified sampling

Random samples miss rare errors, which are exactly what matters. Sample deliberately:

1. **Stratify** by the most categorical column — transaction type, source system, document kind. If no such column exists, synthesise one from the leading token of the widest text column; ledger exports often bury the transaction type inside the description.
2. **Oversample extremes** — the largest absolute amounts.
3. **Include failures** — rows where the amount will not parse, or the key will not extract.

Pick the stratifier by coverage *and* variety: a column whose leading tokens are mostly blank is a bad stratifier even if it has many distinct values.

## Locating the account key

Try in this order and stop at the first that works. **Always try the generic case first** — skipping it and jumping to bespoke patterns is a classic and expensive mistake.

1. **Dedicated column.** The key is its own field. Easiest and most common in modern exports.
2. **Head of the description.** `001000-01 -BANK ACCOUNT` → key `1000-01`. Covers most ordinary ledger dumps.
3. **Embedded elsewhere in a text field.** Legacy and printed-report exports hide the key inside a longer string — after a document number, a payroll prefix, a date block. Derive one narrow regex per observed pattern and name each one (`S1`, `S2`, …) so attribution can be traced back to the rule that produced it.
4. **Named/textual accounts.** Some rows key on a word rather than a number (a tax authority, a clearing account). Map these explicitly.
5. **Unresolvable.** Leave unattributed. Do not force a match.

Record the coverage of each rule. If a rule attributes very few rows, question whether it is real or coincidence. Report overall attribution rate; below ~95% on a clean ledger usually means a pattern is still missing.

### Canonical keys

Normalise keys to one canonical form before comparing across files (pad or strip leading zeros, standardise the separator, decide how sub-accounts are represented). Beware collapsing distinct accounts: a rule tuned to one chart of accounts can silently merge unrelated accounts in another. Prefer a normaliser that **fails loudly** (returns nothing) over one that guesses and collides.

After normalising, verify: the number of distinct keys per file should be plausible against the user's expectation of how many accounts exist.

## Parsing amounts

Decimal and thousands separators vary by locale — `1.234,56` and `1,234.56` are the same number. Infer from the data, confirm with the user, and record the convention as a decision. Watch for parentheses for negatives, trailing minus signs, and currency symbols.

Always compute and store **control totals** (row count, sum, sum of absolute values, sha256) per source file. Restate them in the report. If a control total changes between runs, the input changed — say so loudly.

## Output of this phase

A datamap the user has confirmed:

- per file: role, key location and extraction rules, amount column, amount format, row count, sha256
- the reconciliation equation to be tested
- open questions that blocked anything

Append each confirmed element to `decisions.jsonl` as a `datamap` decision.
