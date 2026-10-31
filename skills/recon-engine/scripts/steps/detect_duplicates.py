#!/usr/bin/env python3
"""DETECTOR `detect-duplicates` — a posting recorded more than once.

    python steps/detect_duplicates.py --run runs/r1

Produces: signals/duplicates.csv   Requires: `equation`, `side:movements`
Signals: DUPLICATE_POSTING (priority 30), PAGEBREAK_SUSPECT (priority 35)

Two things make this detector honest rather than noisy.

**Id-like columns are excluded from the signature.** A genuine duplicate
posting almost always carries a DIFFERENT row id, so including the id finds
nothing at all.

**Only accounts that actually BREAK are suspect.** If a balance ties exactly,
a repeated row cannot be a spurious extra posting — an extra posting would
break the balance — so the rows are legitimate repeated instalments. That
resolves the duplicate-vs-instalment ambiguity in the common case. Where the
account does break the ambiguity genuinely remains, which is why adjacent
repeats are reported as PAGEBREAK_SUSPECT at LOW confidence and never removed
automatically: de-duplicating real instalments turns a correct reconciliation
into a wrong one.

This detector therefore REQUIRES `equation`. Running it earlier is not merely
premature, it reintroduces false positives on clean ledgers — which is why
_state.py refuses to let that happen.
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from steps._state import RunState, cli, emit  # noqa: E402

ID_TOKENS = ("id", "seq", "line", "row", "uuid", "guid")


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
    g = dict(zip(brk.key, brk.gap))
    mv = st.read_side("side:movements")

    sig_cols = [c for c in mv.columns
                if not c.startswith("_")
                and not any(t in str(c).lower() for t in ID_TOKENS)]
    sig_cols = sig_cols or [c for c in mv.columns if not c.startswith("_")]
    sig = mv[sig_cols].astype(str).agg("|".join, axis=1)

    broken = set(brk.key)
    suspect = mv["_key"].isna() | mv["_key"].isin(broken)
    dmask = sig.duplicated(keep="first") & suspect
    consec = (sig == sig.shift()) & suspect

    rows = []
    for k, grp in mv[dmask & mv["_key"].notna()].groupby("_key"):
        if k not in g:
            continue
        dup_val = float(grp["_amt"].abs().sum())
        if abs(abs(g[k]) - dup_val) > a.materiality:
            continue
        adjacent = bool(consec.reindex(grp.index).fillna(False).any())
        rows.append({
            "key": k,
            "signal": "PAGEBREAK_SUSPECT" if adjacent else "DUPLICATE_POSTING",
            "priority": 35 if adjacent else 30,
            "evidence": f"{len(grp)} repeated row(s) totalling {dup_val:.2f} "
                        f"equal this account's gap; repeats are "
                        f"{'adjacent' if adjacent else 'non-adjacent'}"})

    st.write_signals("duplicates", rows)
    st.record("detect-duplicates", params={"materiality": a.materiality},
              inputs=["equation", "side:movements"])
    emit({"ok": True, "step": "detect-duplicates",
          "duplicate_rows": int(dmask.sum()),
          "duplicate_gross": round(float(mv.loc[dmask, "_amt"].abs().sum()), 2),
          "consecutive_duplicate_rows": int(consec.sum()),
          "flagged_keys": len(rows),
          "detail": rows[:5] or None,
          "warning": ("consecutive duplicate rows found — these may be a "
                      "paginated-source artifact OR real instalments. Ask the "
                      "user; never de-duplicate automatically."
                      if int(consec.sum()) else None)})


if __name__ == "__main__":
    cli(main)
