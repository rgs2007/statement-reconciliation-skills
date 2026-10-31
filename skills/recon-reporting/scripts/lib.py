# ---------------------------------------------------------------------
# VENDORED COPY — DO NOT EDIT.
# Canonical: skills/recon-engine/scripts/lib.py
# VENDORED-FROM-SHA256: 19a5ae27b59194f8ae4e6338328f617c5ab6b92ed44f461fb3d80134b1c4cbdf
# Regenerate: python tools/sync_lib.py   (CI fails if this drifts)
#
# This skill is separately installable, so it carries its own copy
# rather than importing across skills. Editing this file instead of
# the canonical one makes two skills compute different numbers from
# the same input — which is the one failure this toolchain must not
# have. Edit the canonical file and re-run the sync.
# ---------------------------------------------------------------------
#!/usr/bin/env python3
"""Canonical reconciliation arithmetic — the single implementation of every
calculation in this toolchain.

CANONICAL COPY: skills/recon-engine/scripts/lib.py
Vendored into the other skills by `python tools/sync_lib.py`; CI fails if a
copy drifts. Never edit a vendored copy — edit this one and re-sync.

Everything here is deterministic and has no model involvement. The division of
labour across these skills is deliberate: a model decides *which* steps run and
*on what data*, and this file decides *what every number is*. Nothing that
produces a figure lives anywhere else, so two runs over the same inputs cannot
disagree because a different assistant was driving.

Contents
--------
parse_amount   locale-tolerant amount parsing (comma or dot decimals,
               parenthesised negatives, currency symbols)
detect_style   infer the decimal convention from the data
canon          canonical account key; returns None rather than guessing
key_from_text  ordered extraction rules, first match wins
load_side      read one side of a reconciliation: amounts parsed, key derived,
               provenance (sha256, row count) recorded
"""
from __future__ import annotations

import os
import re

import pandas as pd

GENERIC_KEY = re.compile(r"^\s*([A-Za-z0-9]{1,12})\s*[-/ ]\s*(\d{1,4})\b")


# ---------------------------------------------------------------- parsing
def parse_amount(v, style: str | None) -> float:
    s = str(v).strip() if v is not None else ""
    if s == "" or s.lower() == "nan":
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(" ", "")
    s = re.sub(r"[^\d.,\-]", "", s)
    if style == "comma":
        s = s.replace(".", "").replace(",", ".")
    elif style == "dot":
        s = s.replace(",", "")
    else:  # auto: last separator wins as decimal
        if "," in s and "." in s:
            s = (s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".")
                 else s.replace(",", ""))
        elif "," in s:
            s = s.replace(",", ".") if len(s.split(",")[-1]) <= 2 else s.replace(",", "")
    try:
        x = float(s)
    except ValueError:
        return 0.0
    return -x if neg else x


def detect_style(series: pd.Series) -> str | None:
    c = d = 0
    for s in series.head(400).astype(str):
        s = s.strip()
        if re.fullmatch(r"-?[\d.]+,\d{1,2}", s):
            c += 1
        elif re.fullmatch(r"-?[\d,]+\.\d{1,2}", s):
            d += 1
    return None if c == d == 0 else ("comma" if c > d else "dot")


def canon(key) -> str | None:
    """Canonical key: strip leading zeros per segment, uppercase, '-' separator.

    Fails loudly (returns None) rather than guessing - a normaliser that
    guesses will silently merge unrelated accounts in an unfamiliar chart.
    """
    s = str(key or "").strip().upper()
    if not s or s == "NAN":
        return None
    parts = re.split(r"[-/ .]+", s)
    parts = [p for p in parts if p]
    if not parts:
        return None
    out = []
    for p in parts:
        out.append(p.lstrip("0") or "0" if p.isdigit() else p)
    return "-".join(out)


def key_from_text(text: str, rules: list[dict]) -> tuple[str | None, str]:
    t = str(text or "")
    for r in rules:
        pat = r.get("pattern")
        m = GENERIC_KEY.match(t) if pat in (None, "") else re.search(pat, t)
        if m:
            g = [x for x in m.groups() if x]
            return canon("-".join(g) if len(g) > 1 else (g[0] if g else m.group(0))), r.get("name", "R")
    return None, "UNATTRIBUTED"


# ---------------------------------------------------------------- loading
def _sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_side(spec: dict, base: str, style: str | None) -> pd.DataFrame:
    path = spec["path"] if os.path.isabs(spec["path"]) else os.path.join(base, spec["path"])
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.attrs["source"] = {"path": spec["path"], "rows": len(df),
                          "sha256": _sha256(path)}
    st = style or detect_style(df[spec["amount"]])
    df["_amt"] = df[spec["amount"]].map(lambda v: parse_amount(v, st))
    if spec.get("key"):
        df["_key"] = df[spec["key"]].map(canon)
        df["_rule"] = "COLUMN"
    else:
        cols = spec.get("key_from") or []
        rules = spec.get("rules") or [{"name": "S0", "pattern": None}]
        # NB: pandas>=3 keeps NaN through .astype(str); fill first or regexes
        # receive floats and raise TypeError.
        texts = [df[c].fillna("").astype(str) if c in df.columns
                 else pd.Series([""] * len(df)) for c in cols]
        keys, rls = [], []
        for vals in zip(*texts) if texts else []:
            k = r = None
            for v in vals:
                k, r = key_from_text(v, rules)
                if k:
                    break
            keys.append(k)
            rls.append(r if k else "UNATTRIBUTED")
        df["_key"] = keys or None
        df["_rule"] = rls or "UNATTRIBUTED"
    return df

