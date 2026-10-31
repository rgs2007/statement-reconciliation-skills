#!/usr/bin/env python3
"""STEP `equation` — compute the per-key gap and status.

    python steps/equation.py --run runs/r1 [--no-movements]

Produces: `equation`
Requires: `keys`, and `convention` unless --no-movements

This is the step every detector depends on, because a detector that runs
before status is known cannot tell a real signal from noise.

    gap = closing - (opening +/- movements)

With `--no-movements` the equation collapses to `closing = opening`, which is
the two-sided comparison: a ledger against a statement, or a sub-ledger
against its control account. No convention is needed because there is nothing
to sign.

Status is RECONCILED within materiality; otherwise BREAK, or a scope status
when the key exists on only one side. Scope mismatch is separated here rather
than mixed into the break list, because it routinely dominates the total and
would otherwise distort every other figure.
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from steps._state import RunState, cli, emit  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--materiality", type=float, default=0.01)
    ap.add_argument("--no-movements", action="store_true",
                    help="two-sided job: test closing = opening")
    a = ap.parse_args()

    st = RunState(a.run)
    st.require("keys")
    k = st.read_table("keys")
    for c in ("opening", "closing", "movements"):
        k[c] = pd.to_numeric(k[c], errors="coerce").fillna(0.0)
    for c in ("in_opening", "in_closing", "in_movements"):
        k[c] = k[c].astype(int)

    if a.no_movements:
        sign, equation = 0, "closing = opening"
    else:
        st.require("convention")
        conv = st.read_json("convention")
        sign = int(conv["movement_sign"])
        equation = conv["equation"]

    k["expected"] = k.opening + sign * k.movements
    k["gap"] = (k.closing - k.expected).round(2)

    status = pd.Series("BREAK", index=k.index)
    status[k.gap.abs() <= a.materiality] = "RECONCILED"
    only_c = (k.in_closing == 1) & (k.in_opening == 0) & (k.in_movements == 0)
    only_o = (k.in_opening == 1) & (k.in_closing == 0) & (k.in_movements == 0)
    only_m = (k.in_movements == 1) & (k.in_opening == 0) & (k.in_closing == 0)
    status[only_c] = "CLOSING_ONLY"
    status[only_o] = "OPENING_ONLY"
    status[only_m] = "MOVEMENT_ONLY"
    k["status"] = status

    st.write_table("equation", k)
    st.record("equation",
              params={"materiality": a.materiality, "equation": equation,
                      "movement_sign": sign},
              inputs=["keys"] + ([] if a.no_movements else ["convention"]),
              outputs=["equation"])

    unrec = k[k.status != "RECONCILED"]
    emit({"ok": True, "step": "equation", "equation": equation,
          "keys_total": int(len(k)),
          "reconciled": int((k.status == "RECONCILED").sum()),
          "reconciled_pct": round(100 * (k.status == "RECONCILED").sum()
                                  / max(len(k), 1), 1),
          "gap_gross": round(float(unrec.gap.abs().sum()), 2),
          "gap_net": round(float(unrec.gap.sum()), 2),
          "by_status": k.status.value_counts().to_dict(),
          "produced": "equation",
          "note": "gross and net answer different questions — gross is how "
                  "much activity is misposted, net is how much value is "
                  "unexplained. Report both."})


if __name__ == "__main__":
    cli(main)
