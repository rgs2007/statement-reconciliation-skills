#!/usr/bin/env python3
"""Generic reconciliation engine: attribute, solve sign convention, find breaks.

Deterministic only - no model calls. Reads a datamap describing the sources,
computes per-key gaps, applies structural detectors, and writes breaks,
residual and metrics for the agent to interpret.

Usage
-----
    python reconcile.py DATAMAP.json --out runs/run-001 [--materiality 0.01]

Datamap shape (all paths relative to the datamap file, or absolute):

    {
      "opening":   {"path": "working/open.csv",  "key": "account",
                    "amount": "balance"},
      "closing":   {"path": "working/close.csv", "key": "account",
                    "amount": "balance"},
      "movements": {"path": "working/mov.csv",   "amount": "value",
                    "key": "account",                     # OR:
                    "key_from": ["desc1", "desc2"],       # parse key from text
                    "rules": [{"name": "S0", "pattern": null}]},
      "decimal_style": "dot"        # or "comma"; omit to auto-detect
    }

If `key_from` is given instead of `key`, keys are extracted from those text
columns using `rules` in order, first match wins. A rule with a null pattern
is the GENERIC rule: the key appears at the head of the field. Always keep it
first - most ordinary exports need nothing else.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import pandas as pd

# Isolated mode (python -I) does not prepend the script's own directory to
# sys.path, so make the sibling import explicit rather than relying on it.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# All arithmetic comes from lib.py — the single implementation. This module
# only orchestrates the standard roll-forward plan; it defines no figures of
# its own. See steps/ for the individually-invocable version of this pipeline.
from lib import (GENERIC_KEY, canon, detect_style, key_from_text,  # noqa: F401
                 load_side, parse_amount, _sha256)


# ---------------------------------------------------------------- engine
def run(dm: dict, base: str, materiality: float, eff: dict | None = None) -> dict:
    eff = eff or {}
    if eff.get("tolerance") is not None:
        materiality = float(eff["tolerance"])
    style = dm.get("decimal_style")
    op = load_side(dm["opening"], base, style)
    cl = load_side(dm["closing"], base, style)
    mv = load_side(dm["movements"], base, style)

    # manual attributions from the decision log override extraction
    # decision-log keys arrive in the user's natural form ("1400-01"); they
    # must be canonicalised or they will silently match nothing.
    manual = {k: canon(v) for k, v in (eff.get("attribute") or {}).items()}
    if manual and "source_id" in mv.columns:
        sid = mv["source_id"].fillna("").astype(str)
        mv.loc[sid.isin(manual), "_key"] = sid[sid.isin(manual)].map(manual)
        mv.loc[sid.isin(manual), "_rule"] = "MANUAL"

    excl = {canon(k) for k in (eff.get("exclude_keys") or [])} - {None}
    if excl:
        for df in (op, cl, mv):
            df.loc[df["_key"].isin(excl), "_key"] = None

    o = op.groupby("_key")["_amt"].sum()
    c = cl.groupby("_key")["_amt"].sum()
    m = mv[mv["_key"].notna()].groupby("_key")["_amt"].sum()

    keys = sorted(set(o.index) | set(c.index) | set(m.index))
    O = o.reindex(keys).fillna(0.0)
    C = c.reindex(keys).fillna(0.0)
    M = m.reindex(keys).fillna(0.0)

    # --- solve the sign convention empirically; never assume it
    shared = [k for k in keys if k in o.index and k in c.index]
    plus = int(((C - (O + M)).abs() <= materiality).reindex(shared).sum())
    minus = int(((C - (O - M)).abs() <= materiality).reindex(shared).sum())
    sign = 1 if plus >= minus else -1
    if eff.get("convention") is not None:
        sign = int(eff["convention"])
    expected = O + sign * M
    gap = (C - expected).round(2)

    status = pd.Series("BREAK", index=keys)
    status[gap.abs() <= materiality] = "RECONCILED"
    for k in keys:
        in_o, in_c, in_m = k in o.index, k in c.index, k in m.index
        if in_c and not in_o and not in_m:
            status[k] = "CLOSING_ONLY"
        elif in_o and not in_c and not in_m:
            status[k] = "OPENING_ONLY"
        elif in_m and not in_o and not in_c:
            status[k] = "MOVEMENT_ONLY"

    breaks = pd.DataFrame({"key": keys, "opening": O.values, "movements": M.values,
                           "closing": C.values, "expected": expected.values,
                           "gap": gap.values, "status": status.values})
    breaks = breaks[breaks.status != "RECONCILED"].sort_values(
        "gap", key=lambda s: s.abs(), ascending=False)

    # --- structural detectors (deterministic signatures only)
    breaks["signal"] = ""
    g = dict(zip(breaks.key, breaks.gap))

    def parent(k):
        return k.rsplit("-", 1)[0] if "-" in k else k

    fam: dict[str, list[str]] = {}
    for k in breaks.key:
        fam.setdefault(parent(k), []).append(k)
    from itertools import combinations
    for p, ks in fam.items():
        if len(ks) < 2:
            continue
        # whole family nets out
        if abs(sum(g[k] for k in ks)) <= materiality:
            for k in ks:
                breaks.loc[breaks.key == k, "signal"] = "OFFSETTING_SIBLINGS"
            continue
        # otherwise look for offsetting PAIRS inside the family; a family can
        # contain one mis-post plus unrelated breaks, so the sum test alone
        # under-detects.
        for a_, b_ in combinations(sorted(ks, key=lambda k: -abs(g[k])), 2):
            if abs(g[a_] + g[b_]) <= materiality and abs(g[a_]) > materiality:
                for k in (a_, b_):
                    if not breaks.loc[breaks.key == k, "signal"].iloc[0]:
                        breaks.loc[breaks.key == k, "signal"] = "OFFSETTING_SIBLINGS"

    mv_by_key = {k: grp["_amt"].tolist() for k, grp in mv[mv["_key"].notna()].groupby("_key")}
    for k, gv in g.items():
        if breaks.loc[breaks.key == k, "signal"].iloc[0]:
            continue
        # a value keyed f-times too large leaves a gap of amt*(f-1)/f
        for amt in mv_by_key.get(k, []):
            if not amt:
                continue
            hit = next((f for f in (10, 100, 1000)
                        if abs(abs(gv) - abs(amt) * (f - 1) / f) <= max(materiality, abs(amt) * 1e-6)), None)
            if hit:
                breaks.loc[breaks.key == k, "signal"] = f"DECIMAL_SHIFT_x{hit}"
                break

    # --- duplicate and reversal signatures on the movement side
    dup_rows = rev_rows = 0
    dup_amt = rev_amt = 0.0
    consec_dups = 0
    if len(mv):
        # a genuine duplicate posting usually carries a DIFFERENT row id, so
        # id-like columns are excluded from the signature or nothing is found.
        id_tokens = ("id", "seq", "line", "row", "uuid", "guid")
        sig_cols = [c for c in mv.columns
                    if not c.startswith("_")
                    and not any(t in str(c).lower() for t in id_tokens)]
        sig_cols = sig_cols or [c for c in mv.columns if not c.startswith("_")]
        sig = mv[sig_cols].astype(str).agg("|".join, axis=1)
        dmask = sig.duplicated(keep="first")
        # Only duplicates on an account that ACTUALLY BREAKS are suspect.
        # If the balance ties exactly, a repeated row cannot be a spurious
        # extra posting - an extra posting would break the balance - so the
        # rows are legitimate repeated instalments. This resolves the
        # duplicate-vs-instalment ambiguity in the common case; where the
        # account does break, the ambiguity genuinely remains and the user
        # must be asked (see taxonomy: PAGEBREAK_DUPLICATION).
        broken = set(breaks.key) if len(breaks) else set()
        suspect = mv["_key"].isna() | mv["_key"].isin(broken)
        dmask = dmask & suspect
        dup_rows = int(dmask.sum())
        dup_amt = round(float(mv.loc[dmask, "_amt"].abs().sum()), 2)
        # consecutive identical rows are the page-break signature specifically
        consec_mask = (sig == sig.shift()) & suspect
        consec_dups = int(consec_mask.sum())

        # Per-key attribution: when a break equals the duplicated value on
        # that same account, the duplicate explains the break. Name it, rather
        # than letting it fall through to a generic residual - a named cause
        # tells the accountant what to DO.
        for k, grp in mv[dmask & mv["_key"].notna()].groupby("_key"):
            if k not in g:
                continue
            if abs(abs(g[k]) - float(grp["_amt"].abs().sum())) <= materiality:
                cur = breaks.loc[breaks.key == k, "signal"].iloc[0]
                if cur:
                    continue
                # Consecutive repeats are the paginated-source signature and
                # stay LOW; non-adjacent repeats are a duplicate posting.
                tag = ("PAGEBREAK_SUSPECT"
                       if bool(consec_mask.reindex(grp.index).fillna(False).any())
                       else "DUPLICATE_POSTING")
                breaks.loc[breaks.key == k, "signal"] = tag
        # reversal pairs: same key, exactly opposing amounts
        for k, grp in mv[mv["_key"].notna()].groupby("_key"):
            pos = sorted(round(v, 2) for v in grp["_amt"] if v > 0)
            neg = sorted(-round(v, 2) for v in grp["_amt"] if v < 0)
            i = j = 0
            while i < len(pos) and j < len(neg):
                if abs(pos[i] - neg[j]) <= materiality:
                    rev_rows += 2
                    rev_amt += pos[i] * 2
                    i += 1
                    j += 1
                elif pos[i] < neg[j]:
                    i += 1
                else:
                    j += 1

    unattr = mv[mv["_key"].isna()].copy()
    residual = unattr.assign(amount=unattr["_amt"]).sort_values(
        "amount", key=lambda s: s.abs(), ascending=False)

    metrics = {
        "keys_total": len(keys),
        "reconciled": int((status == "RECONCILED").sum()),
        "reconciled_pct": round(100 * (status == "RECONCILED").sum() / max(len(keys), 1), 1),
        "sign_convention": "closing = opening + movements" if sign == 1
                           else "closing = opening - movements",
        "convention_evidence": {"reconciled_with_plus": plus,
                                "reconciled_with_minus": minus,
                                "keys_tested": len(shared)},
        "gap_gross": round(float(gap[status != "RECONCILED"].abs().sum()), 2),
        "gap_net": round(float(gap[status != "RECONCILED"].sum()), 2),
        "scope_only": {s: int((status == s).sum())
                       for s in ("CLOSING_ONLY", "OPENING_ONLY", "MOVEMENT_ONLY")},
        "movements_total": int(len(mv)),
        "movements_unattributed": int(len(unattr)),
        "attribution_rate_pct": round(100 * (1 - len(unattr) / max(len(mv), 1)), 2),
        "residual_net": round(float(unattr["_amt"].sum()), 2),
        "residual_gross": round(float(unattr["_amt"].abs().sum()), 2),
        "rule_coverage": mv["_rule"].value_counts().to_dict(),
        "materiality": materiality,
        "datasets": [dict(d.attrs.get("source", {}),
                          role=r, sum=round(float(d["_amt"].sum()), 2))
                     for r, d in (("opening", op), ("closing", cl), ("movements", mv))],
        "duplicate_rows": dup_rows,
        "duplicate_gross": dup_amt,
        "consecutive_duplicate_rows": consec_dups,
        "reversal_rows": rev_rows,
        "reversal_gross": round(rev_amt, 2),
        "decisions_applied": len(eff.get("applied") or []),
        "scope_excluded_keys": len(eff.get("exclude_keys") or []),
    }
    # parent-level rollup separates misposting from missing money
    pr = breaks.assign(p=breaks.key.map(parent)).groupby("p")["gap"].sum()
    metrics["gap_gross_at_parent"] = round(float(pr.abs().sum()), 2)
    metrics["parents_netting_to_zero"] = int((pr.abs() <= materiality).sum())
    return {"metrics": metrics, "breaks": breaks, "residual": residual}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("datamap")
    ap.add_argument("--out", default="runs/run-001")
    ap.add_argument("--materiality", type=float, default=0.01)
    ap.add_argument("--decisions", help="path to decisions.jsonl to replay")
    a = ap.parse_args()

    dm = json.load(open(a.datamap))
    base = os.path.dirname(os.path.abspath(a.datamap))
    eff = None
    if a.decisions:
        # Resolution comes from lib (vendored), so the engine can replay a
        # decision log whether or not the recon-decisions skill is installed.
        from lib import resolve_file
        try:
            eff = resolve_file(a.decisions)
        except ValueError as e:
            raise SystemExit(f"{e}")
    res = run(dm, base, a.materiality, eff)

    os.makedirs(a.out, exist_ok=True)
    res["breaks"].to_csv(os.path.join(a.out, "breaks.csv"), index=False)
    cols = [c for c in res["residual"].columns if not c.startswith("_")]
    res["residual"][cols].to_csv(os.path.join(a.out, "residual.csv"), index=False)
    json.dump(res["metrics"], open(os.path.join(a.out, "metrics.json"), "w"), indent=2)

    m = res["metrics"]
    print(json.dumps(m, indent=2))
    print(f"\nbreaks -> {a.out}/breaks.csv ({len(res['breaks'])} rows)")
    print(f"residual -> {a.out}/residual.csv ({len(res['residual'])} rows)")
    if m["attribution_rate_pct"] < 95 and m["movements_unattributed"]:
        print("\n! Attribution below 95%: an extraction rule is probably still missing. "
              "Inspect residual.csv for a recurring pattern before interpreting the gap.")
    if m["consecutive_duplicate_rows"]:
        print(f"\n! {m['consecutive_duplicate_rows']} consecutive duplicate row(s) found. "
              "These may be page-break artifacts OR legitimate repeated instalments - "
              "the data cannot tell them apart. Ask the user; do NOT de-duplicate "
              "automatically (see taxonomy: PAGEBREAK_DUPLICATION).")
    if abs(m["convention_evidence"]["reconciled_with_plus"]
           - m["convention_evidence"]["reconciled_with_minus"]) < 3:
        print("\n! The two sign conventions score alike - the convention is NOT established. "
              "Investigate mixed conventions or out-of-scope movements before proceeding.")


if __name__ == "__main__":
    sys.exit(main())
