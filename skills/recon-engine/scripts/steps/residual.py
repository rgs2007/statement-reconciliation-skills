#!/usr/bin/env python3
"""STEP `residual` — movements whose account could not be derived.

    python steps/residual.py --run runs/r1

Produces: `residual`
Requires: `side:movements`

This is the slice where human or model judgement actually earns its keep, so
it is reported largest-first and with net and gross separated.

A large gross with a near-zero net means offsetting pairs — mechanical noise,
not missing money. A large net is real unexplained value. Before asking the
user about individual rows, look for a recurring pattern: one additional
extraction rule that recovers a whole cluster is worth far more than dozens of
one-by-one mappings.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from steps._state import RunState, cli, emit  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--top", type=int, default=10,
                    help="how many of the largest rows to echo in the result")
    a = ap.parse_args()

    st = RunState(a.run)
    st.require("side:movements")
    mv = st.read_side("side:movements")
    un = mv[mv["_key"].isna()].copy()
    un["amount"] = un["_amt"]
    un = un.sort_values("amount", key=lambda s: s.abs(), ascending=False)

    st.write_table("residual", un)
    st.record("residual", inputs=["side:movements"], outputs=["residual"])

    cols = [c for c in un.columns if not c.startswith("_")]
    emit({"ok": True, "step": "residual",
          "movements_total": int(len(mv)),
          "unattributed": int(len(un)),
          "attribution_rate_pct": round(100 * (1 - len(un) / max(len(mv), 1)), 2),
          "net": round(float(un["_amt"].sum()), 2),
          "gross": round(float(un["_amt"].abs().sum()), 2),
          "largest": un[cols].head(a.top).to_dict("records"),
          "produced": "residual",
          "hint": ("look for a shared pattern across these before asking "
                   "row by row — one extraction rule may recover the cluster"
                   if len(un) else None)})


if __name__ == "__main__":
    cli(main)
