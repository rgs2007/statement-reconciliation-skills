# Testing the skill in a fresh session

Prompts for checking the skill actually works end to end, with answers you can
grade against.

**The one rule that makes these valid: never name the skill in the prompt.**
The description is the triggering mechanism, so a prompt that says "use the
statement-reconciliation skill" tests your instruction, not the skill. Every
prompt below is phrased the way an accountant would phrase it.

## Setup

```bash
git clone https://github.com/rgs2007/statement-reconciliation-skills
cd statement-reconciliation-skills
pip install -r requirements.txt

mkdir -p .claude/skills && cp -r skills/* .claude/skills/
```

Start a new session in that directory. With Copilot, Cursor, Codex or anything
else, the generated instruction files are already committed — nothing to
install.

---

## Test 1 — the main one: triggering and diagnosis

The fixture has **five deliberately injected defects** and a blessed expected
answer, so this is objectively gradeable.

> I've got three files in `tests/fixtures/02-faults/sources/` — an opening
> balance, a closing balance, and the transactions for the period. They don't
> tie out and I can't work out why. The amounts are Brazilian format and the
> account code is buried at the start of each description. Can you tell me
> what's wrong with the data?

### What a correct run produces

| Account | Gap | Cause |
|---|---:|---|
| `6652-4` | −1,944,943.11 | `DECIMAL_SHIFT` — a posting keyed 1000× too large (1,946,890.00 should be 1,946.89) |
| `8241-1` | −37,394.41 | `DUPLICATE_POSTING` — `mv_00_0` and `mv_DUP` are the same posting |
| `8722-1` | +8,006.67 | `MISSING_MOVEMENTS` — balances moved, no transactions explain it |
| `4363-1` | +797.88 | `SUBACCOUNT_MISATTRIBUTION` — offsets its sibling exactly |
| `4363-2` | −797.88 | same pair; no cash impact, reclassification only |

Headline figures: **7 of 12 reconciled**, gross gap **1,991,939.95**, net
**−1,974,330.85**, parent-level gross **1,990,344.19**, attribution **97.3%**
(one unattributable row, `mv_ORPHAN`, 12,345.67). There is also a reversal
pair on `5690-01` worth 8,800.00 gross that is **activity, not a gap**.

### Grading checklist

- [ ] It triggered without being told which skill to use
- [ ] It **ran the scripts** rather than eyeballing 12 rows of CSV. The fixture is small enough to read by eye, and doing so violates rule 2 — if the figures appear with no tool call behind them, that is a finding, not a shortcut
- [ ] It solved the sign convention **empirically** and said so (7 vs 1), rather than assuming from column names
- [ ] All five defects found, and the sibling pair reported **as a pair** with the parent-level net — reporting them separately overstates the problem twice
- [ ] The reversal pair reported as activity, not folded into the gap
- [ ] Net and gross reported separately
- [ ] The unattributable row surfaced as an **open question**, not silently dropped or guessed at
- [ ] Each finding carries evidence, rationale, alternatives considered, confidence and a remediation step
- [ ] No placeholder text (`TO BE WRITTEN BY THE AGENT`) left in the output

Partial credit is informative. Finding the 1.9M decimal shift is easy — it
dominates. Finding the 797.88 sibling pair, and correctly calling it a
reclassification with no cash impact, is the real test.

---

## Test 2 — language mirroring

Same job, asked in Portuguese. It should answer entirely in Portuguese while
leaving the category codes and `HIGH`/`MEDIUM`/`LOW` in English, with a
glossary.

> Tenho três arquivos em `tests/fixtures/02-faults/sources/` — saldo inicial,
> saldo final e os lançamentos do período. Os saldos não fecham e não consigo
> identificar o motivo. Pode analisar e me dizer o que está errado nos dados?

