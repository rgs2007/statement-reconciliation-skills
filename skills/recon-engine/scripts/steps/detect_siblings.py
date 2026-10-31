#!/usr/bin/env python3
"""DETECTOR `detect-siblings` — offsetting sub-accounts under one parent.

    python steps/detect_siblings.py --run runs/r1

Produces: signals/siblings.csv       Requires: `equation`
Signal: OFFSETTING_SIBLINGS (priority 10)

Signature: two or more keys sharing a parent whose gaps offset to about zero.
The money is in the ledger, in the wrong place — a reclassification, not an
investigation, and no cash impact.

Two tests, because the family-sum test alone under-detects: a family can hold
one misposting *plus* unrelated breaks, in which case the family will not net
out but a pair inside it will.
"""
from __future__ import annotations

import argparse
import os
import sys
from itertools import combinations

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from steps._state import RunState, cli, emit  # noqa: E402

PRIORITY = 10


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--materiality", type=float, default=0.01)
    a = ap.parse_args()

    st = RunState(a.run)
    st.require("equation")
    eq = st.read_table("equation")
    eq["gap"] = pd.to_numeric(eq["gap"], errors="coerce").fillna(0.0)
    brk = eq[eq.status != "RECONCILED"]
    g = dict(zip(brk.key, brk.gap))

    def parent(k: str) -> str:
        return k.rsplit("-", 1)[0] if "-" in k else k

    fam: dict[str, list[str]] = {}
    for k in brk.key:
        fam.setdefault(parent(k), []).append(k)

    rows, families = [], 0
    for p, ks in fam.items():
        if len(ks) < 2:
            continue
        if abs(sum(g[k] for k in ks)) <= a.materiality:
            families += 1
            for k in ks:
                rows.append({"key": k, "signal": "OFFSETTING_SIBLINGS",
                             "priority": PRIORITY,
                             "evidence": f"family {p} nets to "
                                         f"{sum(g[k2] for k2 in ks):.2f}"})
            continue
        seen = {r["key"] for r in rows}
        for x, y in combinations(sorted(ks, key=lambda k: -abs(g[k])), 2):
            if abs(g[x] + g[y]) <= a.materiality and abs(g[x]) > a.materiality:
                families += 1
                for k in (x, y):
                    if k not in seen:
                        rows.append({"key": k, "signal": "OFFSETTING_SIBLINGS",
                                     "priority": PRIORITY,
                                     "evidence": f"pair {x}/{y} offsets exactly"})
                        seen.add(k)

    st.write_signals("siblings", rows)
    st.record("detect-siblings", params={"materiality": a.materiality},
              inputs=["equation"])
    emit({"ok": True, "step": "detect-siblings", "flagged_keys": len(rows),
          "families_or_pairs": families, "signal": "OFFSETTING_SIBLINGS",
          "priority": PRIORITY,
          "note": "report these as a pair with the parent-level net, or the "
                  "problem is overstated twice over"})


if __name__ == "__main__":
    cli(main)
