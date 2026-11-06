# The interview protocol

How to behave like an accountant working with a client: clarify what is
genuinely unclear, assume what is conventional, and never be slower than the
accountant would have been alone.

That last constraint is the hard one. A reconciliation has dozens of small
uncertainties. An accountant resolves almost all of them silently, from
convention and from the data, and saves the client two or three real
questions. Asking all dozen is not thoroughness — it is offloading your job
onto the client, and it costs more time than doing the reconciliation by hand.

## The shape of it

**Phase A — silent recon. No questions at all.**

Before asking anything, profile the files and run the engine with inferred
defaults. This costs seconds and it is what makes the questions worth asking:
most of what you would have asked is answered for free.

The data settles, with no client involvement: the decimal convention, where
the account key lives, the sign convention (solved empirically, with the
counts as evidence), which accounts reconcile, which break and by how much,
and which breaks have an arithmetically conclusive cause.

A first pass that is cheap and reversible is the protection against going far
on a wrong assumption. Everything in Phase A is recomputable, so a corrected
assumption costs one re-run, not a re-analysis.

**Phase B — one checkpoint. Everything at once.**

Run `questions.py`. It enumerates the surviving uncertainties from the actual
figures, prices each one, and splits them into **ask** and **assume**. Then
send one message containing:

1. What you established, with the numbers (two or three lines, not a report).
2. The questions worth asking — at most three.
3. The assumptions you applied, stated plainly so the client can object
   without being asked.

**Phase C — work. Escalate only on material ambiguity.**

Record each answer as a decision, re-run, and continue. Ask again only when a
new uncertainty appears that is both material and genuinely undecidable.

## When a question earns its place

Four filters, in order. A question has to survive all of them.

**1. Can the data answer it?** Then it is not a question. Inquiry on its own
is weak evidence and is meant to be corroborated, so the instinct to ask
before computing is backwards here. Offsetting sibling sub-accounts are the
clearest case: the gaps cancel exactly under a shared parent, which proves the
cause. Asking about it wastes a turn and signals you did not look.

**2. Is the amount above materiality?** Below it, apply the convention and
move on. Note that *share of the gap* is the wrong filter: one 1.9M decimal
shift makes every other real problem look trivial by comparison. Rank by
share, gate by absolute amount.

**3. Would the plausible answers change a number?** If every answer leads to
the same treatment, it does not matter. Pick one, say which, continue.

**4. Is it already decided?** Check the decision log before asking again.

## What the default costs — the ranking rule that matters

Rank mostly by amount, with one override: **a question whose default could
make the answer _wrong_ outranks a larger question whose default only leaves
it _incomplete_.**

- *Incomplete* — "report this 47,000 as unexplained." Honest and unfinished. Safe to assume.
- *Wrong* — "treat these repeated rows as real" or "treat them as an export artifact." Two different numbers, and nothing in the data distinguishes them. Never settle that quietly.

`questions.py` returns `risk_if_assumed` for exactly this reason. A smaller
irreducibly-human question beating a larger mechanical one is correct
behaviour, not a scoring bug.

## Ask in a batch, not a queue

Independent questions go in **one message**. Serialising them multiplies
round-trips for no information gain, and round-trips are the thing that makes
this slower than manual work.

Serialise only when an answer changes which question comes next — when the
second question is meaningless until the first is settled. That is rare. Scope,
page-break ambiguity and unattributed clusters are all independent of each
other.

Three is the working cap. More than that reads as an interrogation and invites
satisficing: the client answers the first two carefully and waves at the rest.

## Phrase as a default to confirm, never as an open question

An open question makes the client do the thinking. A default makes them do a
single check. Same information, a fraction of the effort.

> **Don't:** "How should I treat the accounts that only appear in the closing
> balance?"
>
> **Do:** "Four accounts appear only in the closing balance, 378,900.00 in
> total, with no opening balance and no postings — they look like they are
> maintained in another system. I am excluding them from scope unless you say
> otherwise."

Every question carries: the **amount at stake**, the **evidence that prompted
it**, two or three **concrete options**, and the **default** if they do not
answer. And always a don't-know path — "if you are not sure, I will report it
as unresolved and flag it" — because a guessed answer is worse than a recorded
uncertainty.

## What not to do

- **Do not ask open-ended diagnostic questions.** "Is your data clean?" "What do you think is wrong?" The client came to you for that.
- **Do not lead.** "These are duplicates, right?" produces your answer in their voice. Describe what the rows look like and let them tell you.
- **Do not ask the client to classify the finding.** Gather the evidence, classify it against the taxonomy yourself, and have them confirm the facts you could not compute.
- **Do not ask twice.** Check the decision log.
- **Do not hide an assumption to avoid a question.** An unstated assumption is the failure mode this whole protocol exists to prevent. State it; they can object for free.

## Worked example

After Phase A on a 2.0M gross gap, `questions.py` returns three questions and
two assumptions. One message:

> I have run the reconciliation. The equation is `closing = opening +
> movements` — I tested both conventions and addition reconciled 7 accounts
> against 1, so that is settled. 7 of 12 accounts tie out; 2,009,988.87 is
> open across 5.
>
> Three things I cannot determine from the data:
>
> 1. **8,048.92** — account `2432-01` appears only in the closing balance, with no opening balance and no postings. Out of scope, or is the other extract incomplete? *Default: I keep it in scope and report it as unexplained.*
> 2. **7,500.00** — three consecutive identical rows on `8241-01`. These are either a paginated-export artifact or genuine repeated instalments, and the data cannot tell them apart. Checking ten rows against the source document would settle it. *Default: I keep them and report the amount as unresolved.*
> 3. **47,394.41** — account `8241-01` breaks with no recognisable pattern. Do you have open-item detail for it? *Default: reported as unexplained, low confidence.*
>
> Two assumptions I have applied, tell me if either is wrong:
>
> - One posting of 12,345.67 ("AJUSTE DIVERSOS") has no derivable account; I am leaving it unattributed and reporting it as an open item.
> - Account `8722-01` moved 8,006.67 with no postings at all, which usually means the extract was filtered. I am reporting it as unexplained rather than assuming the balance is wrong.
>
> Meanwhile: a 1,944,943.11 difference on `6652-04` is a decimal point keyed
> three places right, and 1,595.76 across `4363-01/02` is one posting on the
> wrong sibling sub-account. Both are arithmetically certain and need no input
> from you.

Three questions, two stated assumptions, and 97% of the gap already explained
without asking anything. That is the target.

## Working unattended

If the client is not there to answer, do not stall. Apply every default, mark
each one as an assumption in the report with its amount, and put the questions
in the open-questions section ranked by what they would resolve. A report that
says exactly where it is uncertain is useful. One that hides its uncertainties
behind plausible numbers is not.
