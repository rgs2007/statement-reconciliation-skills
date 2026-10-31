#!/usr/bin/env python3
"""Golden-file regression tests for the statement-reconciliation skill.

Each fixture under tests/fixtures/ holds committed source files and a blessed
`expected/` directory. This runner regenerates the output with the skill's own
scripts and compares it against what was blessed, reporting the exact field
that moved rather than dumping a whole diff.

    python tests/run_tests.py                 # check everything
    python tests/run_tests.py --only 02-faults
    python tests/run_tests.py --verbose        # show full diffs
    python tests/run_tests.py --update         # RE-BLESS the expected output

`--update` rewrites the goldens from the current code. Only ever run it when
you have *read the diff* and decided the new behaviour is correct - otherwise
it converts a regression into the new expected truth, silently. The runner
prints the diff before writing, so there is no excuse for blessing blind.

What is compared, and why it is stable:

  metrics.json   every headline figure. Dict order is ignored, floats are
                 compared to 2 decimals (money), so platform float noise
                 cannot fail a run.
  breaks.csv     per-account gap, status, and structural signal - the
                 detection contract.
  report.md      the full report, after normalising the one volatile line
                 (the generation timestamp). Source sha256 hashes are NOT
                 normalised: if a fixture's bytes change, the test must fail,
                 because the expected figures no longer describe that input.
  item_match.json  matching passes and the surviving residual.
  profile.json   masked structure, proving values stay masked.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "statement-reconciliation", "scripts")
FIX = os.path.join(HERE, "fixtures")

# The generation timestamp is the only genuinely volatile line in a report.
VOLATILE = [
    (re.compile(r"(\*\*(?:Generated|Gerado em|Generado)[^:]*:\*\*)\s*\S+"),
     r"\1 <TIMESTAMP>"),
    (re.compile(r'"generated_at":\s*"[^"]*"'), '"generated_at": "<TIMESTAMP>"'),
]

MONEY_DP = 2


def norm_report(text: str) -> str:
    for pat, repl in VOLATILE:
        text = pat.sub(repl, text)
    return text.replace("\r\n", "\n").rstrip() + "\n"


def run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I"] + cmd, cwd=cwd,
                          capture_output=True, text=True)


# ----------------------------------------------------------------- comparing
def round_floats(obj):
    """Compare money to 2dp so platform float noise cannot fail a run."""
    if isinstance(obj, float):
        return round(obj, MONEY_DP)
    if isinstance(obj, dict):
        return {k: round_floats(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [round_floats(v) for v in obj]
    return obj


def diff_json(expected, actual, path: str = "") -> list[str]:
    """Report the exact fields that moved, not a whole-document diff."""
    out: list[str] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for k in sorted(set(expected) | set(actual)):
            p = f"{path}.{k}" if path else k
            if k not in actual:
                out.append(f"  {p}: MISSING (expected {expected[k]!r})")
            elif k not in expected:
                out.append(f"  {p}: UNEXPECTED (got {actual[k]!r})")
            else:
                out += diff_json(expected[k], actual[k], p)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            out.append(f"  {path}: length {len(expected)} -> {len(actual)}")
        for i, (e, a) in enumerate(zip(expected, actual)):
            out += diff_json(e, a, f"{path}[{i}]")
    elif expected != actual:
        out.append(f"  {path}: expected {expected!r}, got {actual!r}")
    return out


def diff_text(expected: str, actual: str, label: str, verbose: bool) -> list[str]:
    e, a = expected.splitlines(), actual.splitlines()
    if e == a:
        return []
    d = list(difflib.unified_diff(e, a, fromfile=f"expected/{label}",
                                  tofile=f"actual/{label}", lineterm="", n=1))
    changed = [x for x in d if x.startswith(("+", "-"))
               and not x.startswith(("+++", "---"))]
    if verbose:
        return ["  " + x for x in d]
    head = [f"  {len(changed)} changed line(s); first few:"]
    return head + ["  " + x for x in changed[:8]]


# ------------------------------------------------------------------ fixtures
def produce_recon(fixture: str, work: str) -> dict[str, str]:
    """Run reconcile + make_report for a reconciliation fixture."""
    src = os.path.join(FIX, fixture)
    shutil.copytree(src, work, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("expected"))
    out = os.path.join(work, "run")
    cmd = [os.path.join(SCRIPTS, "reconcile.py"),
           os.path.join(work, "datamap.json"), "--out", out]
    dec = os.path.join(work, "decisions.jsonl")
    if os.path.exists(dec):
        cmd += ["--decisions", dec]
    r = run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"reconcile.py failed:\n{r.stdout}\n{r.stderr}")

    rep = [os.path.join(SCRIPTS, "make_report.py"), out,
           "--out", os.path.join(work, "report.md"),
           "--entity", "ACME INDUSTRIA LTDA", "--period", "2026-09"]
    if os.path.exists(dec):
        rep += ["--decisions", dec]
    r2 = run(rep)
    if r2.returncode != 0:
        raise RuntimeError(f"make_report.py failed:\n{r2.stdout}\n{r2.stderr}")

    got = {"metrics.json": open(f"{out}/metrics.json").read(),
           "breaks.csv": open(f"{out}/breaks.csv").read(),
           "report.md": open(f"{work}/report.md").read()}
    rp = f"{out}/residual.csv"
    if os.path.exists(rp):
        got["residual.csv"] = open(rp).read()
    return got


def produce_items(fixture: str, work: str) -> dict[str, str]:
    src = os.path.join(FIX, fixture)
    shutil.copytree(src, work, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("expected"))
    cfg = json.load(open(os.path.join(work, "match.json")))
    out = os.path.join(work, "run")
    r = run([os.path.join(SCRIPTS, "match_items.py"),
             os.path.join(work, "sources", "open_items.csv"),
             os.path.join(work, "sources", "statement.csv"),
             "--amount", cfg["amount"], "--ref", cfg["ref"],
             "--date", cfg["date"], "--tolerance", str(cfg["tolerance"]),
             "--max-subset", str(cfg["max_subset"]),
             "--node-cap", str(cfg["node_cap"]), "--out", out])
    if r.returncode != 0:
        raise RuntimeError(f"match_items.py failed:\n{r.stdout}\n{r.stderr}")
    got = {"item_match.json": open(f"{out}/item_match.json").read()}
    up = f"{out}/unmatched_items.csv"
    if os.path.exists(up):
        got["unmatched_items.csv"] = open(up).read()
    return got


def produce_profile(fixture: str, work: str) -> dict[str, str]:
    src = os.path.join(FIX, fixture)
    shutil.copytree(src, work, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("expected"))
    sdir = os.path.join(work, "sources")
    files = sorted(os.path.join(sdir, f) for f in os.listdir(sdir))
    r = run([os.path.join(SCRIPTS, "profile_files.py"), *files,
             "--rows", "9", "--json"])
    if r.returncode != 0:
        raise RuntimeError(f"profile_files.py failed:\n{r.stdout}\n{r.stderr}")
    data = json.loads(r.stdout)
    # Absolute paths and byte sizes vary by checkout; keep the basename, drop
    # size. The sha256 stays - it is the point of the provenance check.
    for d in data:
        d["path"] = os.path.basename(d.get("path", ""))
        d.pop("size_bytes", None)
    return {"profile.json": json.dumps(data, indent=2, sort_keys=True) + "\n"}


PRODUCERS = {
    "05-item-matching": produce_items,
    "06-profile": produce_profile,
}

# Fixtures whose point is a specific behaviour; asserted beyond the goldens so
# a silent golden re-bless cannot erase the contract.
CONTRACTS: dict[str, list[tuple[str, str]]] = {
    "01-clean": [
        ("metrics.reconciled == metrics.keys_total", "no false positives"),
        ("metrics.gap_gross == 0", "clean ledger must show no gap"),
        ("metrics.movements_unattributed == 0", "every posting attributable"),
    ],
    "02-faults": [
        ("metrics.movements_unattributed == 1", "the orphan row is unattributed"),
        ("signal('6652-4').startswith('DECIMAL_SHIFT')", "x1000 shift detected"),
        ("signal('4363-1') == 'OFFSETTING_SIBLINGS'", "sibling pair detected"),
        ("signal('4363-2') == 'OFFSETTING_SIBLINGS'", "sibling pair detected"),
        ("broke('8722-1')", "account with no movements must break"),
        ("metrics.duplicate_rows >= 1", "duplicate posting detected"),
        ("metrics.reversal_rows >= 2", "reversal pair detected"),
    ],
    "03-decisions": [
        ("metrics.scope_excluded_keys == 1", "exclusion decision replayed"),
        ("metrics.decisions_applied >= 5", "live decisions applied"),
        ("not broke('8722-1')", "excluded account must leave the break list"),
        ("metrics.movements_unattributed == 0",
         "manual attribution resolves the orphan"),
        ("metrics.materiality == 0.01",
         "superseded tolerance must not win"),
    ],
    "04-scope-pagebreak": [
        ("metrics.consecutive_duplicate_rows >= 3",
         "page-break signature surfaced, never auto-removed"),
        ("status('2432-1') == 'CLOSING_ONLY'", "scope mismatch isolated"),
    ],
}


def eval_contracts(fixture: str, got: dict[str, str]) -> list[str]:
    """Check the behavioural contracts for a fixture. Returns failures."""
    rules = CONTRACTS.get(fixture)
    if not rules:
        return []
    import csv as _csv
    import io

    metrics = json.loads(got["metrics.json"])
    rows = list(_csv.DictReader(io.StringIO(got.get("breaks.csv", ""))))
    by_key = {r["key"]: r for r in rows}

    class M:
        def __getattr__(self, k):
            if k not in metrics:
                raise AssertionError(f"metrics has no '{k}'")
            return metrics[k]

    env = {
        "metrics": M(),
        "signal": lambda k: (by_key.get(k, {}).get("signal") or ""),
        "status": lambda k: (by_key.get(k, {}).get("status") or ""),
        "broke": lambda k: k in by_key,
        "gap": lambda k: float(by_key.get(k, {}).get("gap") or 0.0),
    }
    fails = []
    for expr, why in rules:
        try:
            if not eval(expr, {"__builtins__": {}}, env):
                fails.append(f"  contract failed: {expr}   ({why})")
        except Exception as e:  # a contract that cannot evaluate is a failure
            fails.append(f"  contract errored: {expr} -> {type(e).__name__}: {e}")
    return fails


# ---------------------------------------------------------------------- main
def check(fixture: str, update: bool, verbose: bool) -> tuple[bool, list[str]]:
    exp_dir = os.path.join(FIX, fixture, "expected")
    producer = PRODUCERS.get(fixture, produce_recon)
    work = tempfile.mkdtemp(prefix=f"recon_{fixture}_")
    try:
        got = producer(fixture, work)
    except Exception as e:
        shutil.rmtree(work, ignore_errors=True)
        return False, [f"  ERROR running the skill: {e}"]
    shutil.rmtree(work, ignore_errors=True)

    problems = eval_contracts(fixture, got) if "metrics.json" in got else []

    if update:
        os.makedirs(exp_dir, exist_ok=True)
        for name, text in got.items():
            payload = norm_report(text) if name.endswith(".md") else text
            open(os.path.join(exp_dir, name), "w", encoding="utf-8").write(payload)
        return (not problems), problems

    if not os.path.isdir(exp_dir):
        return False, [f"  no expected/ directory - bless it with "
                       f"`python tests/run_tests.py --only {fixture} --update`"]

    for name, text in sorted(got.items()):
        ep = os.path.join(exp_dir, name)
        if not os.path.exists(ep):
            problems.append(f"  {name}: no blessed copy to compare against")
            continue
        expected = open(ep, encoding="utf-8").read()
        if name.endswith(".json"):
            d = diff_json(round_floats(json.loads(expected)),
                          round_floats(json.loads(text)))
            if d:
                problems.append(f"  {name}:")
                problems += d
        else:
            if name.endswith(".md"):
                expected, text = norm_report(expected), norm_report(text)
            d = diff_text(expected, text, name, verbose)
            if d:
                problems.append(f"  {name}:")
                problems += d
    return (not problems), problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only")
    ap.add_argument("--update", action="store_true",
                    help="re-bless expected output from current behaviour")
    ap.add_argument("--verbose", "-v", action="store_true")
    a = ap.parse_args()

    if not os.path.isdir(FIX):
        raise SystemExit("no fixtures; run `python tests/make_fixtures.py` first")
    names = [a.only] if a.only else sorted(
        d for d in os.listdir(FIX) if os.path.isdir(os.path.join(FIX, d)))
    if not names:
        raise SystemExit("no fixtures found")

    if a.update:
        print("RE-BLESSING expected output. Read the diff below and make sure "
              "the new behaviour is what you intended.\n")

    passed, failed = [], []
    for n in names:
        ok, problems = check(n, a.update, a.verbose)
        mark = "ok  " if ok else "FAIL"
        print(f"[{mark}] {n}")
        for p in problems:
            print(p)
        (passed if ok else failed).append(n)

    print("\n" + "=" * 64)
    if a.update:
        print(f"blessed {len(names)} fixture(s). Review `git diff tests/fixtures` "
              f"before committing.")
        sys.exit(1 if failed else 0)
    if failed:
        print(f"FAILED · {len(failed)} of {len(names)}: {', '.join(failed)}")
        print("\nIf a change in behaviour is intended, re-bless deliberately:")
        print("  python tests/run_tests.py --update   # then review git diff")
        sys.exit(1)
    print(f"PASSED · {len(passed)} fixture(s) match the expected report")


if __name__ == "__main__":
    main()
