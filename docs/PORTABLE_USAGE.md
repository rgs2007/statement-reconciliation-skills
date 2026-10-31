<!-- GENERATED FILE — DO NOT EDIT.
     Source: statement-reconciliation/SKILL.md
     Regenerate: python tools/sync_adapters.py
     CI fails if this file is stale. -->

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

> Read `statement-reconciliation/SKILL.md` and follow it to reconcile these statements.
> Open the matching file in `statement-reconciliation/references/` for whichever phase you
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

python statement-reconciliation/scripts/profile_files.py sources/*
python statement-reconciliation/scripts/reconcile.py datamap.json --out runs/run-001 \
       --decisions decisions.jsonl
python statement-reconciliation/scripts/match_items.py left.csv right.csv \
       --amount value --ref doc --out runs/run-001
python statement-reconciliation/scripts/make_report.py runs/run-001 \
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

Edit `statement-reconciliation/SKILL.md`, never an adapter. Duplicated guidance drifts, and
drifted guidance is worse than none — it looks authoritative while being wrong.