# ======================================================================
# Decision-log core (read side)
#
# Lives here, not only in the recon-decisions skill, because every skill is
# separately installable and the engine must be able to REPLAY a decision log
# on its own — a run whose figures do not match its stated reasons is the one
# output this toolchain must never produce. The recon-decisions skill owns
# *authoring* (append, render, the schema and its UX) and imports this.
#
# The vocabulary is closed on purpose: an agent that needs a decision kind
# which is not listed must raise an open question instead of inventing one.
# ======================================================================
import datetime  # noqa: F401  used by the decision-log core below
import json


KINDS = ["datamap", "ingest", "convention", "attribute", "exclude_scope",
         "include_scope", "tolerance", "classify", "dedupe", "note"]
ACTORS = ["user", "agent", "engine"]
CONF = ["HIGH", "MEDIUM", "LOW"]
REQUIRED = ["id", "ts", "actor", "kind", "statement", "reason", "confidence"]


def load(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path}:{n}: invalid JSON - {e}")
    return out


def validate(entries: list[dict]) -> list[str]:
    """Return a list of problems; empty means valid."""
    errs, seen = [], set()
    for i, d in enumerate(entries, 1):
        tag = d.get("id") or f"line {i}"
        for f in REQUIRED:
            if f not in d or d[f] in (None, "", {}):
                errs.append(f"{tag}: missing required field '{f}'")
        if d.get("kind") not in KINDS:
            errs.append(f"{tag}: kind '{d.get('kind')}' is not in the closed "
                        f"vocabulary {KINDS} - raise an open question instead")
        if d.get("actor") not in ACTORS:
            errs.append(f"{tag}: actor must be one of {ACTORS}")
        if d.get("confidence") not in CONF:
            errs.append(f"{tag}: confidence must be one of {CONF}")
        if not str(d.get("reason", "")).strip():
            errs.append(f"{tag}: empty reason - a decision without a reason "
                        f"is not auditable")
        if d.get("id") in seen:
            errs.append(f"{tag}: duplicate id")
        seen.add(d.get("id"))
        sup = d.get("supersedes")
        if sup and sup not in seen:
            errs.append(f"{tag}: supersedes unknown id '{sup}'")
    return errs


def resolve(entries: list[dict]) -> dict:
    """Fold the log into the effective decision set applied at run time."""
    dead = {d["supersedes"] for d in entries if d.get("supersedes")}
    live = [d for d in entries if d.get("id") not in dead]

    eff: dict = {"exclude_keys": [], "include_keys": [], "attribute": {},
                 "tolerance": None, "convention": None, "dedupe": [],
                 "classify": {}, "counts": {}, "applied": []}
    for d in live:
        k, st = d["kind"], d.get("statement", {})
        if k == "exclude_scope":
            eff["exclude_keys"] += [str(x) for x in st.get("keys", [])]
        elif k == "include_scope":
            eff["include_keys"] += [str(x) for x in st.get("keys", [])]
        elif k == "attribute":
            # {"source_id": "...", "key": "..."} or {"map": {...}}
            if st.get("map"):
                eff["attribute"].update({str(a): str(b) for a, b in st["map"].items()})
            elif st.get("source_id") and st.get("key"):
                eff["attribute"][str(st["source_id"])] = str(st["key"])
        elif k == "tolerance":
            eff["tolerance"] = st.get("materiality", eff["tolerance"])
        elif k == "convention":
            eff["convention"] = st.get("movement_sign", eff["convention"])
        elif k == "dedupe":
            eff["dedupe"].append(st)
        elif k == "classify":
            for key in st.get("keys", []):
                eff["classify"][str(key)] = st.get("category")
        eff["applied"].append({"id": d.get("id"), "kind": k,
                               "actor": d.get("actor"),
                               "confidence": d.get("confidence")})
    # dedupe exclusions, honour later re-inclusion
    eff["exclude_keys"] = [k for k in dict.fromkeys(eff["exclude_keys"])
                           if k not in set(eff["include_keys"])]
    eff["counts"] = {"total": len(entries), "live": len(live),
                     "superseded": len(dead),
                     "by_actor": {a: sum(1 for d in live if d.get("actor") == a)
                                  for a in ACTORS},
                     "by_confidence": {c: sum(1 for d in live if d.get("confidence") == c)
                                       for c in CONF}}
    return eff


def resolve_file(path: str) -> dict:
    """Load, validate and resolve a decision log in one call.

    Refuses to return a partial result: an invalid log raises, because
    silently ignoring a malformed decision would detach the figures from the
    reasons recorded for them.
    """
    entries = load(path)
    problems = validate(entries)
    if problems:
        raise ValueError("decision log is invalid:\n  " + "\n  ".join(problems))
    return resolve(entries)
