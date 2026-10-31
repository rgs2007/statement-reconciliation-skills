#!/usr/bin/env python3
"""Run state shared by the reconciliation steps.

The model decides *which* steps run and *on what data*. The arithmetic lives in
code. This module is what makes that division safe: it holds the artifacts
steps pass between each other, and it refuses to let a step run against state
that is missing or stale.

Why that matters
----------------
A freely-sequenced pipeline has two silent failure modes:

  1. Running a step before its input exists — e.g. detecting duplicates before
     break status is known, which is precisely the gate that stops a clean
     ledger reporting false duplicates.
  2. Running a step against a *stale* input — gaps computed before an exclusion
     decision was applied, then a detector run after it.

Both are caught here rather than left to the caller's discipline. Every step
records the sha256 of each input it consumed; `require()` re-hashes those files
and refuses to proceed if anything moved. A wrong sequence therefore fails
loudly instead of producing a confident wrong number.

State is plain CSV and JSON in a run directory, deliberately: the model can
inspect intermediate state, a human can diff it, and an auditor can read it.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
from typing import Any

import pandas as pd

# Logical artifact name -> (relative path, step that produces it)
ARTIFACTS: dict[str, tuple[str, str]] = {
    # Each side gets its own producer name, so loading three sides writes three
    # manifests instead of overwriting one — otherwise the staleness check
    # could only ever verify whichever side was loaded last.
    "side:opening":   ("sides/opening.csv", "load:opening"),
    "side:closing":   ("sides/closing.csv", "load:closing"),
    "side:movements": ("sides/movements.csv", "load:movements"),
    "decisions":      ("decisions.resolved.json", "decide"),
    "keys":           ("keys.csv", "aggregate"),
    "convention":     ("convention.json", "convention"),
    "equation":       ("equation.csv", "equation"),
    "signals":        ("signals.merged.csv", "resolve-signals"),
    "residual":       ("residual.csv", "residual"),
    "metrics":        ("metrics.json", "summarize"),
}

STEPS_DIR = "_steps"
SIGNALS_DIR = "signals"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


class StaleState(RuntimeError):
    """An input changed after the step that consumed it recorded it."""


class MissingState(RuntimeError):
    """A required artifact has not been produced yet."""


class RunState:
    """Artifacts for one reconciliation run, with precondition enforcement."""

    def __init__(self, run_dir: str) -> None:
        self.dir = os.path.abspath(run_dir)
        os.makedirs(os.path.join(self.dir, STEPS_DIR), exist_ok=True)
        os.makedirs(os.path.join(self.dir, SIGNALS_DIR), exist_ok=True)

    # ------------------------------------------------------------- paths
    def path(self, artifact: str) -> str:
        if artifact not in ARTIFACTS:
            raise KeyError(
                f"unknown artifact {artifact!r}; known: {sorted(ARTIFACTS)}")
        return os.path.join(self.dir, ARTIFACTS[artifact][0])

    def exists(self, artifact: str) -> bool:
        return os.path.exists(self.path(artifact))

    # -------------------------------------------------- preconditions
    def require(self, *artifacts: str) -> None:
        """Refuse to continue unless every artifact exists and is current.

        Raises MissingState naming the step that would produce it, or
        StaleState naming what changed. Both messages are written to be
        actionable by whoever sequenced the run - model or human.
        """
        missing = []
        for a in artifacts:
            if not self.exists(a):
                producer = ARTIFACTS[a][1]
                missing.append(f"  {a!r} - run the '{producer}' step first")
        if missing:
            raise MissingState(
                "this step cannot run yet; missing input(s):\n"
                + "\n".join(missing))

        for a in artifacts:
            self._verify_chain(a)

    def _verify_chain(self, artifact: str) -> None:
        """Check the artifact still matches what its producer recorded."""
        producer = ARTIFACTS[artifact][1]
        man = self.manifest(producer)
        if not man:
            return  # produced outside the step system; nothing to verify
        recorded = (man.get("outputs") or {}).get(artifact)
        if not recorded:
            return
        actual = sha256(self.path(artifact))
        if actual != recorded:
            raise StaleState(
                f"{artifact!r} has changed since the '{producer}' step wrote "
                f"it (recorded {recorded[:12]}…, found {actual[:12]}…). "
                f"Re-run '{producer}' and everything downstream of it, or the "
                f"figures will not correspond to the inputs.")
        # and that the producer's own inputs are still current
        for dep, dep_hash in (man.get("inputs") or {}).items():
            if dep in ARTIFACTS and self.exists(dep):
                if sha256(self.path(dep)) != dep_hash:
                    raise StaleState(
                        f"{artifact!r} was computed from a now-outdated "
                        f"{dep!r}. Re-run '{producer}' and everything "
                        f"downstream, otherwise detectors will be reading "
                        f"stale figures.")

    # ----------------------------------------------------------- tables
    def read_table(self, artifact: str) -> pd.DataFrame:
        self.require(artifact)
        return pd.read_csv(self.path(artifact), dtype=str, keep_default_na=False)

    def read_side(self, artifact: str) -> pd.DataFrame:
        """A loaded side, with numeric `_amt` and nullable `_key` restored."""
        df = self.read_table(artifact)
        df["_amt"] = pd.to_numeric(df["_amt"], errors="coerce").fillna(0.0)
        df["_key"] = df["_key"].replace("", None)
        return df

    def write_table(self, artifact: str, df: pd.DataFrame) -> str:
        p = self.path(artifact)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        df.to_csv(p, index=False)
        return p

    def read_json(self, artifact: str) -> Any:
        self.require(artifact)
        return json.load(open(self.path(artifact), encoding="utf-8"))

    def write_json(self, artifact: str, obj: Any) -> str:
        p = self.path(artifact)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(obj, open(p, "w", encoding="utf-8"), indent=2, default=str)
        return p

    # --------------------------------------------------------- signals
    def write_signals(self, detector: str, rows: list[dict]) -> str:
        """A detector's own findings, kept separate until merged.

        Detectors never write to a shared signal table. Each writes its own
        file with an explicit priority, and `resolve-signals` merges them.
        That makes precedence *declared* rather than a side effect of the
        order the steps happened to run in.
        """
        p = os.path.join(self.dir, SIGNALS_DIR, f"{detector}.csv")
        pd.DataFrame(rows, columns=["key", "signal", "priority", "evidence"]
                     ).to_csv(p, index=False)
        return p

    def signal_files(self) -> list[str]:
        d = os.path.join(self.dir, SIGNALS_DIR)
        return sorted(os.path.join(d, f) for f in os.listdir(d)
                      if f.endswith(".csv"))

    # -------------------------------------------------------- manifests
    def record(self, step: str, *, params: dict | None = None,
               inputs: list[str] | None = None,
               outputs: list[str] | None = None,
               notes: str | None = None) -> dict:
        """Write the step's manifest: what it consumed, produced and with what.

        This is the per-run audit trail of the *flow* - the counterpart to
        decisions.jsonl, which records judgement calls. Together they make a
        model-sequenced run reproducible.
        """
        man = {
            "step": step,
            "ts": _now(),
            "params": params or {},
            "inputs": {a: sha256(self.path(a)) for a in (inputs or [])
                       if self.exists(a)},
            "outputs": {a: sha256(self.path(a)) for a in (outputs or [])
                        if self.exists(a)},
        }
        if notes:
            man["notes"] = notes
        p = os.path.join(self.dir, STEPS_DIR, f"{step}.json")
        json.dump(man, open(p, "w", encoding="utf-8"), indent=2)
        self._append_order(step)
        return man

    def manifest(self, step: str) -> dict | None:
        p = os.path.join(self.dir, STEPS_DIR, f"{step}.json")
        if not os.path.exists(p):
            return None
        return json.load(open(p, encoding="utf-8"))

    def _append_order(self, step: str) -> None:
        p = os.path.join(self.dir, STEPS_DIR, "order.json")
        order = json.load(open(p)) if os.path.exists(p) else []
        order.append({"step": step, "ts": _now()})
        json.dump(order, open(p, "w"), indent=2)

    def executed(self) -> list[str]:
        p = os.path.join(self.dir, STEPS_DIR, "order.json")
        if not os.path.exists(p):
            return []
        return [e["step"] for e in json.load(open(p))]


# ------------------------------------------------------------------ CLI help
def add_common_args(ap) -> None:
    ap.add_argument("--run", required=True,
                    help="run directory holding this reconciliation's state")
    ap.add_argument("--materiality", type=float, default=0.01,
                    help="absolute tolerance below which a gap is reconciled")


def emit(obj: Any) -> None:
    """Steps print JSON so the caller can read the outcome without parsing prose."""
    print(json.dumps(obj, indent=2, default=str))


def cli(main_fn) -> None:
    """Run a step, turning precondition failures into clean JSON.

    The model sequences these steps and reads their output, so an ordering
    mistake has to come back as actionable data rather than a traceback.
    Exit codes: 0 ok, 2 wrong order or stale state, 1 anything else.
    """
    try:
        main_fn()
    except SystemExit:
        raise
    except (MissingState, StaleState) as e:
        emit({"ok": False, "error": type(e).__name__, "message": str(e),
              "fix": "run the step named above, then retry this one"})
        sys.exit(2)
    except Exception as e:  # never leak a traceback to the caller
        emit({"ok": False, "error": type(e).__name__, "message": str(e)})
        sys.exit(1)
