#!/usr/bin/env python3
"""Generate tool adapters from the canonical SKILL.md.

Every AI coding tool looks for instructions in a different place, with a
different format. Rather than maintain six copies of the same guidance — which
would drift within a week — `statement-reconciliation/SKILL.md` stays the
single source of truth, and this script renders the adapters from the blocks it
marks with `<!-- shared:NAME -->` HTML comments (invisible when rendered).

    python tools/sync_adapters.py            # regenerate every adapter
    python tools/sync_adapters.py --check    # fail if any is stale (CI)
    python tools/sync_adapters.py --list     # show what gets written where

Generated files carry a "do not edit" banner. Edit SKILL.md and re-run.

Why each target exists
----------------------
AGENTS.md                               the cross-tool standard: Codex CLI,
                                        Copilot, Cursor, Gemini CLI/Jules,
                                        Windsurf, Amp, Devin, Aider, OpenCode,
                                        goose, Junie, Zed, Warp, Factory
CLAUDE.md                               Claude Code does not read AGENTS.md
.github/copilot-instructions.md         Copilot, repository-wide
.github/instructions/*.instructions.md  Copilot path-scoped (`applyTo` globs)
.cursor/rules/*.mdc                     Cursor's own rule format
docs/PORTABLE_USAGE.md                  any other tool, and humans

Path rewriting matters: inside an installed skill the scripts sit at
`scripts/`, but from a repo checkout they are at
`statement-reconciliation/scripts/`. Adapters are repo-rooted, so the
references are rewritten on the way out.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = "statement-reconciliation"
SKILL = os.path.join(ROOT, SKILL_DIR, "SKILL.md")

BANNER = ("<!-- GENERATED FILE — DO NOT EDIT.\n"
          "     Source: {src}\n"
          "     Regenerate: python tools/sync_adapters.py\n"
          "     CI fails if this file is stale. -->")


# --------------------------------------------------------------- extraction
def read_skill() -> str:
    if not os.path.isfile(SKILL):
        raise SystemExit(f"canonical skill not found: {SKILL}")
    return open(SKILL, encoding="utf-8").read()


def frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit("SKILL.md has no YAML frontmatter")
    out: dict[str, str] = {}
    key = None
    for line in m.group(1).splitlines():
        km = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if km:
            key, val = km.group(1), km.group(2)
            out[key] = val
        elif key and line.strip():
            out[key] += " " + line.strip()
    return out


def block(text: str, name: str) -> str:
    """Lift one `<!-- shared:NAME -->` region, with paths rewritten."""
    m = re.search(rf"<!--\s*shared:{re.escape(name)}\s*-->\n(.*?)\n<!--\s*/shared:{re.escape(name)}\s*-->",
                  text, re.S)
    if not m:
        raise SystemExit(
            f"SKILL.md has no '<!-- shared:{name} -->' block. The adapters are "
            f"generated from these markers; add it or update MARKERS in this script.")
    return rewrite_paths(m.group(1).strip())


def rewrite_paths(s: str) -> str:
    """Make skill-relative paths work from the repository root."""
    for pat, repl in (
        (r"`scripts/", f"`{SKILL_DIR}/scripts/"),
        (r"`references/", f"`{SKILL_DIR}/references/"),
        (r"`templates/", f"`{SKILL_DIR}/templates/"),
        (r"(?<!/)\bpython scripts/", f"python {SKILL_DIR}/scripts/"),
    ):
        s = re.sub(pat, repl, s)
    return s


MARKERS = ["core-rules", "workflow", "decision-log", "scripts", "traps"]


# ------------------------------------------------------------------ renderers
def common_body(text: str, *, include: list[str]) -> str:
    return "\n\n".join(block(text, n) for n in include)


def pointer_note(depth: str = "") -> str:
    return (
        f"The full method lives in [`{SKILL_DIR}/SKILL.md`]({SKILL_DIR}/SKILL.md) "
        f"and its `references/` directory — one file per phase:\n\n"
        f"| Phase | Read |\n|---|---|\n"
        f"| Discovery — profiling, locating keys | `{SKILL_DIR}/references/discovery.md` |\n"
        f"| Intake — Excel/PDF → clean tabular | `{SKILL_DIR}/references/intake.md` |\n"
        f"| Matching — conventions, gaps, rollup | `{SKILL_DIR}/references/matching.md` |\n"
        f"| Taxonomy — 12 root causes | `{SKILL_DIR}/references/taxonomy.md` |\n"
        f"| Confidence — HIGH/MEDIUM/LOW rubric | `{SKILL_DIR}/references/confidence.md` |\n"
        f"| Reporting — auditable structure | `{SKILL_DIR}/references/reporting.md` |\n\n"
        f"Open the reference for the phase you are in. Do not try to hold all "
        f"six in context at once.")


def render_agents(text: str, fm: dict) -> str:
    return f"""{BANNER.format(src=f"{SKILL_DIR}/SKILL.md")}

# AGENTS.md — Statement Reconciliation

This repository is a portable, tool-agnostic skill for reconciling financial
statements that do not tie out, and explaining every discrepancy with evidence,
rationale and a confidence level.

