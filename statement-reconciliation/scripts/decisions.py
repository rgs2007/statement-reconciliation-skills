#!/usr/bin/env python3
"""Decision log: validate, append, resolve and replay.

This is what makes the audit claim true. `decisions.jsonl` is append-only;
`resolve()` folds it into an effective decision set (later wins, `supersedes`
respected) which `reconcile.py` applies on every run. The numbers and the
stated reasons therefore cannot drift apart.

Usage
-----
    python decisions.py validate  decisions.jsonl
    python decisions.py show      decisions.jsonl [--lang es]
    python decisions.py history   decisions.jsonl
    python decisions.py resolve   decisions.jsonl            # effective JSON
    python decisions.py append    decisions.jsonl --kind exclude_scope \\
        --actor user --reason "Loans live in treasury" \\
        --statement '{"keys":["2432-01"]}' --confidence HIGH \\
        --evidence '{"balance":250000000}'

Never edit or delete a line. To reverse a decision, append a new one with
--supersedes pointing at the old id.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

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


def next_id(entries: list[dict]) -> str:
    n = 0
    for d in entries:
        i = str(d.get("id", ""))
        if i.startswith("d-") and i[2:].isdigit():
            n = max(n, int(i[2:]))
    return f"d-{n + 1:04d}"


def append(path: str, **kw) -> dict:
    entries = load(path)
    entry = {"id": kw.get("id") or next_id(entries),
             "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
             "actor": kw["actor"], "kind": kw["kind"],
             "statement": kw["statement"], "reason": kw["reason"],
             "confidence": kw["confidence"]}
    for opt in ("evidence", "impact", "supersedes", "run_id"):
        if kw.get(opt):
            entry[opt] = kw[opt]
    errs = validate(entries + [entry])
    errs = [e for e in errs if e.startswith(entry["id"])]
    if errs:
        raise SystemExit("refusing to append:\n  " + "\n  ".join(errs))
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def render(entries: list[dict], history: bool = False) -> str:
    """Human-readable view. Reasons appear in whatever language they were written."""
    if history:
        lines = ["# Decision history (chronological)", ""]
        for d in entries:
            sup = f"  [supersedes {d['supersedes']}]" if d.get("supersedes") else ""
            lines += [f"## {d.get('id')} · {d.get('kind')} · {d.get('actor')} · "
                      f"{d.get('confidence')}{sup}",
                      f"- when: {d.get('ts')}",
                      f"- what: {json.dumps(d.get('statement'), ensure_ascii=False)}",
                      f"- why: {d.get('reason')}"]
            if d.get("evidence"):
                lines.append(f"- evidence: {json.dumps(d['evidence'], ensure_ascii=False)}")
            if d.get("impact"):
                lines.append(f"- impact: {json.dumps(d['impact'], ensure_ascii=False)}")
            lines.append("")
        return "\n".join(lines)

    eff = resolve(entries)
    c = eff["counts"]
    lines = ["# Effective decisions", "",
             f"{c['live']} live of {c['total']} ({c['superseded']} superseded)",
             f"by actor: {c['by_actor']}",
             f"by confidence: {c['by_confidence']}", ""]
    if eff["convention"] is not None:
        lines.append(f"- convention: movement_sign = {eff['convention']}")
    if eff["tolerance"] is not None:
        lines.append(f"- materiality: {eff['tolerance']}")
    if eff["exclude_keys"]:
        lines.append(f"- excluded from scope ({len(eff['exclude_keys'])}): "
                     f"{', '.join(eff['exclude_keys'][:12])}"
                     + (" …" if len(eff["exclude_keys"]) > 12 else ""))
    if eff["attribute"]:
        lines.append(f"- manual attributions: {len(eff['attribute'])}")
    if eff["dedupe"]:
        lines.append(f"- dedupe rules: {len(eff['dedupe'])}")
    if eff["classify"]:
        lines.append(f"- manual classifications: {len(eff['classify'])}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["validate", "show", "history", "resolve", "append"])
    ap.add_argument("path")
    for f in ("kind", "actor", "reason", "confidence", "statement",
              "evidence", "impact", "supersedes", "run_id", "id"):
        ap.add_argument(f"--{f}")
    a = ap.parse_args()

    entries = load(a.path)
    if a.command == "validate":
        errs = validate(entries)
        if errs:
            print(f"INVALID - {len(errs)} problem(s):")
            for e in errs:
                print("  " + e)
            sys.exit(1)
        print(f"valid · {len(entries)} decision(s)")
    elif a.command == "show":
        print(render(entries))
    elif a.command == "history":
        print(render(entries, history=True))
    elif a.command == "resolve":
        print(json.dumps(resolve(entries), indent=2, ensure_ascii=False))
    elif a.command == "append":
        missing = [f for f in ("kind", "actor", "reason", "confidence", "statement")
                   if not getattr(a, f)]
        if missing:
            raise SystemExit(f"append requires: {', '.join('--' + m for m in missing)}")
        e = append(a.path, kind=a.kind, actor=a.actor, reason=a.reason,
                   confidence=a.confidence, statement=json.loads(a.statement),
                   evidence=json.loads(a.evidence) if a.evidence else None,
                   impact=json.loads(a.impact) if a.impact else None,
                   supersedes=a.supersedes, run_id=a.run_id, id=a.id)
        print(json.dumps(e, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
