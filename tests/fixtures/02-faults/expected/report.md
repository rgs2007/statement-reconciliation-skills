# Reconciliation report

**Entity:** ACME INDUSTRIA LTDA  
**Period:** 2026-09  
**Generated:** <TIMESTAMP>  
**Materiality:** 0.01  

## Scope and sources

| File | role | Rows | sum | SHA-256 |
|---|---|---:|---:|---|
| `sources/opening.csv` | opening | 12 | -397,602.38 | `725be77fd44f1530…` |
| `sources/closing.csv` | closing | 12 | -428,732.12 | `0a3d8ebb29b03efc…` |
| `sources/movements.csv` | movements | 37 | 1,955,546.78 | `177d8c4f0e4b4568…` |

- equation: `closing = opening + movements`
- convention evidence: {"reconciled_with_plus": 7, "reconciled_with_minus": 1, "keys_tested": 12}

## Result

- **Reconciled:** 7 / 12 (58.3%)
- **Gross open gap:** 1,991,939.95
- **Net open gap:** -1,974,330.85
- **Explained (HIGH):** 1,946,538.87
- **Probable (MEDIUM):** 45,401.08
- **Unresolved / suspect (LOW):** 0.00

- attribution rate: 97.3% (1 unattributed of 37)
- parent-level gross gap: 1,990,344.19 (vs 1,991,939.95 at leaf level - the difference is misposting rather than missing value)

## Findings

| Category | Confidence | # | Amount (gross) | (net) |
|---|---|---:|---:|---:|
| `DECIMAL_SHIFT` | `HIGH` | 1 | 1,944,943.11 | -1,944,943.11 |
| `DUPLICATE_POSTING` | `MEDIUM` | 1 | 37,394.41 | -37,394.41 |
| `MISSING_MOVEMENTS` | `MEDIUM` | 1 | 8,006.67 | 8,006.67 |
| `SUBACCOUNT_MISATTRIBUTION` | `HIGH` | 2 | 1,595.76 | 0.00 |

### `DECIMAL_SHIFT` · `HIGH` · 1,944,943.11

- **Evidence:** 1 account(s); largest: `6652-4` -1,944,943.11
- **Rationale:** _TO BE WRITTEN BY THE AGENT_
- **Alternatives considered:** _TO BE WRITTEN BY THE AGENT_
- **Remediation:** _TO BE WRITTEN BY THE AGENT_

### `DUPLICATE_POSTING` · `MEDIUM` · 37,394.41

- **Evidence:** 1 account(s); largest: `8241-1` -37,394.41
- **Rationale:** _TO BE WRITTEN BY THE AGENT_
- **Alternatives considered:** _TO BE WRITTEN BY THE AGENT_
- **Remediation:** _TO BE WRITTEN BY THE AGENT_
- **To raise confidence:** _TO BE WRITTEN BY THE AGENT_

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

- **Amount at stake: 12,345.67** — 1 transaction(s) could not be attributed to an account (gross 12,345.67, net 12,345.67). Confirm the mapping for the largest, or supply an extraction rule covering the cluster.

## Decisions applied

_None recorded._

## Method and limitations

- sign convention established empirically: `closing = opening + movements` ({"reconciled_with_plus": 7, "reconciled_with_minus": 1, "keys_tested": 12})
- extraction rule coverage: {"S0": 36, "UNATTRIBUTED": 1}
- accounts excluded from scope: 0 (see decisions above for authority)
- decisions replayed this run: 0

_TO BE WRITTEN BY THE AGENT: what this reconciliation does not cover._

## Glossary

- `DECIMAL_SHIFT` — decimal point misplaced by a power of ten
- `DUPLICATE_POSTING` — same transaction recorded more than once
- `HIGH` — arithmetically proven; no other explanation fits
- `LOW` — suggestive only; unresolved pending evidence
- `MEDIUM` — strong signature, but alternatives survive
- `MISSING_MOVEMENTS` — balances differ but no transactions explain the change
- `SUBACCOUNT_MISATTRIBUTION` — posted to a sibling of the correct account
