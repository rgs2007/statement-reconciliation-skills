# Phase 4 — Root-cause taxonomy

Every break gets exactly one primary category, plus optional secondary tags. Category codes stay in English; the explanation is written in the user's language.

Work down this list in order — earlier causes are usually larger and can mask later ones. Re-rank by amount once all are computed.

---

## SCOPE_MISMATCH
An account or item appears on one side only.

**Signature** · key present in closing but absent from opening and movements (or vice versa); frequently a small number of accounts carrying very large balances.
**Why it happens** · different extraction scopes, a filter applied to one export, accounts opened or closed mid-period, one side covering a different entity or date range.
**Check first** · this routinely dominates the total gap. Quantify and separate it before analysing anything else, or every other number will be distorted.
**Remediation** · re-export both sides with identical scope, or record a scope exclusion decision with justification.
**Confidence** · HIGH when the key is simply absent and control totals confirm it.

## MISSING_MOVEMENTS
Opening and closing both exist and differ, but no transactions explain the change.

**Signature** · gap equals the full opening-to-closing delta; zero or near-zero attributed movements.
**Why** · transaction extract filtered or truncated, a sub-ledger not included, postings made directly to the balance.
**Remediation** · obtain the complete transaction listing for the period.
**Confidence** · HIGH when movement count is zero; MEDIUM when some movements exist, because the true cause may be incomplete attribution rather than missing data — check the unattributed residual before concluding.

## MISSING_BALANCE_ROWS
Transactions exist for a key with no corresponding opening or closing row.

**Signature** · activity present, one balance side absent.
**Why** · zero-balance accounts suppressed in the balance report, or a key normalisation mismatch between files.
**Remediation** · confirm whether the account legitimately closed at zero, or re-export including zero balances.
**Confidence** · MEDIUM — a normalisation bug produces an identical signature. Rule that out first by checking whether a similar key exists on the other side.

## SUBACCOUNT_MISATTRIBUTION
Value posted to a sibling of the correct account.

**Signature** · two or more keys sharing a parent, with gaps that offset to approximately zero.
**Why** · data-entry or mapping error; the money is present, just in the wrong place.
**Remediation** · reclassification entry. No cash impact.
**Confidence** · HIGH when the offset is exact and the accounts share a parent; MEDIUM when approximate.
**Note** · report these as a *pair*, with the parent-level net, or the report will overstate the problem twice over.

## DECIMAL_SHIFT
A value keyed with the decimal point misplaced, typically by a factor of 10, 100 or 1000.

**Signature** · gap ≈ a transaction amount × (10ⁿ − 1); the suspect transaction's magnitude is a clean power-of-ten multiple of a plausible value, and often a later correcting entry exists.
**Remediation** · correcting journal entry.
**Confidence** · HIGH when the ratio is exact and the corrected value restores the balance; otherwise MEDIUM.

## DUPLICATE_POSTING
The same transaction recorded more than once.

**Signature** · identical amount, reference and account appearing multiple times; gap equals a multiple of the amount.
**Caution** · genuinely repeated instalments look identical. Never de-duplicate without confirmation.
**Remediation** · reverse the surplus entries.
**Confidence** · MEDIUM by default; HIGH only once the user confirms the repetition is not legitimate.

## PAGEBREAK_DUPLICATION
Rows repeated as an artifact of a paginated or printed source, not real transactions.

**Signature** · consecutive identical rows, often clustering at regular intervals corresponding to page length.
**Why this is dangerous** · it is indistinguishable by signature alone from legitimate repeated instalments, and it can be enormous. De-duplicating when the rows are real destroys a correct reconciliation; not de-duplicating when they are artifacts leaves a huge phantom gap.
**Remediation** · ask the user to compare a sample against the source document. Until answered, treat the amount as **suspect and quantified but unconfirmed**, and exclude it from the headline "explained" figure.
**Confidence** · LOW until the user confirms. Never resolve this one autonomously.

## REVERSAL_PAIR
A posting and its explicit reversal.

**Signature** · exact ± pairs on the same key and document; large gross, near-zero net.
**Remediation** · usually none — informational. Report as gross activity, not as a gap.
**Confidence** · HIGH when amounts and references match exactly.

## TIMING_DIFFERENCE / CUT_OFF
A transaction recorded in different periods on the two sides.

**Signature** · the item appears on the other side in the adjacent period; gap reverses next period.
**Remediation** · accrual or cut-off adjustment; frequently no error at all.
**Confidence** · HIGH when the matching item is located in the adjacent period; LOW when inferred only from timing proximity.

## UNATTRIBUTED
Transactions whose account could not be determined.

**Signature** · extraction rules produced no key.
**Remediation** · extend extraction rules, or map individually.
**Report** · count, net and gross, plus the largest items with candidate accounts.
**Confidence** · describes only the fact of non-attribution — HIGH — while any *proposed* mapping carries its own, usually MEDIUM or LOW.

## ITEM_LEVEL_BREAK
The balance breaks and item matching leaves a residue that fits none of the above.

Use this only as a genuine residual category, not as a default. If a large share of breaks land here, the more specific detectors are not firing — investigate that as a tooling gap and say so in the report rather than presenting it as an answer.

## FX_TRANSLATION
Multi-currency: the gap corresponds to a rate difference.

**Signature** · gap proportional to balance; consistent percentage across affected accounts.
**Remediation** · align translation rates and revaluation treatment.
**Confidence** · MEDIUM unless the implied rate matches a published rate for the date.

---

## Applying the taxonomy

- One primary cause per break, chosen by the strongest evidence, not the first that fits.
- Explicitly record the **alternatives considered and rejected**, with why. This is what makes a finding auditable rather than merely assertive.
- Test cheap deterministic signatures (exact offsets, exact ratios, exact duplicates) before reaching for judgement.
- Aggregate by category for the summary, ranked by gross amount, with confirmed and unconfirmed totals kept separate so a suspect figure never inflates the explained total.
