---
name: recon-discovery
description: Profile and prepare financial source files before reconciling them — report a file's structure with values masked, locate where account keys and amounts live, write extraction rules, and convert Excel or PDF sources into clean tabular form. Use this skill whenever ledger, balance, trial-balance, statement or transaction files need understanding or cleaning up before analysis, when a spreadsheet has title banners, merged cells or a header part-way down, when a PDF table needs extracting, or when you need to see the shape of a file without exposing confidential figures.
---

# Reconciliation discovery and intake

Learn the shape of each source file and get it into clean tabular form —
without reading the whole corpus, and without exposing values.

`scripts/profile_files.py` reports structure with values **masked**: digits
become `#`, letters `X`, punctuation kept. That reveals a header row, an
embedded account key or a comma-decimal amount without disclosing a single
real figure. Use it by default on client data, and ask the user to confirm
interpretations against what they can see.

```bash
python scripts/profile_files.py sources/*              # masked, human-readable
python scripts/profile_files.py sources/* --json       # machine-readable
python scripts/profile_files.py f.xlsx --unmasked      # only with consent
```

Requires `pandas`; `openpyxl` for .xlsx and `pdfplumber` for .pdf.

`scripts/lib.py` is a vendored copy of the canonical arithmetic
(`recon-engine/scripts/lib.py`) so this skill works installed on its own.
Never edit it — edit the canonical copy and re-run `tools/sync_lib.py`.

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

---

Reconciliation runs on clean tabular data. Users arrive with spreadsheets, printed-report PDFs and exports with title banners, merged cells and totals rows in the middle. This phase converts them — with the user making every structural decision, because the agent works from masked structure while the user can see the actual file.

Skip this phase entirely if the sources are already clean CSVs.

## Principle

The algorithm reads structure and proposes; the user confirms or corrects; the algorithm writes a new file. Never edit the original. Every conversion produces a file in `working/` and an `ingest` decision recording exactly what was chosen.

Because the agent cannot see values, it must not silently infer. It may *propose* — "the header looks like it is on row 4" — but the user confirms before conversion.

## Excel

Run `scripts/profile_files.py` to get sheet names, dimensions, a masked preview and a header-row guess. Then ask, one at a time:

1. **Which sheet** holds the data? (list the sheets with their dimensions)
2. **Which row** is the header? (show the masked preview with row numbers; state the guess)
3. **Where does the data start and end?** Watch for totals rows, subtotal blocks and blank separator rows.
4. **Which columns** matter, and what is each one? Map to roles: key, description, amount, date, document reference.
5. **Any computed column?** Sometimes the amount is a difference or sum of two columns rather than a single field.
6. **Merged or repeated header cells?** Common in exports; they produce blank keys that must be forward-filled.

Then convert: read with no header, slice from the confirmed header row, select and rename columns, drop fully blank rows, write to `working/`.

Report back the row count and column names of what was written, and ask the user to sanity-check the count against what they expect. A count that is wildly off usually means a totals block was included or the data range was wrong.

## PDF

Printed reports are the hardest input and the most error-prone. Extract tables per page and show the user how many tables were found and their masked shape.

Ask which page and which table index to use, and whether the table repeats across pages with a header on each.

Specific hazards:

- **Page-break artifacts.** A row may be repeated at a page boundary. This is one of the most consequential ambiguities in reconciliation — see the taxonomy entry `PAGEBREAK_DUPLICATION`. Never de-duplicate automatically.
- **Wrapped rows.** A long description can spill onto a second line and be read as a separate row with a blank amount.
- **Column drift.** Table extraction can shift columns when a cell is empty. Verify by checking that the amount column parses as numeric for nearly every row; a sudden cluster of parse failures means drift.
- **Totals and subtotals** printed inline will be read as data and will double-count. Identify and exclude them explicitly.

If extraction quality is poor, say so plainly and recommend obtaining a CSV/Excel export from the source system instead. A bad PDF extraction produces a confident and completely wrong reconciliation.

## CSV and text

Confirm delimiter, encoding, quoting, and whether there are preamble lines before the header. Check for a trailing totals row.

## After every conversion

Compute control totals on the produced file and show them. Ask the user to confirm the total matches the source document's stated total, if it has one. This single check catches most intake errors before they contaminate the analysis.

Append an `ingest` decision recording: source file and sha256, sheet/page, header row, data range, column mapping, any computed column, output path, resulting row count and sum.
