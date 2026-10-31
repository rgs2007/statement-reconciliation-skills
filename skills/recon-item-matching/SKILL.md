---
name: recon-item-matching
description: Match individual items between two sides of a reconciliation when a balance breaks — exact reference-and-amount matching, unambiguous amount-only matching, bounded subset-sum for one lump payment settling several invoices, and timing differences across adjacent periods. Use this skill for bank reconciliation, open-item or invoice matching, supplier-statement comparison, sub-ledger against control account, three-way match, or whenever a broken account has itemised detail on both sides and you need to know which items are genuinely unmatched.
---

# Item-level matching

When a balance does not tie, match the underlying items before declaring the
difference unexplained. Whatever survives all four passes is the genuine
residual, and the evidence for a root-cause classification.

```bash
python scripts/match_items.py LEFT.csv RIGHT.csv \
    --amount value --ref doc [--key account] [--date posted_on] \
    [--tolerance 0.01] [--max-subset 4] [--node-cap 200000] \
    [--out runs/run-001]
```

Four passes, cheapest and most certain first:

1. **EXACT** — reference *and* amount agree.
2. **AMOUNT** — amount alone, and only where it is unambiguous on both sides. A duplicated amount is left unmatched rather than paired arbitrarily.
3. **SUBSET** — one item against several, which is how a lump payment settling multiple invoices appears. Branch-and-bound with a hard node cap, because an unbounded search does not terminate on a real ledger. Raise `--max-subset` and `--node-cap` deliberately; very large many-to-many settlements may not resolve.
4. **TIMING** — the same amount present on the other side within 45 days, which is a cut-off difference rather than a loss.

Outputs `item_match.json` (passes and the surviving residual) and
`unmatched_items.csv`.

This skill is also the whole job for a **two-sided** reconciliation — bank
statement against cash book, supplier statement against the payables ledger —
where there is no opening or closing balance to roll forward. Use it directly;
no engine run is required.

`scripts/lib.py` is a vendored copy of the canonical arithmetic
(`recon-engine/scripts/lib.py`), so amount parsing here cannot disagree with
the engine's. Never edit it; edit the canonical copy and re-run
`tools/sync_lib.py`.

## Reading the result

Report matched counts per pass, unmatched by side, and the residual. Net and
gross matter separately: a large gross with a near-zero net is offsetting
noise, while a large net is real unexplained value.

An unmatched item is evidence, not a conclusion. Take it to
`recon-reporting`'s taxonomy to name the cause.
