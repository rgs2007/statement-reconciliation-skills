# Reconciliation report — reviewed reference

> **This file is documentation, not a test target.** `report.md` next to it is
> the machine-generated skeleton the regression test compares against, and it
> deliberately leaves `rationale`, `alternatives considered` and `remediation`
> as placeholders. This file is the *same report with the narrative written*,
> showing the standard an agent's finished output should meet.
>
> Figures here are copied from the blessed `metrics.json` and `breaks.csv` —
> never retyped from memory. The narrative is written in English here; an agent
> writes it in whatever language the user is using, while the category and
> confidence codes stay in English (see `references/reporting.md`).

**Entity:** ACME INDUSTRIA LTDA
**Period:** 2026-09
**Materiality:** 0.01

## Scope and sources

| File | Role | Rows | Sum | SHA-256 |
|---|---|---:|---:|---|
| `sources/opening.csv` | opening | 12 | -397,602.38 | `725be77fd44f1530…` |
| `sources/closing.csv` | closing | 12 | -428,732.12 | `0a3d8ebb29b03efc…` |
| `sources/movements.csv` | movements | 37 | 1,955,546.78 | `177d8c4f0e4b4568…` |

Equation tested: `closing = opening + movements`. The convention was established
empirically, not assumed: addition reconciled 7 accounts against 1 for
subtraction across 12 shared keys.

## Result

| Measure | Value |
|---|---:|
| Reconciled | 7 / 12 (58.3%) |
| Gross open gap | 1,991,939.95 |
| Net open gap | -1,974,330.85 |
| Explained (`HIGH`) | 1,946,538.87 |
| Probable (`MEDIUM`) | 45,401.08 |
| Unresolved / suspect (`LOW`) | 0.00 |

Attribution rate 97.3% — 1 of 37 postings could not be assigned to an account.

Parent-level gross gap is 1,990,344.19 against 1,991,939.95 at leaf level. The
1,595.76 difference is value sitting in the wrong sub-account rather than
missing from the ledger, and it needs a reclassification rather than an
investigation.

## Findings

Ranked by gross amount, which is not the same as ranked by severity: the
largest figure here is a single mis-keyed decimal point, while the smallest is
a control weakness worth more attention than its value suggests.

### 1. `DECIMAL_SHIFT` · `HIGH` · 1,944,943.11

**Account:** `6652-4` (CUSTO FRETE) — gap -1,944,943.11

**Evidence.** The account carries opening 21,227.06 and closing 25,553.49, so
the period movement should be 4,326.43. Attributed movements total
1,949,269.54. One posting (`mv_09_0`) of 1,946,890.00 is exactly 1,000× a
plausible value of 1,946.89, and correcting it by that factor closes the
account to within materiality.

**Rationale.** The gap equals the suspect posting × 999/1000, which is the
arithmetic signature of a decimal point entered three places to the right. No
other single posting, or combination of postings, produces this gap.

**Alternatives considered.** A genuinely large freight charge was considered
and rejected: the account's entire opening balance is 21,227.06, so a single
1.9M freight posting is implausible on its face, and no corresponding credit
exists anywhere in the period. A currency-unit error (centavos keyed as reais)
would produce a factor of 100, not 1,000.

**Remediation.** Correcting journal entry reversing `mv_09_0` and re-entering
it at 1,946.89. No cash impact — the payment itself was correct; only the
ledger entry is wrong.

### 2. `DUPLICATE_POSTING` · `MEDIUM` · 37,394.41

**Account:** `8241-1` (AGGREKO ENERGIA LTDA) — gap -37,394.41

**Evidence.** Two postings carry an identical amount, description and
transaction type, differing only in row identifier (`mv_00_0` and `mv_DUP`).
The gap equals the duplicated value exactly. The two rows are not adjacent in
the file.

**Rationale.** The closing balance does not include the second posting, so one
of the two is not a real movement. Non-adjacency matters: adjacent identical
rows are usually a paginated-export artifact, whereas a repeat elsewhere in
the file is characteristic of a transaction entered twice.

**Alternatives considered.** Two legitimate payments of the same amount in one
period is possible and cannot be excluded from the data alone — which is why
this is `MEDIUM` and not `HIGH`. It is unlikely here because the closing
balance reflects only one of them: if both payments were real, the balance
would be 37,394.41 lower.

**Remediation.** Confirm against the supplier's statement, then reverse the
surplus entry. Cash impact if the payment was genuinely made twice, so check
the bank before posting the reversal.

