# Reconciliation report

**Entity:** Summit Outdoor Gear LLC (synthetic, Mindweave)  
**Period:** 2024-06  
**Generated:** <TIMESTAMP>  
**Materiality:** 0.01  

## Scope and sources

| File | role | Rows | sum | SHA-256 |
|---|---|---:|---:|---|
| `sources/opening.csv` | opening | 16 | 0.00 | `c2ef04df907fd5eb…` |
| `sources/closing.csv` | closing | 16 | -0.00 | `7323cf032cc69b56…` |
| `sources/movements.csv` | movements | 500 | 0.00 | `1770ccde403566ea…` |

- equation: `closing = opening + movements`
- convention evidence: {"reconciled_with_plus": 16, "reconciled_with_minus": 1, "keys_tested": 16}

## Result

- **Reconciled:** 16 / 16 (100.0%)
- **Gross open gap:** 0.00
- **Net open gap:** 0.00
- **Explained (HIGH):** 0.00
- **Probable (MEDIUM):** 0.00
- **Unresolved / suspect (LOW):** 0.00

- attribution rate: 100.0% (0 unattributed of 500)
- parent-level gross gap: 0.00 (vs 0.00 at leaf level - the difference is misposting rather than missing value)

## Findings

_None recorded._

## Open questions

_None recorded._

## Decisions applied

_None recorded._

## Method and limitations

- sign convention established empirically: `closing = opening + movements` ({"reconciled_with_plus": 16, "reconciled_with_minus": 1, "keys_tested": 16})
- extraction rule coverage: {"COLUMN": 500}
- accounts excluded from scope: 0 (see decisions above for authority)
- decisions replayed this run: 0

_TO BE WRITTEN BY THE AGENT: what this reconciliation does not cover._

## Glossary

- `HIGH` — arithmetically proven; no other explanation fits
- `LOW` — suggestive only; unresolved pending evidence
- `MEDIUM` — strong signature, but alternatives survive
