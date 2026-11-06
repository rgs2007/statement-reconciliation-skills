#!/usr/bin/env python3
"""STEP `questions` — rank what is worth asking the client, and what to assume.

    python steps/questions.py --run runs/r1 [--budget 3] [--min-share 0.01]

Produces: `questions`
Requires: `equation`

Asking is expensive: every question costs the client attention and costs the
job a round-trip. An accountant doing this by hand would simply make most of
these calls themselves. So this step does what a model should not do by feel —
it enumerates the open uncertainties from the actual figures, prices each one,
and splits them into **ask** and **assume**.

Scoring follows value-of-information logic: a question earns a place only if
the answer would change a number. Three filters, applied in order:

  1. Can it be computed or corroborated from the data? Then it is not a
     question. (ISA 500: inquiry alone is weak evidence; corroborate it.)
     Offsetting sibling pairs are the clearest case — they are
     arithmetically conclusive, so asking about them wastes a turn.
  2. Is the amount at stake below materiality? Then assume the convention
     and flag it.
  3. Would the plausible answers lead to the same treatment? Then it does
     not matter; pick one and say so.

What survives is ranked by the share of the gap it would resolve, and only
`--budget` questions are returned. Everything else comes back under
`assume` with the default that was applied, so the caller can state its
assumptions instead of hiding them.

The output is deliberately not prose. The caller phrases the questions, in the
client's language, following the interview protocol in the orchestrator skill.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from steps._state import RunState, cli, emit  # noqa: E402

# Questions that affect every figure in the run, not just their own amount.
GLOBAL = 10_000


def _tokens(text: str) -> list[str]:
    """Words worth clustering on: skips pure numbers and very short fragments."""
    return [t for t in re.split(r"[^\wÀ-ÿ]+", str(text).upper())
            if len(t) >= 4 and not t.isdigit()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--materiality", type=float, default=0.01)
    ap.add_argument("--budget", type=int, default=3,
                    help="most questions to return in one round (default 3)")
    ap.add_argument("--min-amount", type=float, default=None,
                    help="absolute floor for asking; defaults to materiality. "
                         "Share of the gap RANKS questions but must not gate "
                         "them: one huge finding would otherwise make every "
                         "other real problem look trivial.")
    a = ap.parse_args()

    floor = a.min_amount if a.min_amount is not None else a.materiality
    st = RunState(a.run)
    st.require("equation")
    eq = st.read_table("equation")
    for c in ("opening", "closing", "movements", "gap"):
        eq[c] = pd.to_numeric(eq[c], errors="coerce").fillna(0.0)

    brk = eq[eq.status != "RECONCILED"].copy()
    total = float(brk.gap.abs().sum()) or 1.0

    signals: dict[str, str] = {}
    if st.exists("signals"):
        sg = st.read_table("signals")
        signals = dict(zip(sg.get("key", []), sg.get("signal", [])))

    conv = st.read_json("convention") if st.exists("convention") else {}
    decided = st.read_json("decisions") if st.exists("decisions") else {}
    already = {str(k) for k in (decided.get("exclude_keys") or [])}
    already |= {str(k) for k in (decided.get("classify") or {})}

    ask: list[dict] = []
    assume: list[dict] = []
    settled: list[dict] = []

    def add(bucket: list, *, id_: str, topic: str, amount: float,
            subject, why: str, options: list[str], default: str,
            risk: str = "incomplete",
            share: float | None = None, boost: float = 0.0) -> None:
        """risk: what applying the default costs.

        "incomplete" — the figure is reported as unexplained. Honest, just
        unfinished, so assuming it is safe.
        "wrong" — the default silently picks one of two treatments that give
        DIFFERENT numbers. Those must never be resolved quietly, so they get
        a boost and are always stated even when over budget.
        """
        unsafe = risk == "wrong"
        bucket.append({
            "id": id_, "topic": topic,
            "amount_at_stake": round(abs(amount), 2),
            "share_of_gap": round(min(abs(amount) / total, 1.0), 4)
            if share is None else share,
            "subject": subject, "why_it_matters": why,
            "options": options, "default_if_unanswered": default,
            "risk_if_assumed": risk,
            "must_state_explicitly": unsafe,
            # A larger question with a safe default should not crowd out a
            # smaller one that cannot be decided by computation at all.
            "score": round(abs(amount) / total + boost + (0.5 if unsafe else 0.0), 4),
        })

    # ---------------------------------------------------------------- 1
    # Sign convention. Affects every figure, so it outranks any amount.
    if conv and not conv.get("established", True):
        add(ask, id_="convention", topic="SIGN_CONVENTION", amount=total,
            subject=conv.get("evidence", {}),
            why="Both conventions reconcile a similar number of accounts, so "
                "the equation itself is unproven. Every gap below is "
                "provisional until this is settled.",
            options=["closing = opening + movements",
                     "closing = opening - movements",
                     "mixed across sub-ledgers — needs splitting"],
            default=conv.get("equation", "closing = opening + movements"),
            risk="wrong", boost=GLOBAL)

    # ---------------------------------------------------------------- 2
    # Scope: accounts present on one side only. Usually dominates the gap,
    # and one answer can clear many accounts at once.
    scope = brk[brk.status.isin(["CLOSING_ONLY", "OPENING_ONLY",
                                 "MOVEMENT_ONLY"])]
    scope = scope[~scope.key.astype(str).isin(already)]
    if len(scope):
        by_status = defaultdict(list)
        for r in scope.itertuples():
            by_status[r.status].append((str(r.key), float(r.gap)))
        for status, items in by_status.items():
            amt = sum(abs(v) for _, v in items)
            if amt < floor:
                continue
            items.sort(key=lambda t: -abs(t[1]))
            add(ask, id_=f"scope_{status.lower()}", topic="SCOPE_MISMATCH",
                amount=amt,
                subject={"status": status, "accounts": len(items),
                         "largest": [{"key": k, "amount": round(v, 2)}
                                     for k, v in items[:5]]},
                why=f"{len(items)} account(s) appear on one side only, worth "
                    f"{amt:,.2f}. Either the two extracts were pulled with "
                    f"different scope, or these are genuinely out of scope. "
                    f"One answer settles all of them.",
                options=["out of scope — exclude them",
                         "in scope — the other extract is incomplete",
                         "re-export both sides with matching scope"],
                default="keep in scope and report as unexplained",
                risk="wrong")

    # ---------------------------------------------------------------- 3
    # The genuinely ambiguous duplicates. The data cannot settle this one.
    pb = [k for k, s in signals.items() if s == "PAGEBREAK_SUSPECT"]
    dup = st.read_json("dup_stats") if st.exists("dup_stats") else {}
    consec = int(dup.get("consecutive_duplicate_rows") or 0)
    if pb or consec:
        amt = (float(brk[brk.key.isin(pb)].gap.abs().sum()) if pb
               else float(dup.get("consecutive_gross") or 0.0))
        add(ask, id_="pagebreak", topic="PAGEBREAK_DUPLICATION", amount=amt,
            subject={"accounts": pb or "not isolated to one account",
                     "consecutive_rows": consec,
                     "consecutive_gross": dup.get("consecutive_gross")},
            why=f"Consecutive identical rows worth {amt:,.2f}. A paginated "
                f"export and real repeated instalments look the same in the "
                f"data, so this cannot be decided by computation — and "
                f"de-duplicating real instalments would turn a correct "
                f"reconciliation into a wrong one.",
            options=["artifact of the export — exclude the repeats",
                     "genuine instalments — keep them",
                     "I will check ten rows against the source document"],
            default="keep the rows; report the amount as unresolved (LOW)",
            risk="wrong")

    # ---------------------------------------------------------------- 4
    # Unattributed movements, CLUSTERED. One extraction rule can recover a
    # whole group, so asking about the cluster beats asking row by row.
    if st.exists("residual"):
        res = st.read_table("residual")
        if len(res):
            amt_col = "amount" if "amount" in res.columns else None
            # NB: itertuples() mangles names starting with "_", so this
            # working column must not be underscore-prefixed.
            res["qv"] = (pd.to_numeric(res[amt_col], errors="coerce").fillna(0.0)
                         if amt_col else 0.0)
            text_cols = [c for c in res.columns
                         if not c.startswith("_") and c not in (amt_col, "qv")
                         and res[c].astype(str).str.len().mean() > 6]
            clusters: dict[str, list] = defaultdict(list)
            for r in res.itertuples():
                blob = " ".join(str(getattr(r, c, "")) for c in text_cols)
                for t in set(_tokens(blob)):
                    clusters[t].append(float(r.qv))
            ranked = sorted(
                ((t, v) for t, v in clusters.items() if len(v) >= 2),
                key=lambda kv: -sum(abs(x) for x in kv[1]))
            res_gross = float(res["qv"].abs().sum())
            if ranked:
                t, vals = ranked[0]
                amt = sum(abs(v) for v in vals)
                add(ask, id_="residual_cluster", topic="UNATTRIBUTED",
                    amount=amt,
                    subject={"shared_token": t, "rows": len(vals),
                             "cluster_gross": round(amt, 2),
                             "residual_gross": round(res_gross, 2)},
                    why=f"{len(vals)} unattributed rows share the token "
                        f"'{t}', worth {amt:,.2f} together. One extraction "
                        f"rule would recover the whole cluster, which is "
                        f"worth far more than mapping rows one at a time.",
                    options=[f"'{t}' identifies one account — which?",
                             "it is several accounts — needs a rule, not a mapping",
                             "these are out of scope"],
                    default="leave unattributed and report as an open item")
            elif res_gross >= floor:
                add(ask, id_="residual_rows", topic="UNATTRIBUTED",
                    amount=res_gross,
                    subject={"rows": int(len(res)),
                             "gross": round(res_gross, 2)},
                    why=f"{len(res)} rows have no derivable account, worth "
                        f"{res_gross:,.2f} gross, with no shared pattern to "
                        f"generalise from.",
                    options=["map the largest individually",
                             "they belong to one suspense account",
                             "out of scope"],
                    default="leave unattributed and report as open items")

    # ---------------------------------------------------------------- 5
    # Materiality. Cheap to answer and can retire a long tail of noise, so
    # it is only worth asking when there IS a long tail.
    noise = brk[brk.gap.abs() <= 1.0]
    if len(noise) >= 3 and decided.get("tolerance") is None:
        add(ask, id_="materiality", topic="TOLERANCE",
            amount=float(noise.gap.abs().sum()),
            subject={"breaks_under_1.00": int(len(noise)),
                     "their_total": round(float(noise.gap.abs().sum()), 2)},
            why=f"{len(noise)} accounts differ by under 1.00 — almost "
                f"certainly rounding. Setting a tolerance retires them and "
                f"leaves only the differences that matter.",
            options=["0.01 — audit requires exact", "1.00", "100.00"],
            default="0.01 (report every difference)",
            boost=GLOBAL / 2)

    # ---------------------------------------------------------------- 6
    # Balances moved but no posting explains it. Usually a truncated extract,
    # and one answer can clear several accounts, so it is worth a slot.
    nomov = brk[(brk.movements.abs() <= a.materiality)
                & (brk.gap.abs() > a.materiality)
                & (~brk.status.isin(["CLOSING_ONLY", "OPENING_ONLY",
                                     "MOVEMENT_ONLY"]))
                & (~brk.key.astype(str).isin(already))]
    if len(nomov):
        amt = float(nomov.gap.abs().sum())
        if amt >= floor:
            top = nomov.reindex(nomov.gap.abs().sort_values(
                ascending=False).index).head(5)
            add(ask, id_="missing_movements", topic="MISSING_MOVEMENTS",
                amount=amt,
                subject={"accounts": int(len(nomov)),
                         "largest": [{"key": str(r.key),
                                      "gap": round(float(r.gap), 2)}
                                     for r in top.itertuples()]},
                why=f"{len(nomov)} account(s) worth {amt:,.2f} changed "
                    f"balance with no posting to explain it. Either the "
                    f"transaction extract was filtered, or these were posted "
                    f"straight to the balance. One answer covers all of them.",
                options=["the extract was filtered — I can re-export",
                         "posted directly to the balance, no transactions exist",
                         "those postings are in a different sub-ledger"],
                default="report as unexplained; request the full extract")

    # ---------------------------------------------------------------- 7
    # Breaks with no structural cause and no item detail to match on.
    plain = brk[(~brk.key.astype(str).isin(signals))
                & (~brk.status.isin(["CLOSING_ONLY", "OPENING_ONLY",
                                     "MOVEMENT_ONLY"]))
                & (brk.movements.abs() > a.materiality)
                & (brk.gap.abs() > 1.0)]
    if len(plain):
        amt = float(plain.gap.abs().sum())
        if amt >= floor:
            top = plain.reindex(plain.gap.abs().sort_values(
                ascending=False).index).head(5)
            add(ask, id_="item_detail", topic="ITEM_LEVEL_BREAK", amount=amt,
                subject={"accounts": int(len(plain)),
                         "largest": [{"key": str(r.key),
                                      "gap": round(float(r.gap), 2)}
                                     for r in top.itertuples()]},
                why=f"{len(plain)} account(s) worth {amt:,.2f} break with no "
                    f"recognisable signature. Item-level detail would let "
                    f"these be matched rather than guessed at.",
                options=["I can supply open-item detail",
                         "no detail exists — report as unexplained",
                         "these are known timing differences"],
                default="report as unexplained, LOW confidence")

    # ---------------------------------------------- settled, do not ask
    sib = [k for k, s in signals.items() if s == "OFFSETTING_SIBLINGS"]
    if sib:
        settled.append({
            "topic": "SUBACCOUNT_MISATTRIBUTION", "accounts": sib,
            "amount": round(float(brk[brk.key.isin(sib)].gap.abs().sum()), 2),
            "resolved_by": "arithmetic — the gaps offset exactly under a "
                           "shared parent, so the cause is proven and there "
                           "is nothing to ask"})
    for topic, sigs in (("DECIMAL_SHIFT", ("DECIMAL_SHIFT_x10",
                                           "DECIMAL_SHIFT_x100",
                                           "DECIMAL_SHIFT_x1000")),
                        ("DUPLICATE_POSTING", ("DUPLICATE_POSTING",))):
        keys = [k for k, s in signals.items() if s in sigs]
        if keys:
            settled.append({
                "topic": topic, "accounts": keys,
                "amount": round(float(brk[brk.key.isin(keys)].gap.abs().sum()), 2),
                "resolved_by": "arithmetic — the gap matches the signature "
                               "exactly; confirm with the client only when "
                               "acting on it, not to diagnose it"})

    # ----------------------------------------------------- apply the budget
    ask.sort(key=lambda q: -q["score"])
    over_budget = ask[a.budget:]
    ask = ask[:a.budget]
    for q in over_budget:
        q["reason_not_asked"] = ("below the question budget for this round; "
                                 "the default was applied and must be stated")
        assume.append(q)

    covered = sum(q["amount_at_stake"] for q in ask)
    payload = {
        "ok": True, "step": "questions",
        "gap_gross": round(total, 2),
        "budget": a.budget,
        "ask": ask,
        "assume": assume,
        "settled_by_arithmetic": settled,
        "coverage": {
            "amount_covered_by_questions": round(covered, 2),
            "share_of_gap_covered": round(min(covered / total, 1.0), 4),
        },
        "protocol": (
            "Ask these together in ONE message, not one at a time: they are "
            "independent, so serialising them only adds round-trips. Phrase "
            "each as a default to confirm rather than an open question, give "
            "the amount at stake, and offer a 'not sure' path. State every "
            "`assume` entry as an assumption in the same message so the "
            "client can object to it without being asked. Everything under "
            "`settled_by_arithmetic` is already proven — do not ask about it."
        ),
    }
    st.write_json("questions", payload)
    st.record("questions",
              params={"budget": a.budget, "min_amount": floor,
                      "materiality": a.materiality},
              inputs=["equation"], outputs=["questions"])
    emit(payload)


if __name__ == "__main__":
    cli(main)
