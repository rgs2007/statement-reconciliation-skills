#!/usr/bin/env python3
"""Vendor the canonical arithmetic library into the skills that need it.

The skills are separately installable, so a cross-skill import would break the
moment someone installs one on its own. Each skill therefore carries its own
copy of `lib.py` — and because divergent copies of *executable* code produce
divergent numbers silently, every copy is stamped with the canonical hash and
CI refuses to pass if one drifts.

    python tools/sync_lib.py            # vendor into every consumer
    python tools/sync_lib.py --check    # fail if any copy is stale (CI)
    python tools/sync_lib.py --list     # show canonical + consumers

Canonical: skills/recon-engine/scripts/lib.py
The engine owns the arithmetic because the engine is what computes the figures;
everything else consumes them.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANONICAL = "skills/recon-engine/scripts/lib.py"
CONSUMERS = [
    "skills/recon-discovery/scripts/lib.py",
    "skills/recon-item-matching/scripts/lib.py",
    "skills/recon-decisions/scripts/lib.py",
    "skills/recon-reporting/scripts/lib.py",
]

STAMP = "# VENDORED-FROM-SHA256: "


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_text() -> str:
    p = os.path.join(ROOT, CANONICAL)
    if not os.path.isfile(p):
        raise SystemExit(f"canonical library not found: {CANONICAL}")
    return open(p, encoding="utf-8").read()


def vendored_text(src: str) -> str:
    """The copy, with a banner naming its origin and the hash it was cut from."""
    banner = (
        "# ---------------------------------------------------------------------\n"
        "# VENDORED COPY — DO NOT EDIT.\n"
        f"# Canonical: {CANONICAL}\n"
        f"{STAMP}{digest(src)}\n"
        "# Regenerate: python tools/sync_lib.py   (CI fails if this drifts)\n"
        "#\n"
        "# This skill is separately installable, so it carries its own copy\n"
        "# rather than importing across skills. Editing this file instead of\n"
        "# the canonical one makes two skills compute different numbers from\n"
        "# the same input — which is the one failure this toolchain must not\n"
        "# have. Edit the canonical file and re-run the sync.\n"
        "# ---------------------------------------------------------------------\n"
    )
    return banner + src


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if any vendored copy is stale")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        print(f"canonical: {CANONICAL}")
        for c in CONSUMERS:
            print(f"  -> {c}")
        return

    src = canonical_text()
    want = vendored_text(src)

    if a.check:
        problems = []
        for rel in CONSUMERS:
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p):
                problems.append(f"  MISSING  {rel}")
            elif open(p, encoding="utf-8").read() != want:
                problems.append(f"  STALE    {rel}")
        if problems:
            print("vendored arithmetic is out of sync with "
                  f"{CANONICAL}:")
            print("\n".join(problems))
            print("\nRun: python tools/sync_lib.py")
            sys.exit(1)
        print(f"up to date · {len(CONSUMERS)} vendored copy(ies) match "
              f"{CANONICAL} ({digest(src)[:12]}…)")
        return

    changed = 0
    for rel in CONSUMERS:
        p = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        old = open(p, encoding="utf-8").read() if os.path.exists(p) else None
        if old != want:
            open(p, "w", encoding="utf-8").write(want)
            changed += 1
            print(f"  wrote  {rel}")
        else:
            print(f"  ok     {rel}")
    print(f"\n{changed} of {len(CONSUMERS)} copy(ies) updated from "
          f"{CANONICAL} ({digest(src)[:12]}…)")


if __name__ == "__main__":
    main()
