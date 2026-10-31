#!/usr/bin/env python3
"""Self-test: build a clean ledger, inject known faults, assert detection.

Two checks that matter in opposite directions:

  CONTROL  a clean, internally consistent ledger must reconcile 100% with
           zero findings - proving the engine invents no false positives.
  FAULTS   five deliberately injected defects must each surface, and the
           structural detectors must name the two that are arithmetically
           provable.

Run this after changing any script, and to demonstrate the toolchain works
before pointing it at real data.

Usage
-----
    python selftest.py [--keep]        # --keep leaves the fixtures on disk
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# A small double-entry ledger: opening, movements, closing. Sums to zero.
ACCOUNTS = [
    ("1000-01", "BANK OPERATING",        600193.40,   83098.68),
    ("1100-01", "ACCOUNTS RECEIVABLE",   214503.34,   85280.59),
    ("1400-01", "SALES TAX RECEIVABLE",   42539.68,    8006.67),
    ("2000-01", "ACCOUNTS PAYABLE",      -59022.49,   13202.36),
    ("2100-01", "SALES TAX PAYABLE",    -111039.10,  -23200.00),
    ("2000-02", "ACCRUED EXPENSES",      -20849.25,   -1773.07),
    ("3000-01", "OWNERS EQUITY",        -200000.00,       0.00),
    ("4000-01", "SALES REVENUE",       -1480520.14, -309332.22),
    ("5000-01", "COST OF GOODS SOLD",    567198.67,  106756.03),
    ("6000-01", "SALARIES AND WAGES",    521227.06,   44326.43),
    ("6100-01", "EMPLOYER TAX EXPENSE",   20849.25,    1773.07),
    ("6800-01", "DEPRECIATION EXPENSE",    7317.20,     731.72),
]


def br(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def write_fixture(d: str, faulty: bool) -> None:
    """Write the fixture with a real CSV writer.

    Comma-decimal values must be quoted or they split into extra columns -
    a mistake worth making once, here, rather than on client data.
    """
    import csv
    os.makedirs(d, exist_ok=True)
    op, cl, mv = [], [], []
    for i, (key, name, opening, movement) in enumerate(ACCOUNTS):
        desc = f"{key} -{name}"
        closing = opening + movement
        op.append([i + 1, desc, br(opening)])
        cl.append([desc, br(closing)])
        parts = [round(movement / 3, 2)] * 2
        parts.append(round(movement - sum(parts), 2))
        for j, p in enumerate(parts):
            if faulty and key == "1400-01":
                continue                                    # F1 MISSING_MOVEMENTS
            val = p
            if faulty and key == "6800-01" and j == 0:
                val = p * 1000                              # F2 DECIMAL_SHIFT
            tgt = desc
            if faulty and key == "2000-02" and j == 0:
                tgt = "2000-01 -ACCOUNTS PAYABLE"           # F3 MISATTRIBUTION
            mv.append([br(val), tgt, "POSTING", f"mv_{i}_{j}"])
    if faulty:
        mv.append(mv[0][:3] + ["mv_DUP"])                   # F4 DUPLICATE
        mv.append([br(12345.67), "MISC ADJUSTMENT NO KEY", "", "mv_ORPHAN"])

    def dump(path, header, rows):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)

    dump(f"{d}/opening.csv", ["id", "account", "balance"], op)
    dump(f"{d}/closing.csv", ["account", "balance"], cl)
    dump(f"{d}/movements.csv", ["value", "desc1", "desc2", "source_id"], mv)
    json.dump({
        "opening":   {"path": "opening.csv", "key_from": ["account"], "amount": "balance"},
        "closing":   {"path": "closing.csv", "key_from": ["account"], "amount": "balance"},
        "movements": {"path": "movements.csv", "key_from": ["desc1", "desc2"],
                      "amount": "value", "rules": [{"name": "S0", "pattern": None}]},
        "decimal_style": "comma",
    }, open(f"{d}/datamap.json", "w"), indent=2)


def run_engine(d: str, out: str) -> dict:
    r = subprocess.run([sys.executable, os.path.join(HERE, "reconcile.py"),
                        f"{d}/datamap.json", "--out", out, "--materiality", "0.01"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit("engine failed")
    return json.load(open(os.path.join(out, "metrics.json")))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="recon_selftest_")
    failures = []

    try:
        # ---- CONTROL
        write_fixture(f"{tmp}/clean", faulty=False)
        m = run_engine(f"{tmp}/clean", f"{tmp}/run_clean")
        print("CONTROL  clean ledger")
        print(f"  reconciled {m['reconciled']}/{m['keys_total']} ({m['reconciled_pct']}%)"
              f" · gap {m['gap_gross']} · unattributed {m['movements_unattributed']}")
        if m["reconciled"] != m["keys_total"]:
            failures.append(f"control: expected all {m['keys_total']} reconciled, "
                            f"got {m['reconciled']}")
        if abs(m["gap_gross"]) > 0.01:
            failures.append(f"control: expected zero gap, got {m['gap_gross']}")
        if m["movements_unattributed"]:
            failures.append(f"control: expected 0 unattributed, "
                            f"got {m['movements_unattributed']}")
        if m["sign_convention"] != "closing = opening + movements":
            failures.append(f"control: sign convention wrongly solved as "
                            f"{m['sign_convention']}")

        # ---- FAULTS
        write_fixture(f"{tmp}/faulty", faulty=True)
        m2 = run_engine(f"{tmp}/faulty", f"{tmp}/run_faulty")
        import pandas as pd
        b = pd.read_csv(f"{tmp}/run_faulty/breaks.csv")
        sig = dict(zip(b.key.astype(str), b.signal.fillna("")))
        print("\nFAULTS   five injected defects")
        print(f"  reconciled {m2['reconciled']}/{m2['keys_total']} · "
              f"breaks {len(b)} · unattributed {m2['movements_unattributed']}")
        print(f"  signals: { {k: v for k, v in sig.items() if v} }")

        # the engine canonicalises keys (1400-01 -> 1400-1); assert on that form
        expect_break = ["1400-1", "6800-1", "2000-1", "2000-2"]
        for k in expect_break:
            if k not in sig:
                failures.append(f"faults: expected {k} to break, it did not")
        if m2["movements_unattributed"] != 1:
            failures.append(f"faults: expected exactly 1 unattributed, "
                            f"got {m2['movements_unattributed']}")
        if not sig.get("6800-1", "").startswith("DECIMAL_SHIFT"):
            failures.append("faults: DECIMAL_SHIFT not detected on 6800-1")
        if sig.get("2000-1") != "OFFSETTING_SIBLINGS" or \
           sig.get("2000-2") != "OFFSETTING_SIBLINGS":
            failures.append("faults: OFFSETTING_SIBLINGS not detected on 2000-1/2000-2")
        if not m2.get("duplicate_rows"):
            failures.append("faults: duplicate posting not detected")

        # ---- decision replay
        dpath = f"{tmp}/decisions.jsonl"
        sys.path.insert(0, HERE)
        import decisions as dec
        dec.append(dpath, actor="user", kind="exclude_scope",
                   statement={"keys": ["1400-01"]},
                   reason="Tax receivable is reconciled separately by the tax team.",
                   confidence="HIGH", evidence={"gap": 8006.67})
        if dec.validate(dec.load(dpath)):
            failures.append("decisions: freshly appended entry failed validation")
        r = subprocess.run([sys.executable, os.path.join(HERE, "reconcile.py"),
                            f"{tmp}/faulty/datamap.json", "--out", f"{tmp}/run_dec",
                            "--decisions", dpath], capture_output=True, text=True)
        m3 = json.load(open(f"{tmp}/run_dec/metrics.json"))
        print("\nREPLAY   decision log applied")
        print(f"  excluded {m3['scope_excluded_keys']} key(s) · "
              f"gap {m2['gap_gross']} -> {m3['gap_gross']}")
        if m3["scope_excluded_keys"] != 1:
            failures.append("replay: exclusion decision was not applied")
        if m3["gap_gross"] >= m2["gap_gross"]:
            failures.append("replay: excluding a broken account did not reduce the gap")

        # ---- report
        r = subprocess.run([sys.executable, os.path.join(HERE, "make_report.py"),
                            f"{tmp}/run_faulty", "--decisions", dpath,
                            "--out", f"{tmp}/report.md"],
                           capture_output=True, text=True)
        ok = os.path.exists(f"{tmp}/report.md") and r.returncode == 0
        print(f"\nREPORT   generated: {ok}")
        if not ok:
            failures.append(f"report generation failed: {r.stderr[:200]}")
        else:
            txt = open(f"{tmp}/report.md").read()
            for need in ("SUBACCOUNT_MISATTRIBUTION", "DECIMAL_SHIFT", "Glossary"):
                if need not in txt:
                    failures.append(f"report: missing expected section/code '{need}'")

    finally:
        if a.keep:
            print(f"\nfixtures kept in {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED · {len(failures)} problem(s)")
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("PASSED · control clean, all five faults detected, replay and report OK")


if __name__ == "__main__":
    sys.exit(main())