## When this applies

{fm['description']}

{common_body(text, include=["core-rules", "workflow"])}

## Where the detail is

{pointer_note()}

{common_body(text, include=["decision-log", "scripts", "traps"])}

## Verifying your environment

```bash
pip install -r requirements.txt
python {SKILL_DIR}/scripts/selftest.py   # must print PASSED
python tests/run_tests.py                # golden-file regression suite
```

Run the self-test before trusting the toolchain on real data. It builds a clean
ledger that must reconcile 100% with zero findings, then injects five known
defects that must all surface.
"""


def render_claude(text: str, fm: dict) -> str:
    return f"""{BANNER.format(src=f"{SKILL_DIR}/SKILL.md")}

# CLAUDE.md

Claude Code does not read `AGENTS.md`, so this file carries the same guidance.
[`AGENTS.md`](AGENTS.md) is the tool-agnostic copy; both are generated from
[`{SKILL_DIR}/SKILL.md`]({SKILL_DIR}/SKILL.md).

## Preferred: install as a skill

This repository *is* a skill. Installed, it triggers on description alone with
no instruction file needed:

```bash
mkdir -p .claude/skills && cp -r {SKILL_DIR} .claude/skills/   # this project
mkdir -p ~/.claude/skills && cp -r {SKILL_DIR} ~/.claude/skills/  # everywhere
```

This file is the fallback for working *on* the repository, or when the skill is
not installed.

## When this applies

{fm['description']}

{common_body(text, include=["core-rules", "workflow"])}

## Where the detail is

{pointer_note()}

{common_body(text, include=["decision-log", "scripts", "traps"])}

## Working on this repository

Changing a script means re-running both suites, and the golden fixtures are
deliberately strict:

```bash
python tests/run_tests.py                 # read any diff before blessing
python tests/run_tests.py --update        # only after deciding it is correct
python {SKILL_DIR}/scripts/selftest.py
python tools/sync_adapters.py --check     # adapters must match SKILL.md
```

Editing `SKILL.md` requires `python tools/sync_adapters.py` — every other
instruction file in this repo is generated from it, and CI fails if they drift.
"""


def render_copilot(text: str, fm: dict) -> str:
    return f"""{BANNER.format(src=f"{SKILL_DIR}/SKILL.md")}

# Copilot instructions — Statement Reconciliation

Repository-wide custom instructions. Copilot loads this automatically; `@`
file references below are followed, so the full method is one hop away.

## When this applies

{fm['description']}

{common_body(text, include=["core-rules", "workflow"])}

## Read the phase reference before acting

@{SKILL_DIR}/SKILL.md

{pointer_note()}

{common_body(text, include=["decision-log", "scripts", "traps"])}

## Checks

```bash
python {SKILL_DIR}/scripts/selftest.py
python tests/run_tests.py
```
"""


def render_copilot_pathspec(text: str, fm: dict) -> str:
    # NB: `@` references are NOT expanded in *.instructions.md, so this file
    # must stand on its own and name the paths in prose instead.
    return f"""---
applyTo: "**/*.csv,**/datamap.json,**/decisions.jsonl,{SKILL_DIR}/**,tests/**"
description: "Reconciliation method, decision-log rules and script usage"
---

{BANNER.format(src=f"{SKILL_DIR}/SKILL.md")}

# Reconciliation work in this repository

These instructions apply when touching ledger data, a datamap, a decision log,
the skill itself, or its tests.

File references are not expanded in this kind of instructions file, so open
these yourself when you need them:
`{SKILL_DIR}/SKILL.md` for the full method, and
`{SKILL_DIR}/references/<phase>.md` for discovery, intake, matching, taxonomy,
confidence and reporting.

{common_body(text, include=["core-rules", "workflow", "decision-log", "scripts", "traps"])}
"""


def render_cursor(text: str, fm: dict) -> str:
    return f"""---
description: "Statement reconciliation — method, decision log, scripts"
globs: ["**/*.csv","**/datamap.json","**/decisions.jsonl","{SKILL_DIR}/**","tests/**"]
alwaysApply: false
---

{BANNER.format(src=f"{SKILL_DIR}/SKILL.md")}

# Statement Reconciliation

{fm['description']}

{common_body(text, include=["core-rules", "workflow"])}

## Where the detail is

@{SKILL_DIR}/SKILL.md

{pointer_note()}

{common_body(text, include=["decision-log", "scripts", "traps"])}
"""


def render_portable(text: str, fm: dict) -> str:
    return f"""{BANNER.format(src=f"{SKILL_DIR}/SKILL.md")}

# Using this skill with any AI tool

The skill is plain Markdown plus plain Python. Nothing in it is specific to one
assistant, so it works anywhere — the only thing that differs between tools is
*where they look* for instructions.

## Tools with a native instruction file

Generated adapters are committed, so these work on checkout with no setup:

