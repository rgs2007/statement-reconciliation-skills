---
name: recon-engine
description: Compute the arithmetic of a reconciliation — parse locale-specific amounts, derive and canonicalise account keys, solve the sign convention empirically, compute per-account gaps, and run structural detectors for offsetting sub-accounts, decimal shifts, duplicate postings and reversals. Use this skill to actually calculate why balances disagree, to run a reconciliation as composable steps whose order the caller chooses, or to replay a decision log so figures always match their recorded reasons. Every number in a reconciliation comes from here; nothing else computes a figure.
---

# Reconciliation engine

**This skill owns every figure.** The caller decides which steps run and on
what data; this code decides what each number is. Nothing outside
`scripts/lib.py` computes an amount, a key or a gap.

Two interfaces over the same arithmetic.

## One-shot: the standard roll-forward plan

```bash
python scripts/reconcile.py datamap.json --out runs/run-001 \
       [--decisions decisions.jsonl] [--materiality 0.01]
```

Writes `breaks.csv`, `residual.csv` and `metrics.json`. Warns when attribution
falls below 95%, when consecutive duplicate rows appear, or when the two sign
conventions score alike — that last one means the convention is **not**
established and something else is wrong.

Datamap shape (paths relative to the datamap file, or absolute):

```json
{
  "opening":   {"path": "working/open.csv",  "key": "account", "amount": "balance"},
  "closing":   {"path": "working/close.csv", "key": "account", "amount": "balance"},
  "movements": {"path": "working/mov.csv",   "amount": "value",
                "key_from": ["desc1", "desc2"],
                "rules": [{"name": "S0", "pattern": null}]},
  "decimal_style": "comma"
}
```

A rule with a `null` pattern is the **generic** rule: the key appears at the
head of the field. Keep it first — most ordinary exports need nothing else,
and reaching for a client-specific regex before trying it is a classic and
expensive mistake.

## Composable: steps the caller sequences

Use the steps when the shape is non-standard (two-sided, balance-only), when
you need to inspect intermediate state, or when you want to add a detector.
Each prints JSON; read it before choosing the next step.

| Step | Produces | Requires |
|---|---|---|
| `load.py --role opening\|closing\|movements` | `side:<role>` | — |
| `decide.py --decisions L.jsonl` | `decisions`, rewrites the sides | any side |
| `aggregate.py` | `keys` | any side |
| `convention.py` | `convention` | `keys` |
| `equation.py [--no-movements]` | `equation` | `keys`, `convention` |
| `detect_siblings.py` | signal, priority 10 | `equation` |
| `detect_decimal_shift.py` | signal, priority 20 | `equation`, `side:movements` |
| `detect_duplicates.py` | signal, priority 30/35 | `equation`, `side:movements` |
| `detect_reversals.py` | signal, priority 60 | `side:movements` only |
| `resolve_signals.py` | `signals` | `equation` |
| `residual.py` | `residual` | `side:movements` |
| `summarize.py --out DIR` | `metrics` | `equation` |

All state is plain CSV and JSON in the run directory, deliberately: the caller
can inspect it, a human can diff it, an auditor can read it.

### What the code enforces, so the caller cannot get it wrong quietly

**Preconditions.** Every step declares its inputs and refuses to run without
them, returning JSON with exit code 2 rather than a traceback. Running
`detect_duplicates` before `equation` is not merely premature — duplicate
detection is *gated on break status*, and without it a clean ledger reports
false duplicates. The guard makes that impossible.

**Staleness.** Each step records the sha256 of everything it consumed. If an
upstream artifact changes afterwards, downstream steps refuse to run and name
what moved. That catches the subtle failure: a detector reading gaps computed
before a scope exclusion was applied.

**Declared precedence.** Detectors never write to a shared table. Each writes
its own file with an explicit priority, and `resolve_signals` merges them, so
**detector order does not affect the result**. Run them in any sequence or in
parallel. Without this, first-match-wins would make the same break get
different labels depending on an arbitrary sequencing choice.

**Coverage reporting.** `summarize` lists which detectors did not run, as
caveats in its output. A cause you did not test for is not a cause you ruled
out, and the report must say so rather than implying coverage it does not have.

### Two-sided jobs

With no movements the equation collapses to `closing = opening`:

```bash
load.py --run r1 --role left  --path ledger.csv    --amount saldo --key-from account
load.py --run r1 --role right --path statement.csv --amount saldo --key-from account
aggregate.py --run r1
equation.py  --run r1 --no-movements      # no convention needed
```

`left`/`right` are aliases for `opening`/`closing`. Then take the breaks to
`recon-item-matching`.

## scripts/lib.py — the canonical arithmetic

`parse_amount` (comma or dot decimals, parenthesised negatives, currency
symbols), `detect_style`, `canon` (canonical account key — returns nothing
rather than guessing, because a normaliser that guesses silently merges
unrelated accounts in an unfamiliar chart), `key_from_text` (ordered rules,
first match wins), `load_side`, and the decision-log read side
(`load`/`validate`/`resolve`) so this skill can replay a log on its own.

This file is **canonical**. The other skills carry vendored copies kept in
step by `tools/sync_lib.py`, with a CI gate. Edit this one.

## Verify the install

```bash
python scripts/selftest.py
```

A clean ledger must reconcile 100% with zero findings, then five injected
defects must all surface. Run it after changing anything here.

---

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
