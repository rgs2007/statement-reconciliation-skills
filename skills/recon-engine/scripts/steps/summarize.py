#!/usr/bin/env python3
"""STEP `summarize` — assemble metrics, and report what the plan did NOT do.

    python steps/summarize.py --run runs/r1 --out runs/r1/legacy

Produces: `metrics`, plus breaks.csv / residual.csv in --out for the reporter
Requires: `equation`

Emits the same metrics shape as the one-shot engine, so the existing report
generator consumes a step-sequenced run unchanged.

It also reports **coverage**: which steps ran and which did not. In a pipeline
the model sequences, a step silently skipped is the main risk — figures that
look complete but had no duplicate detection, or no decision replay, behind
them. `coverage` and `caveats` make that visible in the output rather than
leaving the reader to assume.
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from steps._state import RunState, cli, emit  # noqa: E402

EXPECTED_DETECTORS = ["detect-siblings", "detect-decimal-shift",
                      "detect-duplicates", "detect-reversals"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--materiality", type=float, default=0.01)
    ap.add_argument("--out", help="also write breaks.csv/residual.csv/"
                                  "metrics.json here, for make_report.py")
    a = ap.parse_args()

    st = RunState(a.run)
    st.require("equation")
    eq = st.read_table("equation")
    for c in ("opening", "closing", "movements", "expected", "gap"):
        eq[c] = pd.to_numeric(eq[c], errors="coerce").fillna(0.0)

    executed = st.executed()
    conv = st.read_json("convention") if st.exists("convention") else {}
    eff = st.read_json("decisions") if st.exists("decisions") else {}

    brk = eq[eq.status != "RECONCILED"].copy()
    if st.exists("signals"):
        sig = st.read_table("signals")[["key", "signal"]]
        brk = brk.merge(sig, on="key", how="left")
    brk["signal"] = brk.get("signal", pd.Series(dtype=str)).fillna("")
    brk = brk.sort_values("gap", key=lambda s: s.abs(), ascending=False)

    def parent(k: str) -> str:
        return k.rsplit("-", 1)[0] if "-" in k else k

    pr = brk.assign(p=brk.key.map(parent)).groupby("p")["gap"].sum()

    res_rows = res_net = res_gross = 0
    if st.exists("residual"):
        rdf = st.read_table("residual")
        amt = pd.to_numeric(rdf.get("amount", pd.Series(dtype=float)),
                            errors="coerce").fillna(0.0)
        res_rows, res_net, res_gross = len(rdf), float(amt.sum()), float(amt.abs().sum())

    mv_total = 0
    rule_cov: dict = {}
    if st.exists("side:movements"):
        mv = st.read_side("side:movements")
        mv_total = len(mv)
        rule_cov = mv["_rule"].value_counts().to_dict()

    datasets = []
    for role in ("opening", "closing", "movements"):
        man = st.manifest(f"load:{role}")
        if man:
            p = (man.get("params") or {})
            datasets.append({"role": role, "path": p.get("path"),
                             "amount": p.get("amount")})

    skipped = [d for d in EXPECTED_DETECTORS if d not in executed]
    caveats = []
    if "decide" not in executed:
        caveats.append("No decision log was applied: these figures reflect no "
                       "recorded judgement calls.")
    for d in skipped:
        caveats.append(f"'{d}' did not run, so that cause was not tested for.")
    if conv and not conv.get("established", True):
        caveats.append("The sign convention is not established — the two "
                       "conventions scored alike. Treat every gap as "
                       "provisional until that is resolved.")

    metrics = {
        "keys_total": int(len(eq)),
        "reconciled": int((eq.status == "RECONCILED").sum()),
        "reconciled_pct": round(100 * (eq.status == "RECONCILED").sum()
                                / max(len(eq), 1), 1),
        "sign_convention": conv.get("equation", "closing = opening"),
        "convention_evidence": conv.get("evidence", {}),
        "gap_gross": round(float(brk.gap.abs().sum()), 2),
        "gap_net": round(float(brk.gap.sum()), 2),
        "scope_only": {s: int((eq.status == s).sum())
                       for s in ("CLOSING_ONLY", "OPENING_ONLY", "MOVEMENT_ONLY")},
        "movements_total": mv_total,
        "movements_unattributed": int(res_rows),
        "attribution_rate_pct": round(100 * (1 - res_rows / max(mv_total, 1)), 2),
        "residual_net": round(res_net, 2),
        "residual_gross": round(res_gross, 2),
        "rule_coverage": rule_cov,
        "materiality": a.materiality,
        "datasets": datasets,
        "decisions_applied": len(eff.get("applied") or []),
        "scope_excluded_keys": len(eff.get("exclude_keys") or []),
        "gap_gross_at_parent": round(float(pr.abs().sum()), 2),
        "parents_netting_to_zero": int((pr.abs() <= a.materiality).sum()),
        "coverage": {"steps_executed": executed, "detectors_skipped": skipped},
        "caveats": caveats,
    }
    st.write_json("metrics", metrics)
    st.record("summarize", params={"materiality": a.materiality},
              inputs=["equation"], outputs=["metrics"])

    if a.out:
        os.makedirs(a.out, exist_ok=True)
        brk.to_csv(os.path.join(a.out, "breaks.csv"), index=False)
        import json as _json
        _json.dump(metrics, open(os.path.join(a.out, "metrics.json"), "w"),
                   indent=2, default=str)
        if st.exists("residual"):
            st.read_table("residual").to_csv(
                os.path.join(a.out, "residual.csv"), index=False)

    emit({"ok": True, "step": "summarize", "metrics": metrics,
          "wrote_report_inputs_to": a.out,
          "next": "run recon-reporting's make_report.py on --out to produce "
                  "the auditable report"})


if __name__ == "__main__":
    cli(main)
