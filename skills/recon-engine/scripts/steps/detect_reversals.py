#!/usr/bin/env python3
"""DETECTOR `detect-reversals` — a posting and its explicit reversal.

    python steps/detect_reversals.py --run runs/r1

Produces: signals/reversals.csv   Requires: `side:movements`
Signal: REVERSAL_PAIR (priority 60 — informational, so it loses to any real cause)

Exact +X / -X pairs on the same key. Large gross, near-zero net. Usually no
action at all: they are activity, not a gap, and reporting them as a gap
overstates the problem.

This is the one detector that does NOT need `equation`: a reversal pair is a
property of the movements alone.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from steps._state import RunState, cli, emit  # noqa: E402

PRIORITY = 60


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--materiality", type=float, default=0.01)
    a = ap.parse_args()

    st = RunState(a.run)
    st.require("side:movements")
    mv = st.read_side("side:movements")

    rows, total_rows, total_amt = [], 0, 0.0
    for k, grp in mv[mv["_key"].notna()].groupby("_key"):
        pos = sorted(round(v, 2) for v in grp["_amt"] if v > 0)
        neg = sorted(-round(v, 2) for v in grp["_amt"] if v < 0)
        i = j = n = 0
        amt = 0.0
        while i < len(pos) and j < len(neg):
            if abs(pos[i] - neg[j]) <= a.materiality:
                n += 2
                amt += pos[i] * 2
                i += 1
                j += 1
            elif pos[i] < neg[j]:
                i += 1
            else:
                j += 1
        if n:
            total_rows += n
            total_amt += amt
            rows.append({"key": k, "signal": "REVERSAL_PAIR",
                         "priority": PRIORITY,
                         "evidence": f"{n} row(s) in exact offsetting pairs, "
                                     f"gross {amt:.2f}, net ~0"})

    st.write_signals("reversals", rows)
    st.record("detect-reversals", params={"materiality": a.materiality},
              inputs=["side:movements"])
    emit({"ok": True, "step": "detect-reversals",
          "reversal_rows": total_rows,
          "reversal_gross": round(total_amt, 2),
          "flagged_keys": len(rows), "priority": PRIORITY,
          "note": "informational: report as gross activity, not as a gap"})


if __name__ == "__main__":
    cli(main)
