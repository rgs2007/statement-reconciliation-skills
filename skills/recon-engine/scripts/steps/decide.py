#!/usr/bin/env python3
"""STEP `decide` — resolve the decision log and apply it to the loaded sides.

    python steps/decide.py --run runs/r1 --decisions decisions.jsonl

Produces: `decisions` (the resolved, effective decision set), and rewrites the
          loaded sides with manual attributions and scope exclusions applied
Requires: at least one `side:*`

Run this after `load` and before `aggregate`. Skipping it is legitimate on a
first pass — a baseline run with no decisions yet — but once a decision log
exists, every later step must see its effects, which is why the sides are
rewritten here rather than each step consulting the log itself.

Omitting it when a log exists is the classic way to publish figures that do not
match the stated reasons, so the summarize step reports whether it ran.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import canon  # noqa: E402  canonical arithmetic
from steps._state import RunState, cli, emit  # noqa: E402

SIDES = ("side:opening", "side:closing", "side:movements")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--decisions", help="path to decisions.jsonl; omit for a "
                                        "baseline run with no decisions yet")
    a = ap.parse_args()

    st = RunState(a.run)
    present = [s for s in SIDES if st.exists(s)]
    if not present:
        raise SystemExit("no sides loaded yet — run the 'load' step first")

    eff: dict = {}
    problems: list[str] = []
    if a.decisions and os.path.exists(a.decisions):
        import lib
        entries = lib.load(a.decisions)
        problems = lib.validate(entries)
        if problems:
            raise SystemExit("decision log is invalid; fix it before running:\n  "
                             + "\n  ".join(problems))
        eff = lib.resolve(entries)

    manual = {k: canon(v) for k, v in (eff.get("attribute") or {}).items()}
    excl = {canon(k) for k in (eff.get("exclude_keys") or [])} - {None}

    applied = {"manual_attributions": 0, "rows_excluded": 0}
    for art in present:
        df = st.read_side(art)
        if manual and "source_id" in df.columns:
            sid = df["source_id"].fillna("").astype(str)
            hit = sid.isin(manual)
            df.loc[hit, "_key"] = sid[hit].map(manual)
            df.loc[hit, "_rule"] = "MANUAL"
            applied["manual_attributions"] += int(hit.sum())
        if excl:
            hit = df["_key"].isin(excl)
            df.loc[hit, "_key"] = None
            applied["rows_excluded"] += int(hit.sum())
        st.write_table(art, df)

    st.write_json("decisions", eff)
    # The sides are rewritten, so their load manifests are now stale by
    # design. Re-record them against this step so the chain stays verifiable.
    for art in present:
        role = art.split(":", 1)[1]
        prev = st.manifest(f"load:{role}") or {}
        st.record(f"load:{role}", params=prev.get("params", {}),
                  outputs=[art],
                  notes="rewritten by the 'decide' step")
    st.record("decide",
              params={"decisions": a.decisions, "sides": present},
              inputs=present, outputs=["decisions"])

    emit({"ok": True, "step": "decide",
          "decisions_live": len((eff.get("applied") or [])),
          "exclude_keys": sorted(x for x in excl),
          "manual_attributions": len(manual),
          "tolerance_override": eff.get("tolerance"),
          "convention_override": eff.get("convention"),
          "applied": applied,
          "produced": "decisions",
          "note": ("no decision log supplied — this is a baseline run"
                   if not eff else None)})


if __name__ == "__main__":
    cli(main)