**To raise confidence to `HIGH`:** the supplier statement or bank record for
this period. One document settles it.

### 3. `MISSING_MOVEMENTS` · `MEDIUM` · 8,006.67

**Account:** `8722-1` (SANDRA JULIANA PEREIRA) — gap 8,006.67

**Evidence.** Opening 42,539.68, closing 50,546.35, zero attributed movements.
The gap equals the entire opening-to-closing delta.

**Rationale.** The balance demonstrably changed, so transactions exist; none
reached this reconciliation. The most likely cause is that the movement
extract was filtered or truncated, rather than that the balance moved without
any posting.

**Alternatives considered.** Incomplete attribution rather than missing data —
the postings might be present but unrecognised. This was tested and rejected:
the single unattributed row in the period is 12,345.67, which does not
reconcile this account, and no other residual exists. Direct-to-balance
posting also remains possible and would not appear in any transaction extract.

**Remediation.** Re-request the transaction listing for this account for the
period, confirming the export filter. Until the postings are obtained the
8,006.67 stays unexplained.

**To raise confidence to `HIGH`:** a complete movement extract for this
account, or confirmation from the source system that no postings exist.

### 4. `SUBACCOUNT_MISATTRIBUTION` · `HIGH` · 1,595.76 gross / 0.00 net

**Accounts:** `4363-1` (ECOLAB QUIMICA) +797.88 and `4363-2` (ECOLAB SERVICOS)
-797.88

**Evidence.** The two gaps offset to exactly zero. Both accounts share parent
`4363`. One posting of 797.88 intended for `-02` was recorded against `-01`.

**Rationale.** Exact offset between siblings under one parent is conclusive:
the money is in the ledger, in the wrong place. The parent-level rollup for
`4363` nets to zero, which independently confirms it.

**Alternatives considered.** Coincidental equal-and-opposite errors in two
related accounts would be an extraordinary coincidence at this precision, and
the shared parent makes a keying slip the ordinary explanation.

**Remediation.** Reclassification entry moving 797.88 from `4363-1` to
`4363-2`. **No cash impact and no effect on the financial statements at parent
level** — this is a presentational correction. Report it so the control
weakness is visible, but it does not change reported totals.

## Open questions

Sorted by the amount each answer would resolve.

1. **12,345.67** — One posting, `mv_ORPHAN` ("AJUSTE DIVERSOS SEM CONTA"),
   carries no derivable account. The closest name match is `5690-01`
   (TRANSPORTES UNIAO SA) at a weak similarity score, which is not strong
   enough to act on. *Which account does this adjustment belong to?* If it is
   part of a recurring pattern rather than a one-off, an extraction rule would
   be better than a single mapping.

2. **37,394.41** — Is the repeated AGGREKO posting a double entry, or two
   genuine payments of the same amount? The bank record for the period
   settles it.

3. **8,006.67** — Was the movement extract for `8722-1` filtered, or were
   these postings made directly to the balance?

## Decisions applied

No decisions were recorded for this run — it is the baseline. Every judgement
call above is still an open question rather than a settled position, which is
why nothing here is recorded as explained on a user's authority.

See fixture `03-decisions` for the same data after decisions have been taken
and replayed: an exclusion, a manual attribution, a classification, and a
superseded tolerance.

## Method and limitations

- Sign convention established empirically (7 against 1 across 12 shared keys),
  not inferred from column names.
- One extraction rule, `S0` (key at the head of the description), attributed
  36 of 37 postings. No client-specific pattern was needed.
- Reversal pair detected: 8,800.00 gross across 2 rows on `5690-01`, netting
  to zero. Reported as activity, not as a gap — no action required.
- No accounts were excluded from scope.

**What this reconciliation does not cover.** Only account-level balances were
tested; no item-level matching was performed, because the fixture carries no
open-item detail. It is single-currency, so no translation differences were
assessed. Postings are matched to accounts, not to source documents, so a
posting attributed to the right account but the wrong document would
reconcile here and still be wrong.

## Glossary

| Code | Meaning |
|---|---|
| `DECIMAL_SHIFT` | decimal point misplaced by a power of ten |
| `DUPLICATE_POSTING` | same transaction recorded more than once |
| `MISSING_MOVEMENTS` | balances differ but no transactions explain the change |
| `SUBACCOUNT_MISATTRIBUTION` | posted to a sibling of the correct account |
| `HIGH` | arithmetically proven; no other explanation fits |
| `MEDIUM` | strong signature, but alternatives survive |
| `LOW` | suggestive only; unresolved pending evidence |
