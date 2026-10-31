# Phase 2 — Guided intake

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
