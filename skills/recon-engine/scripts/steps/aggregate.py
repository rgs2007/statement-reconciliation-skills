#!/usr/bin/env python3
"""STEP `aggregate` — sum each loaded side per canonical account key.

    python steps/aggregate.py --run runs/r1

Produces: `keys`
Requires: at least one `side:*`

Takes the union of keys across whichever sides are present, so an account that
appears on only one side still gets a row — that is how scope mismatch becomes
visible instead of silently vanishing. Sides that were not loaded are reported
as zero and flagged in `sides_present`, which downstream steps use to decide
what the equation can legitimately claim.
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from steps._state import RunState, cli, emit  # noqa: E402

SIDES = ("opening", "closing", "movements")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    a = ap.parse_args()

    st = RunState(a.run)
    present = [s for s in SIDES if st.exists(f"side:{s}")]
    if not present:
        raise SystemExit("no sides loaded yet — run the 'load' step first")

    sums: dict[str, pd.Series] = {}
    membership: dict[str, set] = {}
    for s in present:
        df = st.read_side(f"side:{s}")
        keyed = df[df["_key"].notna()]
        sums[s] = keyed.groupby("_key")["_amt"].sum()
        membership[s] = set(sums[s].index)

    keys = sorted(set().union(*membership.values())) if membership else []
    out = pd.DataFrame({"key": keys})
    for s in SIDES:
        out[s] = (sums[s].reindex(keys).fillna(0.0).values
                  if s in sums else 0.0)
        out[f"in_{s}"] = [int(k in membership.get(s, set())) for k in keys]

    st.write_table("keys", out)
    st.record("aggregate", params={"sides_present": present},
              inputs=[f"side:{s}" for s in present], outputs=["keys"])

    emit({"ok": True, "step": "aggregate",
          "sides_present": present,
          "sides_missing": [s for s in SIDES if s not in present],
          "keys_total": len(keys),
          "keys_on_one_side_only": int(sum(
              1 for k in keys
              if sum(int(k in membership.get(s, set())) for s in present) == 1)),
          "totals": {s: round(float(sums[s].sum()), 2) for s in present},
          "produced": "keys"})


if __name__ == "__main__":
    cli(main)
