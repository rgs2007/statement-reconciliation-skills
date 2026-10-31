# Phase 3 — Matching

Turn the datamap into a per-key gap. Everything downstream depends on getting this right, so verify rather than assume.

## Step 1 — Solve the sign convention empirically

Do **not** infer the sign convention from column names, account types or a textbook. Debit/credit presentation varies by system, by export and sometimes by report within the same system.

Test both candidates across all keys present on both sides:

```
A:  closing = opening + movements
B:  closing = opening − movements
```

Count how many keys reconcile within materiality under each. Adopt the winner and record it as a `convention` decision with the counts as evidence. If the two are close, something else is wrong — usually mixed conventions across sub-ledgers, or movements that are not all in scope. Stop and investigate rather than picking one.

If the sides are not opening/movements/closing but two independent listings (statement vs ledger), the equivalent step is deciding the match unit and direction — see Step 4.

## Step 2 — Attribute transactions to keys

Apply the extraction rules from discovery, in order, first match wins. Record which rule produced each attribution so it can be audited and so a bad rule can be withdrawn.

Report:
- attribution rate (attributed / total)
- rows per rule
- the unattributed residual: count, net sum, gross sum of absolute values

Net and gross both matter. A residual with a large gross but near-zero net is dominated by offsetting pairs — mechanical noise, not missing money. A residual with a large net is real unexplained value.

### The unattributed residual

This is the highest-value slice for judgement. For each unresolved row, attach the best candidate keys by fuzzy match against the account-name master built from the balance files, with scores. Present the largest by absolute value first, with candidates, and let the user confirm mappings in batches. Each confirmation becomes an `attribute` decision.

Before asking the user anything, first strip out what can be resolved mechanically:
- exact offsetting ± pairs (a posting and its reversal) — group them and report as one item
- clusters sharing a common token that a single new extraction rule would capture — propose the rule rather than dozens of individual mappings

Fixing one rule that recovers a whole cluster is worth far more than resolving rows one at a time.

## Step 3 — Compute per-key gaps

For every key present on either side:

```
gap = closing_actual − closing_expected
```

Classify: `RECONCILED` (|gap| ≤ materiality), `BREAK`, or a scope status when the key is absent from one side.

Produce:
- counts and percentage reconciled
- total absolute open gap, and total net gap
- a per-key break table sorted by |gap|

**Report net and gross separately, always.** They answer different questions: net is "how much money is unexplained", gross is "how much activity is misposted". A reconciliation can have a tiny net gap and a large gross one; reporting only the net hides real control failures.

## Step 4 — Item-level matching (when balances break)

Where a key breaks and both sides have itemised detail, attempt to match items before declaring the whole balance unexplained:

1. **Exact** match on reference/document + amount.
2. **Amount-only** match where references are missing, but only when unambiguous.
3. **Subset-sum** — one item on one side against several on the other, e.g. a lump payment settling multiple invoices. Bound the search (cap nodes and candidate set size) or it will not terminate on real data.
4. **Timing** — an item present on both sides in adjacent periods is a cut-off difference, not a loss.

Report matched, unmatched-by-side, and the residual per key. Unmatched items are the evidence for the taxonomy classification in Phase 4.

## Step 5 — Roll up

Before concluding, aggregate gaps to the parent-account level. Sibling sub-accounts that offset each other collapse to zero at the parent, revealing that the money is present but mis-posted. The difference between the leaf-level total and the parent-level total is one of the most useful numbers in the whole report: it separates *misposting* from *missing*.

Report both figures and the list of parents that net to zero.

## Guardrails

- Exclude nothing from scope without an explicit decision recorded.
- When a proposed exclusion would change the headline gap materially, show the before/after and get confirmation.
- Re-run from the decision log after every batch of answers so the numbers and the reasons never drift apart.
- Keep a per-run `metrics.json` so successive runs can be compared and progress demonstrated.
