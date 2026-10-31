# Reconciliation report

**Entity:** Summit Outdoor Gear LLC (synthetic, Mindweave)  
**Period:** 2025-10  
**Generated:** <TIMESTAMP>  
**Materiality:** 0.01  

## Scope and sources

| File | role | Rows | sum | SHA-256 |
|---|---|---:|---:|---|
| `sources/opening.csv` | opening | 16 | 0.00 | `87a2c7aa620236f0…` |
| `sources/closing.csv` | closing | 16 | -0.00 | `adc937cfaf697f9c…` |
| `sources/movements.csv` | movements | 1035 | 0.00 | `53468b877eeac56e…` |

- equation: `closing = opening + movements`
- convention evidence: {"reconciled_with_plus": 14, "reconciled_with_minus": 1, "keys_tested": 16}

## Result

- **Reconciled:** 14 / 16 (87.5%)
- **Gross open gap:** 154.12
- **Net open gap:** 0.00
- **Explained (HIGH):** 0.00
- **Probable (MEDIUM):** 0.00
- **Unresolved / suspect (LOW):** 154.12

- attribution rate: 100.0% (0 unattributed of 1035)
- parent-level gross gap: 154.12 (vs 154.12 at leaf level - the difference is misposting rather than missing value)

## Findings

| Category | Confidence | # | Amount (gross) | (net) |
|---|---|---:|---:|---:|
| `ITEM_LEVEL_BREAK` | `LOW` | 2 | 154.12 | 0.00 |

### `ITEM_LEVEL_BREAK` · `LOW` · 154.12

- **Evidence:** 2 account(s); largest: `1-2010` -77.06, `6-2800` 77.06
- **Rationale:** _TO BE WRITTEN BY THE AGENT_
- **Alternatives considered:** _TO BE WRITTEN BY THE AGENT_
- **Remediation:** _TO BE WRITTEN BY THE AGENT_
- **To raise confidence:** _TO BE WRITTEN BY THE AGENT_

## Open questions

- **Amount at stake: 154.12** — 2 break(s) have no determined cause (gross 154.12). Item-level detail for these accounts would allow matching.

## Decisions applied

_None recorded._

## Method and limitations

- sign convention established empirically: `closing = opening + movements` ({"reconciled_with_plus": 14, "reconciled_with_minus": 1, "keys_tested": 16})
- extraction rule coverage: {"COLUMN": 1035}
- accounts excluded from scope: 0 (see decisions above for authority)
- decisions replayed this run: 0

_TO BE WRITTEN BY THE AGENT: what this reconciliation does not cover._

## Glossary

- `HIGH` — arithmetically proven; no other explanation fits
- `ITEM_LEVEL_BREAK` — residual not fitting a more specific cause
- `LOW` — suggestive only; unresolved pending evidence
- `MEDIUM` — strong signature, but alternatives survive
