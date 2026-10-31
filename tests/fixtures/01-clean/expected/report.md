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
| `sources/movements.csv` | movements | 36 | -31,129.74 | `ce00cf899caa2751…` |

- equation: `closing = opening + movements`
- convention evidence: {"reconciled_with_plus": 12, "reconciled_with_minus": 1, "keys_tested": 12}

## Result

- **Reconciled:** 12 / 12 (100.0%)
- **Gross open gap:** 0.00
- **Net open gap:** 0.00
- **Explained (HIGH):** 0.00
- **Probable (MEDIUM):** 0.00
- **Unresolved / suspect (LOW):** 0.00

- attribution rate: 100.0% (0 unattributed of 36)
- parent-level gross gap: 0.00 (vs 0.00 at leaf level - the difference is misposting rather than missing value)

## Findings

_None recorded._

## Open questions

_None recorded._

## Decisions applied

_None recorded._

## Method and limitations

- sign convention established empirically: `closing = opening + movements` ({"reconciled_with_plus": 12, "reconciled_with_minus": 1, "keys_tested": 12})
- extraction rule coverage: {"S0": 36}
- accounts excluded from scope: 0 (see decisions above for authority)
- decisions replayed this run: 0

_TO BE WRITTEN BY THE AGENT: what this reconciliation does not cover._

## Glossary

- `HIGH` — arithmetically proven; no other explanation fits
- `LOW` — suggestive only; unresolved pending evidence
- `MEDIUM` — strong signature, but alternatives survive
