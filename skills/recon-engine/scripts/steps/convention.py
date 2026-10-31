#!/usr/bin/env python3
"""STEP `convention` — establish the sign convention empirically.

    python steps/convention.py --run runs/r1 [--force-sign -1]

Produces: `convention`
Requires: `keys`

Counts how many keys present on BOTH balance sides reconcile under
`closing = opening + movements` versus `closing = opening - movements`, and
adopts whichever wins. Column names lie about this constantly, so nothing is
inferred from them.

Skip this step only when there are no movements to sign — a two-sided balance
comparison, where the equation is simply `closing = opening`. In that case run
`equation --no-movements` instead.

If the two conventions score alike the convention is NOT established, and the
result says so: something else is wrong (mixed conventions across sub-ledgers,
or movements that are out of scope). Treat a near-tie as a finding, not a
coin toss.
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
    ap.add_argument("--force-sign", type=int, choices=[1, -1],
                    help="override the solve; only with a recorded "
                         "`convention` decision explaining why")
    a = ap.parse_args()

    st = RunState(a.run)
    st.require("keys")
    k = st.read_table("keys")
    for c in ("opening", "closing", "movements"):
        k[c] = pd.to_numeric(k[c], errors="coerce").fillna(0.0)

    shared = k[(k["in_opening"].astype(int) == 1) & (k["in_closing"].astype(int) == 1)]
    plus = int(((shared.closing - (shared.opening + shared.movements)).abs()
                <= a.materiality).sum())
    minus = int(((shared.closing - (shared.opening - shared.movements)).abs()
                 <= a.materiality).sum())
    sign = 1 if plus >= minus else -1
    source = "solved"
    if a.force_sign:
        sign, source = a.force_sign, "forced"

    undecided = abs(plus - minus) < 3
    out = {"movement_sign": sign,
           "equation": "closing = opening + movements" if sign == 1
                       else "closing = opening - movements",
           "source": source,
           "evidence": {"reconciled_with_plus": plus,
                        "reconciled_with_minus": minus,
                        "keys_tested": int(len(shared))},
           "established": not undecided}
    st.write_json("convention", out)
    st.record("convention", params={"materiality": a.materiality,
                                    "force_sign": a.force_sign},
              inputs=["keys"], outputs=["convention"])

    emit({"ok": True, "step": "convention", **out,
          "warning": ("the two conventions score alike, so the convention is "
                      "NOT established — investigate mixed conventions across "
                      "sub-ledgers or out-of-scope movements before trusting "
                      "any gap" if undecided else None)})


if __name__ == "__main__":
    cli(main)