| Tool | Reads | Status |
|---|---|---|
| Claude Code | `CLAUDE.md`, or install as a skill | committed |
| GitHub Copilot | `.github/copilot-instructions.md` + `.github/instructions/` | committed |
| Codex CLI, Cursor, Windsurf, Gemini CLI/Jules, Amp, Devin, Aider, OpenCode, goose, Junie, Zed, Warp, Factory | `AGENTS.md` | committed |
| Cursor (native rules) | `.cursor/rules/statement-reconciliation.mdc` | committed |

Claude Code is the one tool that does not read `AGENTS.md`, which is why
`CLAUDE.md` exists alongside it. Both are generated from the same source.

## Any other tool

Two routes, in order of preference.

**1. Point it at the skill.** Most agentic tools can read a file on request:

> Read `{SKILL_DIR}/SKILL.md` and follow it to reconcile these statements.
> Open the matching file in `{SKILL_DIR}/references/` for whichever phase you
> are in.

**2. Paste the operating brief.** For a tool with no file access, paste
`AGENTS.md` as a system prompt. It is self-contained: the non-negotiable rules,
the six-phase workflow, the decision-log contract, the script commands and the
known traps.

## The scripts work with no AI at all

This matters for CI, for scheduled runs, and for anyone who simply wants the
arithmetic. The deterministic engine needs no model:

```bash
pip install -r requirements.txt

python {SKILL_DIR}/scripts/profile_files.py sources/*
python {SKILL_DIR}/scripts/reconcile.py datamap.json --out runs/run-001 \\
       --decisions decisions.jsonl
python {SKILL_DIR}/scripts/match_items.py left.csv right.csv \\
       --amount value --ref doc --out runs/run-001
python {SKILL_DIR}/scripts/make_report.py runs/run-001 \\
       --decisions decisions.jsonl --lang pt --out report.md
```

What an AI adds is the parts a script cannot do: interviewing the user about
what only they can see, choosing between explanations that fit the same
evidence, and writing the rationale. The figures, the detection and the audit
trail come from the scripts either way — which is also why the output is
reproducible regardless of which assistant was driving.

## A note on languages

The agent replies in whatever language the user writes in. Category codes
(`MISSING_MOVEMENTS`, `SCOPE_MISMATCH`, …) and confidence labels
(`HIGH`/`MEDIUM`/`LOW`) deliberately stay in English so tooling and audit
trails remain stable across languages; the report carries a glossary.

`make_report.py` has translated section headings for `en`, `pt` and `es`, and
falls back to English headings elsewhere, which the agent then translates. Pass
`--lang`.

## Keeping the adapters honest

Every file in the table above is generated:

```bash
python tools/sync_adapters.py          # regenerate
python tools/sync_adapters.py --check  # CI gate: fails if stale
```

Edit `{SKILL_DIR}/SKILL.md`, never an adapter. Duplicated guidance drifts, and
drifted guidance is worse than none — it looks authoritative while being wrong.
"""


TARGETS: list[tuple[str, callable]] = [
    ("AGENTS.md", render_agents),
    ("CLAUDE.md", render_claude),
    (".github/copilot-instructions.md", render_copilot),
    (".github/instructions/reconciliation.instructions.md", render_copilot_pathspec),
    (".cursor/rules/statement-reconciliation.mdc", render_cursor),
    ("docs/PORTABLE_USAGE.md", render_portable),
]


# ---------------------------------------------------------------------- main
def build_all() -> dict[str, str]:
    text = read_skill()
    fm = frontmatter(text)
    out = {}
    for rel, fn in TARGETS:
        body = fn(text, fm)
        out[rel] = body.replace("\r\n", "\n").rstrip() + "\n"
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if any adapter is stale; writes nothing")
    ap.add_argument("--list", action="store_true", help="list targets and exit")
    a = ap.parse_args()

    if a.list:
        print(f"canonical source: {SKILL_DIR}/SKILL.md")
        print(f"shared blocks:    {', '.join(MARKERS)}")
        for rel, _ in TARGETS:
            print(f"  -> {rel}")
        return

    built = build_all()

    if a.check:
        stale, missing = [], []
        for rel, body in built.items():
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p):
                missing.append(rel)
            elif open(p, encoding="utf-8").read() != body:
                stale.append(rel)
        if missing or stale:
            if missing:
                print("MISSING adapter(s):")
                for m in missing:
                    print(f"  {m}")
            if stale:
                print("STALE adapter(s) — SKILL.md changed but these were not "
                      "regenerated:")
                for s in stale:
                    print(f"  {s}")
            print("\nRun: python tools/sync_adapters.py")
            sys.exit(1)
        print(f"up to date · {len(built)} adapter(s) match {SKILL_DIR}/SKILL.md")
        return

    changed = []
    for rel, body in built.items():
        p = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        old = open(p, encoding="utf-8").read() if os.path.exists(p) else None
        if old != body:
            open(p, "w", encoding="utf-8").write(body)
            changed.append(rel)
        print(f"  {'wrote  ' if old != body else 'ok     '} {rel}")
    print(f"\n{len(changed)} of {len(built)} adapter(s) updated from "
          f"{SKILL_DIR}/SKILL.md")


if __name__ == "__main__":
    main()
