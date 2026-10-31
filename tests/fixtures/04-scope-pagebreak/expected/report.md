# Reconciliation report

**Entity:** ACME INDUSTRIA LTDA  
**Period:** 2026-09  
**Generated:** <TIMESTAMP>  
**Materiality:** 0.01  

## Scope and sources

| File | role | Rows | sum | SHA-256 |
|---|---|---:|---:|---|
| `sources/opening.csv` | opening | 11 | -404,919.58 | `61bfcbebcc1462ff…` |
| `sources/closing.csv` | closing | 12 | -428,732.12 | `0a3d8ebb29b03efc…` |
| `sources/movements.csv` | movements | 38 | 1,964,815.06 | `7cd0bcd4883b1dbb…` |

- equation: `closing = opening + movements`
- convention evidence: {"reconciled_with_plus": 6, "reconciled_with_minus": 1, "keys_tested": 11}

## Result

- **Reconciled:** 6 / 12 (50.0%)
- **Gross open gap:** 2,009,988.87
- **Net open gap:** -1,976,281.93
- **Explained (HIGH):** 1,954,587.79
- **Probable (MEDIUM):** 8,006.67
- **Unresolved / suspect (LOW):** 47,394.41

- attribution rate: 97.37% (1 unattributed of 38)
- parent-level gross gap: 2,008,393.11 (vs 2,009,988.87 at leaf level - the difference is misposting rather than missing value)

> ⚠ 3 consecutive duplicate row(s) detected (gross 44,894.41). Classified PAGEBREAK_DUPLICATION at LOW confidence and **excluded from the explained total** until confirmed against the source document.

## Findings

| Category | Confidence | # | Amount (gross) | (net) |
|---|---|---:|---:|---:|
| `DECIMAL_SHIFT` | `HIGH` | 1 | 1,944,943.11 | -1,944,943.11 |
| `ITEM_LEVEL_BREAK` | `LOW` | 1 | 47,394.41 | -47,394.41 |
| `SCOPE_MISMATCH` | `HIGH` | 1 | 8,048.92 | 8,048.92 |
| `MISSING_MOVEMENTS` | `MEDIUM` | 1 | 8,006.67 | 8,006.67 |
| `SUBACCOUNT_MISATTRIBUTION` | `HIGH` | 2 | 1,595.76 | 0.00 |

### `DECIMAL_SHIFT` · `HIGH` · 1,944,943.11

- **Evidence:** 1 account(s); largest: `6652-4` -1,944,943.11
- **Rationale:** _TO BE WRITTEN BY THE AGENT_
- **Alternatives considered:** _TO BE WRITTEN BY THE AGENT_
- **Remediation:** _TO BE WRITTEN BY THE AGENT_

### `ITEM_LEVEL_BREAK` · `LOW` · 47,394.41

- **Evidence:** 1 account(s); largest: `8241-1` -47,394.41
- **Rationale:** _TO BE WRITTEN BY THE AGENT_
- **Alternatives considered:** _TO BE WRITTEN BY THE AGENT_
- **Remediation:** _TO BE WRITTEN BY THE AGENT_
- **To raise confidence:** _TO BE WRITTEN BY THE AGENT_

### `SCOPE_MISMATCH` · `HIGH` · 8,048.92

- **Evidence:** 1 account(s); largest: `2432-1` 8,048.92
- **Rationale:** _TO BE WRITTEN BY THE AGENT_
- **Alternatives considered:** _TO BE WRITTEN BY THE AGENT_
- **Remediation:** _TO BE WRITTEN BY THE AGENT_

### `MISSING_MOVEMENTS` · `MEDIUM` · 8,006.67

- **Evidence:** 1 account(s); largest: `8722-1` 8,006.67
- **Rationale:** _TO BE WRITTEN BY THE AGENT_
- **Alternatives considered:** _TO BE WRITTEN BY THE AGENT_
- **Remediation:** _TO BE WRITTEN BY THE AGENT_
- **To raise confidence:** _TO BE WRITTEN BY THE AGENT_

### `SUBACCOUNT_MISATTRIBUTION` · `HIGH` · 1,595.76

- **Evidence:** 2 account(s); largest: `4363-1` 797.88, `4363-2` -797.88
- **Rationale:** _TO BE WRITTEN BY THE AGENT_
- **Alternatives considered:** _TO BE WRITTEN BY THE AGENT_
- **Remediation:** _TO BE WRITTEN BY THE AGENT_

## Open questions

- **Amount at stake: 47,394.41** — 1 break(s) have no determined cause (gross 47,394.41). Item-level detail for these accounts would allow matching.
- **Amount at stake: 44,894.41** — Are the 3 consecutive duplicate row(s) page-break artifacts, or legitimate repeated instalments? Checking ten against the source document would settle it.
- **Amount at stake: 12,345.67** — 1 transaction(s) could not be attributed to an account (gross 12,345.67, net 12,345.67). Confirm the mapping for the largest, or supply an extraction rule covering the cluster.

## Decisions applied

_None recorded._

## Method and limitations

- sign convention established empirically: `closing = opening + movements` ({"reconciled_with_plus": 6, "reconciled_with_minus": 1, "keys_tested": 11})
- extraction rule coverage: {"S0": 37, "UNATTRIBUTED": 1}
- accounts excluded from scope: 0 (see decisions above for authority)
- decisions replayed this run: 0

_TO BE WRITTEN BY THE AGENT: what this reconciliation does not cover._

## Glossary

- `DECIMAL_SHIFT` — decimal point misplaced by a power of ten
- `HIGH` — arithmetically proven; no other explanation fits
- `ITEM_LEVEL_BREAK` — residual not fitting a more specific cause
- `LOW` — suggestive only; unresolved pending evidence
- `MEDIUM` — strong signature, but alternatives survive
- `MISSING_MOVEMENTS` — balances differ but no transactions explain the change
- `SCOPE_MISMATCH` — account present on one side only
- `SUBACCOUNT_MISATTRIBUTION` — posted to a sibling of the correct account
