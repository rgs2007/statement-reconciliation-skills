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

# The read side (vocabulary, load, validate, resolve) is canonical in
# lib.py so that every skill can replay a log independently. This module
# owns AUTHORING: creating entries, rendering them and the CLI.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (ACTORS, CONF, KINDS, REQUIRED, load,  # noqa: E402,F401
                 resolve, resolve_file, validate)


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
