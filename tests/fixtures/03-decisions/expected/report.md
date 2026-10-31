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
- convention evidence: {"reconciled_with_plus": 6, "reconciled_with_minus": 1, "keys_tested": 11}

## Result

- **Reconciled:** 6 / 11 (54.5%)
- **Gross open gap:** 1,996,278.95
- **Net open gap:** -1,994,683.19
- **Explained (HIGH):** 1,946,538.87
- **Probable (MEDIUM):** 37,394.41
- **Unresolved / suspect (LOW):** 12,345.67

- attribution rate: 100.0% (0 unattributed of 37)
- parent-level gross gap: 1,994,683.19 (vs 1,996,278.95 at leaf level - the difference is misposting rather than missing value)

## Findings

| Category | Confidence | # | Amount (gross) | (net) |
|---|---|---:|---:|---:|
| `DECIMAL_SHIFT` | `HIGH` | 1 | 1,944,943.11 | -1,944,943.11 |
| `DUPLICATE_POSTING` | `MEDIUM` | 1 | 37,394.41 | -37,394.41 |
| `ITEM_LEVEL_BREAK` | `LOW` | 1 | 12,345.67 | -12,345.67 |
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

### `ITEM_LEVEL_BREAK` · `LOW` · 12,345.67

- **Evidence:** 1 account(s); largest: `5690-1` -12,345.67
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

- **Amount at stake: 12,345.67** — 1 break(s) have no determined cause (gross 12,345.67). Item-level detail for these accounts would allow matching.

## Decisions applied

| id | kind | actor | conf | reason |
|---|---|---|---|---|
| d-0001 | `convention` | engine | `HIGH` | Both conventions tested across shared keys; addition reconciled every account that is not otherwise defective. |
| d-0002 | `exclude_scope` | user | `HIGH` | Conta reconciliada separadamente pela equipe fiscal; fora do escopo desta conciliacao. |
| d-0003 | `attribute` | user | `MEDIUM` | Confirmado pelo cliente: ajuste pertence a TRANSPORTES UNIAO SA conforme documento de origem. |
| d-0004 | `classify` | agent | `HIGH` | As duas subcontas irmas apresentam diferencas que se anulam exatamente: valor lancado na subconta errada. |
| ~~d-0005~~ | `tolerance` | user | `LOW` | Tentativa inicial de elevar a materialidade. |
| d-0006 | `tolerance` | user | `HIGH` | Materialidade revertida para centavos: a auditoria exige conciliacao exata nesta conta. |

5 live of 6 (1 superseded) · by actor: {'user': 3, 'agent': 1, 'engine': 1}

## Method and limitations

- sign convention established empirically: `closing = opening + movements` ({"reconciled_with_plus": 6, "reconciled_with_minus": 1, "keys_tested": 11})
- extraction rule coverage: {"S0": 36, "MANUAL": 1}
- accounts excluded from scope: 1 (see decisions above for authority)
- decisions replayed this run: 5

_TO BE WRITTEN BY THE AGENT: what this reconciliation does not cover._

## Glossary

- `DECIMAL_SHIFT` — decimal point misplaced by a power of ten
- `DUPLICATE_POSTING` — same transaction recorded more than once
- `HIGH` — arithmetically proven; no other explanation fits
- `ITEM_LEVEL_BREAK` — residual not fitting a more specific cause
- `LOW` — suggestive only; unresolved pending evidence
- `MEDIUM` — strong signature, but alternatives survive
- `SUBACCOUNT_MISATTRIBUTION` — posted to a sibling of the correct account
