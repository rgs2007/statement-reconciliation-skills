"""The composable steps must agree with the one-shot engine, exactly.

This is the test that protects the architecture the repo is built on: a model
chooses *which* steps run and *on what data*, and code decides *what every
number is*. If sequencing the steps by hand produced different figures from
`reconcile.py`, that division would be a fiction — the flow would be silently
affecting the arithmetic.

It also pins the three properties that make model-chosen ordering safe:

  * preconditions   a step run too early fails loudly, with exit code 2
  * staleness       a step refuses to read an artifact that changed underneath it
  * precedence      detector order does not affect the resolved signal
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STEPS = os.path.join(ROOT, "skills", "recon-engine", "scripts", "steps")
ENGINE = os.path.join(ROOT, "skills", "recon-engine", "scripts", "reconcile.py")
FIXTURE = os.path.join(HERE, "fixtures", "02-faults")

DETECTORS = ["detect_siblings", "detect_decimal_shift",
             "detect_duplicates", "detect_reversals"]

# Figures that must be identical between the two interfaces. `coverage` and
# `caveats` are deliberately excluded: they describe the *plan*, which is the
# one thing that legitimately differs between a one-shot and a stepped run.
COMPARED = ["keys_total", "reconciled", "reconciled_pct", "sign_convention",
            "gap_gross", "gap_net", "scope_only", "movements_total",
            "movements_unattributed", "attribution_rate_pct", "residual_net",
            "residual_gross", "rule_coverage", "gap_gross_at_parent",
            "parents_netting_to_zero"]


def step(name: str, *args: str, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", os.path.join(STEPS, f"{name}.py"), *args],
        capture_output=True, text=True, cwd=cwd)


def load_sides(work: str, run: str) -> None:
    for role, path, amount, keyfrom in (
        ("opening", "sources/opening.csv", "saldo_inicial", ["account_description"]),
        ("closing", "sources/closing.csv", "saldo_final", ["account_description"]),
        ("movements", "sources/movements.csv", "valor", ["historico1", "historico2"]),
    ):
        r = step("load", "--run", run, "--role", role, "--path", path,
                 "--amount", amount, "--key-from", *keyfrom,
                 "--decimal-style", "comma", cwd=work)
        assert r.returncode == 0, f"load {role} failed:\n{r.stdout}{r.stderr}"


@pytest.fixture()
def work():
    d = tempfile.mkdtemp(prefix="recon_steps_")
    shutil.copytree(FIXTURE, d, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("expected"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def run_full_plan(work: str, run: str = "run",
                  detector_order: list[str] | None = None) -> dict:
    load_sides(work, run)
    for name in ("aggregate", "convention", "equation"):
        r = step(name, "--run", run, cwd=work)
        assert r.returncode == 0, f"{name} failed:\n{r.stdout}{r.stderr}"
    for d in (detector_order or DETECTORS):
        r = step(d, "--run", run, cwd=work)
        assert r.returncode == 0, f"{d} failed:\n{r.stdout}{r.stderr}"
    for name in ("resolve_signals", "residual"):
        r = step(name, "--run", run, cwd=work)
        assert r.returncode == 0, f"{name} failed:\n{r.stdout}{r.stderr}"
    r = step("summarize", "--run", run, "--out", f"{run}/out", cwd=work)
    assert r.returncode == 0, f"summarize failed:\n{r.stdout}{r.stderr}"
    return json.load(open(os.path.join(work, run, "metrics.json")))


def test_steps_match_the_one_shot_engine(work) -> None:
    stepped = run_full_plan(work)

    r = subprocess.run([sys.executable, "-I", ENGINE, "datamap.json",
                        "--out", "oneshot"], capture_output=True, text=True,
                       cwd=work)
    assert r.returncode == 0, f"reconcile.py failed:\n{r.stdout}{r.stderr}"
    oneshot = json.load(open(os.path.join(work, "oneshot", "metrics.json")))

    diffs = [f"{k}: one-shot {oneshot.get(k)!r} vs stepped {stepped.get(k)!r}"
             for k in COMPARED if oneshot.get(k) != stepped.get(k)]
    assert not diffs, (
        "the composable steps disagree with the one-shot engine, so the flow "
        "is affecting the arithmetic:\n  " + "\n  ".join(diffs))


def test_detector_order_does_not_change_the_result(work) -> None:
    """Precedence is declared by priority, not by call order."""
    forward = run_full_plan(work, run="a", detector_order=DETECTORS)
    reverse = run_full_plan(work, run="b",
                            detector_order=list(reversed(DETECTORS)))
    a = open(os.path.join(work, "a", "signals.merged.csv")).read()
    b = open(os.path.join(work, "b", "signals.merged.csv")).read()
    assert a == b, "resolved signals changed when the detectors ran in reverse"
    assert {k: forward[k] for k in COMPARED} == {k: reverse[k] for k in COMPARED}


def test_detector_before_equation_is_refused(work) -> None:
    """A step run too early must fail loudly, not produce a wrong number."""
    load_sides(work, "run")
    r = step("detect_duplicates", "--run", "run", cwd=work)
    assert r.returncode == 2, (
        f"expected exit 2 for a missing precondition, got {r.returncode}")
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert out["error"] == "MissingState"
    assert "equation" in out["message"], (
        "the error must name the artifact that is missing")


def test_equation_before_convention_is_refused(work) -> None:
    load_sides(work, "run")
    assert step("aggregate", "--run", "run", cwd=work).returncode == 0
    r = step("equation", "--run", "run", cwd=work)
    assert r.returncode == 2
    assert "convention" in json.loads(r.stdout)["message"]


def test_two_sided_job_needs_no_convention(work) -> None:
    """closing = opening, for a bank-rec style comparison with no movements."""
    for role, path, amount in (("opening", "sources/opening.csv", "saldo_inicial"),
                               ("closing", "sources/closing.csv", "saldo_final")):
        assert step("load", "--run", "two", "--role", role, "--path", path,
                    "--amount", amount, "--key-from", "account_description",
                    "--decimal-style", "comma", cwd=work).returncode == 0
    assert step("aggregate", "--run", "two", cwd=work).returncode == 0
    r = step("equation", "--run", "two", "--no-movements", cwd=work)
    assert r.returncode == 0, f"two-sided equation failed:\n{r.stdout}{r.stderr}"
    out = json.loads(r.stdout)
    assert out["equation"] == "closing = opening"
    assert out["keys_total"] > 0


def test_stale_upstream_is_refused(work) -> None:
    """A detector must not read gaps that changed after they were computed."""
    load_sides(work, "run")
    for name in ("aggregate", "convention", "equation"):
        assert step(name, "--run", "run", cwd=work).returncode == 0
    eq = os.path.join(work, "run", "equation.csv")
    with open(eq, "a", encoding="utf-8") as fh:
        fh.write("TAMPER-9,0,0,0,0,0,0,0,0,BREAK\n")
    r = step("detect_siblings", "--run", "run", cwd=work)
    assert r.returncode == 2, "a tampered upstream artifact must be refused"
    assert json.loads(r.stdout)["error"] == "StaleState"


def test_summarize_reports_skipped_detectors(work) -> None:
    """A cause not tested for must not look like a cause ruled out."""
    load_sides(work, "run")
    for name in ("aggregate", "convention", "equation"):
        assert step(name, "--run", "run", cwd=work).returncode == 0
    assert step("detect_siblings", "--run", "run", cwd=work).returncode == 0
    assert step("resolve_signals", "--run", "run", cwd=work).returncode == 0
    assert step("summarize", "--run", "run", cwd=work).returncode == 0
    m = json.load(open(os.path.join(work, "run", "metrics.json")))
    skipped = m["coverage"]["detectors_skipped"]
    assert "detect-duplicates" in skipped and "detect-decimal-shift" in skipped
    assert any("detect-duplicates" in c for c in m["caveats"]), (
        "a skipped detector must appear in the caveats, not just in coverage")
    assert any("No decision log" in c for c in m["caveats"])
