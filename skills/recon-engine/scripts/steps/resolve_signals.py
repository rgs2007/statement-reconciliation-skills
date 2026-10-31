#!/usr/bin/env python3
"""STEP `resolve-signals` — merge the detectors' findings by declared priority.

    python steps/resolve_signals.py --run runs/r1

Produces: `signals`
Requires: `equation`, plus whichever signals/*.csv the detectors wrote

Each detector writes its own file. This step merges them, lowest priority
number winning per key, so **precedence is declared rather than a side effect
of the order the steps happened to run in**.

That matters specifically because the model chooses the order. In a pipeline
where detectors wrote into one shared table, first-match-wins would mean the
same break got a different label depending on an arbitrary sequencing choice —
the kind of bug that produces confident, irreproducible answers. Here the
order is irrelevant: run the detectors in any sequence, or in parallel, and
the resolved signal is identical.

Current priorities (lower wins):
    10  OFFSETTING_SIBLINGS      arithmetically conclusive, no cash impact
    20  DECIMAL_SHIFT_x*         arithmetically conclusive
    30  DUPLICATE_POSTING        strong, but legitimate repeats are possible
    35  PAGEBREAK_SUSPECT        genuinely ambiguous; must be asked about
    60  REVERSAL_PAIR            informational; loses to any real cause
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
    a = ap.parse_args()

    st = RunState(a.run)
    st.require("equation")
    files = st.signal_files()
    frames = []
    for f in files:
        df = pd.read_csv(f, dtype=str, keep_default_na=False)
        if len(df):
            df["_detector"] = os.path.basename(f)[:-4]
            frames.append(df)

    if frames:
        allsig = pd.concat(frames, ignore_index=True)
        allsig["priority"] = pd.to_numeric(allsig["priority"],
                                           errors="coerce").fillna(999)
        allsig = allsig.sort_values(["key", "priority"], kind="stable")
        merged = allsig.drop_duplicates("key", keep="first")
        losers = len(allsig) - len(merged)
    else:
        merged = pd.DataFrame(columns=["key", "signal", "priority",
                                       "evidence", "_detector"])
        losers = 0

    st.write_table("signals", merged)
    st.record("resolve-signals",
              params={"detectors": [os.path.basename(f)[:-4] for f in files]},
              inputs=["equation"], outputs=["signals"])

    emit({"ok": True, "step": "resolve-signals",
          "detectors_run": [os.path.basename(f)[:-4] for f in files],
          "keys_with_signal": int(len(merged)),
          "signals_superseded_by_priority": losers,
          "by_signal": merged["signal"].value_counts().to_dict() if len(merged) else {},
          "produced": "signals",
          "note": "detector order does not affect this result — priority does"})


if __name__ == "__main__":
    cli(main)
