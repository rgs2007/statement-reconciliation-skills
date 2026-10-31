"""Pytest wrapper around the golden-file runner.

The runner in `run_tests.py` is the primary entry point and needs nothing but
pandas, so the tests work in a restricted environment. This shim exists so
`pytest tests/` works too, and so CI gets per-fixture reporting.

    pytest tests/ -v
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIX = os.path.join(HERE, "fixtures")

sys.path.insert(0, HERE)
import run_tests  # noqa: E402


def fixtures() -> list[str]:
    if not os.path.isdir(FIX):
        return []
    return sorted(d for d in os.listdir(FIX)
                  if os.path.isdir(os.path.join(FIX, d)))


@pytest.mark.parametrize("fixture", fixtures())
def test_matches_expected_report(fixture: str) -> None:
    """Current output must match the blessed expected report."""
    ok, problems = run_tests.check(fixture, update=False, verbose=True)
    assert ok, f"{fixture} diverged from its expected report:\n" + "\n".join(problems)


def test_every_fixture_has_expected_output() -> None:
    """A fixture with no blessed output is not a test."""
    missing = [f for f in fixtures()
               if not os.path.isdir(os.path.join(FIX, f, "expected"))]
    assert not missing, f"fixtures with no expected/ directory: {missing}"


def test_skill_selftest_passes() -> None:
    """The skill's own bundled self-test must pass independently."""
    script = os.path.join(ROOT, "statement-reconciliation", "scripts",
                          "selftest.py")
    r = subprocess.run([sys.executable, "-I", script],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"selftest.py failed:\n{r.stdout}\n{r.stderr}"


def test_decision_schema_is_valid_json() -> None:
    import json
    p = os.path.join(ROOT, "statement-reconciliation", "templates",
                     "decisions.schema.json")
    schema = json.load(open(p))
    # The closed vocabulary is the capability boundary; keep it in step with
    # the validator so an agent cannot be told one thing and checked against
    # another.
    sys.path.insert(0, os.path.join(ROOT, "statement-reconciliation", "scripts"))
    import decisions
    assert set(schema["properties"]["kind"]["enum"]) == set(decisions.KINDS)
    assert set(schema["properties"]["actor"]["enum"]) == set(decisions.ACTORS)
    assert set(schema["properties"]["confidence"]["enum"]) == set(decisions.CONF)


def test_skill_frontmatter_is_well_formed() -> None:
    """SKILL.md must carry name + description, or the skill will not trigger."""
    import re
    p = os.path.join(ROOT, "statement-reconciliation", "SKILL.md")
    text = open(p, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md has no YAML frontmatter"
    fm = m.group(1)
    assert re.search(r"^name:\s*\S+", fm, re.M), "frontmatter has no name"
    desc = re.search(r"^description:\s*(.+)", fm, re.M | re.S)
    assert desc, "frontmatter has no description"
    assert len(desc.group(1)) > 80, "description too short to trigger reliably"


@pytest.mark.parametrize("ref", [
    "confidence.md", "discovery.md", "intake.md",
    "matching.md", "reporting.md", "taxonomy.md",
])
def test_referenced_docs_exist(ref: str) -> None:
    """SKILL.md points at these by name; a dangling pointer breaks the workflow."""
    p = os.path.join(ROOT, "statement-reconciliation", "references", ref)
    assert os.path.isfile(p), f"missing reference: {ref}"


def test_binary_fixtures_are_valid() -> None:
    """A committed .xlsx fixture must actually open.

    The golden comparison checks hashes and masked structure, so a corrupted
    workbook would pass it — that happened once while making the fixtures
    byte-reproducible. This asserts loadability directly.
    """
    openpyxl = pytest.importorskip("openpyxl")
    found = 0
    for root, _dirs, files in os.walk(FIX):
        for f in files:
            if f.endswith((".xlsx", ".xlsm")) and "normalising" not in f:
                openpyxl.load_workbook(os.path.join(root, f)).close()
                found += 1
    assert found, "no .xlsx fixture found — 06-profile should provide one"


def test_tool_adapters_are_in_sync() -> None:
    """AGENTS.md, CLAUDE.md, Copilot and Cursor files are generated.

    Drifted guidance is worse than none: it looks authoritative while being
    wrong. The canonical source is statement-reconciliation/SKILL.md.
    """
    script = os.path.join(ROOT, "tools", "sync_adapters.py")
    r = subprocess.run([sys.executable, "-I", script, "--check"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, (
        "tool adapters are stale or missing; run "
        f"`python tools/sync_adapters.py`\n{r.stdout}{r.stderr}")


# Instruction files a tool loads as guidance. Each must stand on its own.
INSTRUCTION_ADAPTERS = [
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".github/instructions/reconciliation.instructions.md",
    ".cursor/rules/statement-reconciliation.mdc",
]
# Human-facing documentation: explains how to wire tools up, and is not
# itself loaded as guidance, so it carries no operating rules.
DOC_ADAPTERS = ["docs/PORTABLE_USAGE.md"]


@pytest.mark.parametrize("rel", INSTRUCTION_ADAPTERS)
def test_adapter_carries_the_core_rules(rel: str) -> None:
    """Each instruction adapter must stand on its own for the key rules.

    A tool that only injects text, without following file references, still
    has to get the language rule, the no-guessing rule and the decision-log
    contract — otherwise the skill silently degrades on that tool.
    """
    p = os.path.join(ROOT, rel)
    assert os.path.isfile(p), f"missing adapter: {rel}"
    text = open(p, encoding="utf-8").read()
    for needle in ("Mirror the user's language", "Never guess a number",
                   "decisions.jsonl"):
        assert needle in text, f"{rel} is missing the core rule: {needle!r}"


@pytest.mark.parametrize("rel", INSTRUCTION_ADAPTERS + DOC_ADAPTERS)
def test_adapter_paths_are_repo_rooted(rel: str) -> None:
    """Adapters sit at the repository root, so skill-relative paths break.

    Matches only path-shaped references — `references/foo.md`, `scripts/x.py` —
    not the English phrase "its `references/` directory".
    """
    import re
    text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    bad = re.findall(r"`(?:references|scripts|templates)/[\w.-]+\.\w+`", text)
    bad += re.findall(r"python (?:references|scripts|templates)/", text)
    assert not bad, (
        f"{rel} has skill-relative path(s) that will not resolve from the "
        f"repository root: {sorted(set(bad))}")


def test_referenced_paths_in_adapters_exist() -> None:
    """Every repo path an adapter names must actually be there.

    A dangling pointer is the most likely way this breaks over time: the
    adapter still reads plausibly, and the tool quietly finds nothing.
    """
    import re
    broken: list[str] = []
    for rel, _ in [(t, None) for t in (
            "AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md",
            ".github/instructions/reconciliation.instructions.md",
            ".cursor/rules/statement-reconciliation.mdc",
            "docs/PORTABLE_USAGE.md")]:
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        for m in re.finditer(r"`(statement-reconciliation/[\w./-]+)`", text):
            target = m.group(1)
            if target.endswith("/") or "<" in target:
                continue
            if not os.path.exists(os.path.join(ROOT, target)):
                broken.append(f"{rel} -> {target}")
    assert not broken, "adapters point at paths that do not exist: " + str(broken)


def test_public_data_matches_provenance() -> None:
    """Committed third-party data must be byte-identical to what was pinned.

    tests/public/ answer keys describe those exact bytes; a hand-edited input
    would silently stop matching its key. Verification only - no network.
    """
    script = os.path.join(HERE, "public", "fetch_public.py")
    r = subprocess.run([sys.executable, "-I", script, "--verify"],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"public test data drifted:\n{r.stdout}\n{r.stderr}"


def test_no_client_data_committed() -> None:
    """Guard the privacy rule: real ledger exports must never enter history."""
    offenders = []
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for f in files:
            if f.endswith("_raw.csv"):
                offenders.append(os.path.relpath(os.path.join(root, f), ROOT))
    assert not offenders, (
        "files matching *_raw.csv look like real ledger exports and must not "
        f"be committed: {offenders}")
