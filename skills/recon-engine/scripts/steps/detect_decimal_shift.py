#!/usr/bin/env python3
"""DETECTOR `detect-decimal-shift` — a value keyed a power of ten too large.

    python steps/detect_decimal_shift.py --run runs/r1

Produces: signals/decimal_shift.csv   Requires: `equation`, `side:movements`
Signal: DECIMAL_SHIFT_x{10,100,1000} (priority 20)

Signature: a value entered f times too large leaves a gap of amt*(f-1)/f.
Each posting on a broken account is tested against that identity, so the
match is arithmetic rather than a guess, and the corrected value is reported.
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from steps._state import RunState, cli, emit  # noqa: E402

PRIORITY = 20
FACTORS = (10, 100, 1000)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--materiality", type=float, default=0.01)
    a = ap.parse_args()

    st = RunState(a.run)
    st.require("equation", "side:movements")
    eq = st.read_table("equation")
    eq["gap"] = pd.to_numeric(eq["gap"], errors="coerce").fillna(0.0)
    brk = eq[eq.status != "RECONCILED"]
    mv = st.read_side("side:movements")

    by_key = {k: grp["_amt"].tolist()
              for k, grp in mv[mv["_key"].notna()].groupby("_key")}
    rows = []
    for k, gv in zip(brk.key, brk.gap):
        for amt in by_key.get(k, []):
            if not amt:
                continue
            hit = next((f for f in FACTORS
                        if abs(abs(gv) - abs(amt) * (f - 1) / f)
                        <= max(a.materiality, abs(amt) * 1e-6)), None)
            if hit:
                rows.append({"key": k, "signal": f"DECIMAL_SHIFT_x{hit}",
                             "priority": PRIORITY,
                             "evidence": f"posting {amt:.2f} is {hit}x a "
                                         f"plausible {amt / hit:.2f}; "
                                         f"gap {gv:.2f} = amt*({hit}-1)/{hit}"})
                break

    st.write_signals("decimal_shift", rows)
    st.record("detect-decimal-shift", params={"materiality": a.materiality,
                                              "factors": list(FACTORS)},
              inputs=["equation", "side:movements"])
    emit({"ok": True, "step": "detect-decimal-shift", "flagged_keys": len(rows),
          "priority": PRIORITY,
          "detail": rows[:5] or None})


if __name__ == "__main__":
    cli(main)