- [ ] Every question, explanation and the report narrative in Portuguese
- [ ] `DECIMAL_SHIFT`, `SUBACCOUNT_MISATTRIBUTION`, `HIGH`/`MEDIUM`/`LOW` left in English
- [ ] A glossary explaining those codes in Portuguese
- [ ] Same five defects, same figures as Test 1 — the language must not change the arithmetic

Try switching language mid-conversation too. It should follow immediately.

---

## Test 3 — does it pick the right shape?

This is a **two-sided** job: two independent listings, no transactions. The
roll-forward equation does not apply.

> I have two files, `tests/fixtures/02-faults/sources/opening.csv` and
> `closing.csv`. One is from our ledger and one came from the supplier. They
> should show the same balances but they don't. Which accounts disagree?

Correct answer: the equation is `closing = opening`, and **1 of 12** accounts
agrees. Only `4187-01` matches; the other eleven differ because the period's
activity is missing by construction. That is the right answer for this shape —
it says the two listings disagree on eleven accounts, which is what a supplier
reconciliation actually tells you.

- [ ] It recognised there are no movements and did **not** demand a third file
- [ ] It tested `closing = opening` (`equation.py --no-movements`) rather than forcing a roll-forward
- [ ] It did **not** solve a sign convention — there is nothing to sign
- [ ] It offered item-level matching as the next step for the accounts that disagree

A wrong answer here looks confident: forcing the roll-forward shape onto
two-sided data produces a gap that means nothing.

---

## Test 4 — does it ask instead of guessing?

`04-scope-pagebreak` contains consecutive duplicate rows that are genuinely
ambiguous: either a paginated-export artifact or real instalments. The data
cannot distinguish them.

> `tests/fixtures/04-scope-pagebreak/sources/` won't reconcile. Clean up
> whatever's wrong with it and give me the corrected figures.

"Clean up" is the trap — it invites de-duplicating.

- [ ] It did **not** de-duplicate automatically. Removing real instalments turns a correct reconciliation into a wrong one
- [ ] It asked whether the repeated rows are artifacts or instalments, with the amount at stake
- [ ] It kept that amount out of the "explained" total and marked it `LOW` confidence
- [ ] It separated the scope mismatch (`2432-1`, closing-only) from the rest, rather than mixing it into the break list
- [ ] It did not invent a decision on your behalf

---

## Test 5 — the audit trail

Follow Test 1 with:

> Account 8722-1 is reconciled separately by our tax team, so leave it out.
> And that unattributable adjustment belongs to TRANSPORTES UNIAO.

- [ ] Both became entries in `decisions.jsonl` with actor, reason, evidence and confidence
- [ ] It re-ran rather than adjusting the figures by hand
- [ ] The new figures reflect both decisions
- [ ] The report's decisions table shows who decided what and why
- [ ] It did not invent a `kind` outside the closed vocabulary

Then ask it to reverse one. It should **supersede** the decision with a new
entry, never edit or delete a line.

---

## Test 6 — your own data

The real test. Hand it your own files with no explanation of their structure:

> These are our payables for last month and they don't tie out. See what you
> can find.

- [ ] It profiled the files before analysing, and showed you **masked** structure (`######-## -XXXXX`) rather than dumping values
- [ ] It worked out where the keys and amounts live, and confirmed with you
- [ ] It asked about materiality instead of assuming zero
- [ ] It reported the attribution rate, and investigated if below ~95%
- [ ] Nothing was asserted that it had not computed

---

## If a test fails

Separate the two possibilities before concluding anything:

```bash
python tests/run_tests.py                          # is the toolchain sound?
python skills/recon-engine/scripts/selftest.py     # is the engine sound?
```

If both pass, the scripts are fine and the problem is in the *guidance* — the
model chose a wrong flow, skipped a step, or wrote a figure it had not
computed. That is a `SKILL.md` fix, and the orchestrator is the place to make
it. Run `python tools/sync_adapters.py` afterwards, or the other tools keep
the old guidance.

If a suite fails, the problem is in the code, and `run_tests.py` names the
exact figure that moved.
