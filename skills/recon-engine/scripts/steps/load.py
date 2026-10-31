#!/usr/bin/env python3
"""STEP `load` — read one side of the reconciliation into run state.

    python steps/load.py --run runs/r1 --role opening \\
        --path sources/opening.csv --amount saldo \\
        --key-from account_description

Produces: `side:<role>`
Requires: nothing

Call it once per side you actually have. A roll-forward reconciliation loads
three (opening, closing, movements); a two-sided comparison loads two; a
balance-only confirmation loads two with no detail. Nothing here assumes which.

The arithmetic — amount parsing, decimal-style detection, key extraction and
canonicalisation — is imported from reconcile.py, which stays the single
implementation of every calculation in this toolchain.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import detect_style, load_side  # noqa: E402  canonical arithmetic
from steps._state import RunState, cli, emit  # noqa: E402

ROLES = ("opening", "closing", "movements", "left", "right")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--role", required=True,
                    help="opening | closing | movements (left/right are "
                         "aliases for a two-sided job)")
    ap.add_argument("--path", required=True, help="source file")
    ap.add_argument("--amount", required=True, help="column holding the amount")
    ap.add_argument("--key", help="column holding the account key")
    ap.add_argument("--key-from", nargs="*", default=None,
                    help="text column(s) to extract the key from, in order")
    ap.add_argument("--rules", help="JSON list of extraction rules; default is "
                                    "the generic 'key at head of field' rule")
    ap.add_argument("--decimal-style", choices=["comma", "dot"],
                    help="omit to infer from the data")
    a = ap.parse_args()

    role = {"left": "opening", "right": "closing"}.get(a.role, a.role)
    if role not in ("opening", "closing", "movements"):
        raise SystemExit(f"--role must be one of {ROLES}")

    spec: dict = {"path": os.path.abspath(a.path), "amount": a.amount}
    if a.key:
        spec["key"] = a.key
    else:
        if not a.key_from:
            raise SystemExit(
                "give either --key (a dedicated key column) or --key-from "
                "(text column(s) to extract it from). Try --key-from first "
                "with the generic rule: most exports put the key at the head "
                "of the description.")
        spec["key_from"] = list(a.key_from)
        if a.rules:
            import json
            spec["rules"] = json.loads(a.rules)

    st = RunState(a.run)
    df = load_side(spec, base=os.getcwd(), style=a.decimal_style)
    src = df.attrs.get("source", {})
    artifact = f"side:{role}"
    st.write_table(artifact, df)
    inferred = a.decimal_style or detect_style(df[a.amount]) or "ambiguous"

    unattr = int(df["_key"].isna().sum())
    st.record(f"load:{role}",
              params={"role": role, **spec,
                      "decimal_style": a.decimal_style or "inferred"},
              outputs=[artifact])

    emit({"ok": True, "step": f"load:{role}", "role": role,
          "rows": len(df), "sum": round(float(df["_amt"].sum()), 2),
          "decimal_style": inferred,
          "keys_distinct": int(df["_key"].nunique(dropna=True)),
          "rows_without_key": unattr,
          "rule_coverage": df["_rule"].value_counts().to_dict(),
          "source": src,
          "produced": artifact,
          "hint": ("some rows have no derivable key; they will show up as "
                   "residual. Check the extraction rules before treating the "
                   "gap as real." if unattr else None)})


if __name__ == "__main__":
    cli(main)
