#!/usr/bin/env python3
"""Item-level matching for keys whose balance breaks.

When a balance does not tie, match the underlying items before declaring the
difference unexplained. Runs four passes, cheapest and most certain first:

  1. EXACT      reference + amount
  2. AMOUNT     amount alone, only where unambiguous on both sides
  3. SUBSET     one item against several (a lump payment settling invoices),
                bounded so it terminates on real data
  4. TIMING     item present on the other side in an adjacent period

Whatever survives all four is the genuine residual and the evidence for a
taxonomy classification.

Usage
-----
    python match_items.py LEFT.csv RIGHT.csv --amount value --ref doc \\
        [--key account] [--date posted_on] [--tolerance 0.01] \\
        [--max-subset 4] [--node-cap 200000] [--out runs/run-001]

LEFT and RIGHT are the two sides for one key (e.g. open items vs statement
lines). Use --key to process every key in one pass.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from itertools import combinations

import pandas as pd

# Amount parsing is NOT reimplemented here: lib.py is the single
# implementation, so a figure cannot differ between the engine and the
# item matcher. lib.py is vendored by tools/sync_lib.py.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import parse_amount  # noqa: E402




def subset_match(target: float, pool: list[tuple[int, float]], tol: float,
                 max_size: int, node_cap: int) -> list[int] | None:
    """Find a subset of `pool` summing to `target`.

    Branch and bound with a hard node cap: an unbounded search does not
    terminate on real ledgers. Returns indices, or None if not found or the
    cap was hit.
    """
    pool = [(i, v) for i, v in pool if abs(v) > tol]
    pool.sort(key=lambda t: -abs(t[1]))
    n = len(pool)
    if not n:
        return None
    # cheap exits first
    for i, v in pool:
        if abs(v - target) <= tol:
            return [i]
    suffix = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix[i] = suffix[i + 1] + abs(pool[i][1])
    nodes = 0
    best: list[int] | None = None

    def dfs(i: int, remaining: float, chosen: list[int]) -> bool:
        nonlocal nodes, best
        if nodes > node_cap:
            return False
        nodes += 1
        if abs(remaining) <= tol and chosen:
            best = list(chosen)
            return True
        if i >= n or len(chosen) >= max_size:
            return False
        if abs(remaining) > suffix[i] + tol:
            return False
        idx, val = pool[i]
        chosen.append(idx)
        if dfs(i + 1, remaining - val, chosen):
            return True
        chosen.pop()
        return dfs(i + 1, remaining, chosen)

    dfs(0, target, [])
    return best


def match_one(left: pd.DataFrame, right: pd.DataFrame, amount: str,
              ref: str | None, date: str | None, tol: float,
              max_subset: int, node_cap: int) -> dict:
    L = left.reset_index(drop=True).copy()
    R = right.reset_index(drop=True).copy()
    L["_a"] = L[amount].map(lambda v: parse_amount(v, None))
    R["_a"] = R[amount].map(lambda v: parse_amount(v, None))
    L["_m"] = None
    R["_m"] = None
    pairs = []

    # 1 EXACT: reference + amount
    if ref and ref in L.columns and ref in R.columns:
        ridx: dict = {}
        for j, r in R.iterrows():
            ridx.setdefault((str(r[ref]).strip(), round(r["_a"], 2)), []).append(j)
        for i, r in L.iterrows():
            k = (str(r[ref]).strip(), round(r["_a"], 2))
            if ridx.get(k):
                j = ridx[k].pop()
                L.at[i, "_m"] = "EXACT"
                R.at[j, "_m"] = "EXACT"
                pairs.append({"pass": "EXACT", "left": int(i), "right": int(j),
                              "amount": float(r["_a"])})

    # 2 AMOUNT only, and only where unambiguous on both sides
    lc = L[L._m.isna()]["_a"].round(2).value_counts()
    rc = R[R._m.isna()]["_a"].round(2).value_counts()
    for amt in set(lc.index) & set(rc.index):
        if lc[amt] == 1 and rc[amt] == 1:
            i = L[(L._m.isna()) & (L._a.round(2) == amt)].index[0]
            j = R[(R._m.isna()) & (R._a.round(2) == amt)].index[0]
            L.at[i, "_m"] = "AMOUNT"
            R.at[j, "_m"] = "AMOUNT"
            pairs.append({"pass": "AMOUNT", "left": int(i), "right": int(j),
                          "amount": float(amt)})

    # 3 SUBSET: one large item against several smaller ones
    for big, small, tagB, tagS in ((L, R, "left", "right"), (R, L, "right", "left")):
        for i in list(big[big._m.isna()].index):
            if big.at[i, "_m"] is not None:
                continue
            target = big.at[i, "_a"]
            pool = [(int(j), float(small.at[j, "_a"]))
                    for j in small[small._m.isna()].index]
            if len(pool) < 2:
                continue
            hit = subset_match(target, pool, tol, max_subset, node_cap)
            if hit and len(hit) > 1:
                big.at[i, "_m"] = "SUBSET"
                for j in hit:
                    small.at[j, "_m"] = "SUBSET"
                pairs.append({"pass": "SUBSET", tagB: int(i), tagS: hit,
                              "amount": float(target)})

    # 4 TIMING: same amount, adjacent period
    if date and date in L.columns and date in R.columns:
        lt = pd.to_datetime(L[date], errors="coerce")
        rt = pd.to_datetime(R[date], errors="coerce")
        for i in list(L[L._m.isna()].index):
            cand = R[(R._m.isna()) & (R._a.round(2) == round(L.at[i, "_a"], 2))]
            for j in cand.index:
                if pd.notna(lt[i]) and pd.notna(rt[j]) and abs((lt[i] - rt[j]).days) <= 45:
                    L.at[i, "_m"] = "TIMING"
                    R.at[j, "_m"] = "TIMING"
                    pairs.append({"pass": "TIMING", "left": int(i), "right": int(j),
                                  "amount": float(L.at[i, "_a"]),
                                  "days_apart": int(abs((lt[i] - rt[j]).days))})
                    break

    lu, ru = L[L._m.isna()], R[R._m.isna()]
    return {
        "matched_pairs": pairs,
        "matched_by_pass": pd.Series([p["pass"] for p in pairs]).value_counts().to_dict()
                           if pairs else {},
        "left_total": round(float(L["_a"].sum()), 2),
        "right_total": round(float(R["_a"].sum()), 2),
        "unmatched_left": {"rows": int(len(lu)), "net": round(float(lu["_a"].sum()), 2),
                           "gross": round(float(lu["_a"].abs().sum()), 2)},
        "unmatched_right": {"rows": int(len(ru)), "net": round(float(ru["_a"].sum()), 2),
                            "gross": round(float(ru["_a"].abs().sum()), 2)},
        "residual": round(float(lu["_a"].sum() - ru["_a"].sum()), 2),
        "_left": L, "_right": R,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("left")
    ap.add_argument("right")
    ap.add_argument("--amount", required=True)
    ap.add_argument("--ref")
    ap.add_argument("--key")
    ap.add_argument("--date")
    ap.add_argument("--tolerance", type=float, default=0.01)
    ap.add_argument("--max-subset", type=int, default=4)
    ap.add_argument("--node-cap", type=int, default=200_000)
    ap.add_argument("--out")
    a = ap.parse_args()

    L = pd.read_csv(a.left, dtype=str, keep_default_na=False)
    R = pd.read_csv(a.right, dtype=str, keep_default_na=False)

    results = {}
    if a.key and a.key in L.columns and a.key in R.columns:
        for k in sorted(set(L[a.key]) | set(R[a.key])):
            res = match_one(L[L[a.key] == k], R[R[a.key] == k], a.amount, a.ref,
                            a.date, a.tolerance, a.max_subset, a.node_cap)
            if res["unmatched_left"]["rows"] or res["unmatched_right"]["rows"] or res["matched_pairs"]:
                results[k] = res
    else:
        results["(all)"] = match_one(L, R, a.amount, a.ref, a.date, a.tolerance,
                                     a.max_subset, a.node_cap)

    summary = {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
               for k, v in results.items()}
    print(json.dumps(summary, indent=2, default=str))

    if a.out:
        os.makedirs(a.out, exist_ok=True)
        rows = []
        for k, v in results.items():
            for side, df in (("left", v["_left"]), ("right", v["_right"])):
                un = df[df._m.isna()].copy()
                un.insert(0, "side", side)
                un.insert(0, "key", k)
                rows.append(un.drop(columns=[c for c in ("_m",) if c in un.columns]))
        if rows:
            pd.concat(rows).to_csv(os.path.join(a.out, "unmatched_items.csv"), index=False)
        json.dump(summary, open(os.path.join(a.out, "item_match.json"), "w"),
                  indent=2, default=str)
        print(f"\nunmatched -> {a.out}/unmatched_items.csv")

    tot = sum(v["unmatched_left"]["rows"] + v["unmatched_right"]["rows"]
              for v in results.values())
    if tot:
        print(f"\n{tot} item(s) unmatched after all four passes - this is the "
              "genuine residual and the evidence for classification.")


if __name__ == "__main__":
    sys.exit(main())
