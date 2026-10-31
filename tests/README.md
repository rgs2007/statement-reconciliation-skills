# Tests

Golden-file regression tests. Each fixture holds committed **source files** and
a blessed **expected report**; the runner regenerates the output with the
skill's own scripts and compares.

```bash
python tests/run_tests.py            # check every fixture
python tests/run_tests.py --only 02-faults
python tests/run_tests.py -v         # full diffs instead of a summary
pytest tests/                        # same checks, if you prefer pytest
```

A passing run means current behaviour still produces the expected report. A
failing run names the exact figure that moved.

## Two layers of protection

**Golden comparison** catches *any* change in output, including ones nobody
thought to assert. Useful but blunt: re-blessing makes a failure disappear.

**Behavioural contracts**, declared in `CONTRACTS` in `run_tests.py`, state
what each fixture exists to prove — that the ×1000 shift is detected, that the
sibling pair offsets, that an exclusion decision is replayed. These are checked
on every run *including* `--update`, so re-blessing cannot silently erase the
contract. If a contract fails, the skill is broken regardless of what the
goldens say.

## Fixtures

| Fixture | Proves |
|---|---|
| `01-clean` | A clean ledger reconciles 100% with **zero findings** — no false positives, no spurious duplicate warnings |
| `02-faults` | Five injected defects all surface: missing movements, ×1000 decimal shift, sibling misposting, duplicate posting, unattributable row — plus a reversal pair reported as activity, not as a gap |
| `03-decisions` | The decision log replays: an exclusion, a manual attribution, a classification, and a **superseded** tolerance that must not win |
| `04-scope-pagebreak` | Scope mismatch is isolated; consecutive duplicate rows are *surfaced and never auto-removed* |
| `05-item-matching` | Item matching across all four passes — exact, amount-only, bounded subset-sum (one lump payment settling three invoices), and timing |
| `06-profile` | The profiler reports structure with values **masked**, and guesses the header row in a messy workbook |
| `07-public-gl-clean` | On published third-party data (Mindweave GL, 2024-06), every account ties with zero gap |
| `08-public-gl-tb-offset` | On the same GL for 2025-10, exactly the two accounts the answer key flags break, by -77.06 and +77.06 |
| `09-public-bank-vs-gl` | Bank vs GL account 1-1000 over 24 months: 3,208 exact pairs, 24 unbooked bank fees, the opening equity line GL-only, no forced matches |

Fixtures 07-09 are reshaped from third-party data in [`public/`](public/README.md).
Their defects were not planted by us, and their contracts restate an answer key
computed independently of the skill.

Each reconciliation fixture contains:

```
NN-name/
  sources/           opening.csv, closing.csv, movements.csv  (committed inputs)
  datamap.json       how the engine reads them
  decisions.jsonl    only where the fixture exercises replay
  report.json        optional: entity and period for the report header
  expected/          the blessed output — metrics.json, breaks.csv,
                     residual.csv, report.md
```

`02-faults/expected/report.reviewed.md` is **documentation, not a test
target**: the same report with the narrative written out, showing the standard
a finished agent report should meet. The generated `report.md` deliberately
leaves rationale, alternatives and remediation as placeholders, because the
scripts guarantee the figures and the audit trail while the reasoning is the
agent's job.

## Public test data

[`public/`](public/README.md) holds third-party synthetic datasets with answer
keys the skill did not produce, kept as `inputs/` and `expected/` per dataset.
Every file is pinned by sha256 in `public/PROVENANCE.json`, and a pytest check
fails if a committed one changes. Large packs and the one set without a license
are fetched on demand:

```bash
python tests/public/fetch_public.py --verify   # integrity only, no network
python tests/public/fetch_public.py            # fetch what is not committed
```

## Why the data is synthetic

The ledgers that motivated this skill are real client accounting data, which
does not belong in a git history — history is permanent, and a private repo can
be shared later. The fixtures instead reproduce the *structural* properties
that make real reconciliations hard: account keys embedded in free-text
descriptions and zero-padded, comma decimal separators, offsetting sibling
sub-accounts, a decimal-shift keying error, accounts present on one side only,
consecutive duplicate rows, and a posting whose account cannot be derived.

Regenerate the sources any time — `make_fixtures.py` shows exactly how each
defect is constructed, so a reviewer can see it rather than trusting a CSV that
appeared from nowhere:

```bash
python tests/make_fixtures.py              # all fixtures
python tests/make_fixtures.py --only 02-faults
```

## What is compared, and why it is stable

| File | Compared how |
|---|---|
| `metrics.json` | Every figure. Dict order ignored; money compared to 2dp so platform float noise cannot fail a run |
| `breaks.csv` | Per-account gap, status and structural signal — the detection contract |
| `report.md` | In full, after normalising the one volatile line (the generation timestamp) |
| `item_match.json` | Matching passes and the surviving residual |
| `profile.json` | Masked structure, proving values stay masked |

Source **sha256 hashes are deliberately not normalised**. If a fixture's bytes
change, the test must fail — the blessed figures no longer describe that input.

## Re-blessing after an intended change

```bash
python tests/run_tests.py            # read the diff first
python tests/run_tests.py --update   # then bless
git diff tests/fixtures              # review before committing
```

`--update` rewrites the goldens from current behaviour. Only run it once you
have read the diff and decided the new behaviour is correct — otherwise it
converts a regression into the new expected truth, silently. It exits non-zero
if a behavioural contract fails, so a broken skill cannot be blessed.

The runner prints the diff before writing, so there is no excuse for blessing
blind. When a change is an improvement, say so in the commit message and
explain what moved.

## Adding a fixture

1. Add a builder to `BUILDERS` in `make_fixtures.py`.
2. Run `python tests/make_fixtures.py --only NN-name`.
3. Add behavioural contracts to `CONTRACTS` in `run_tests.py` — what does this
   fixture *prove*? A fixture with no contract only guards against drift.
4. Bless: `python tests/run_tests.py --only NN-name --update`.
5. Read the blessed output before committing it. A golden nobody checked is
   worse than no golden, because it looks like verification.

## Separate from the skill's own self-test

`statement-reconciliation/scripts/selftest.py` builds its fixtures in a temp
directory at run time and asserts detection. It ships *inside* the skill, so a
user who installs the skill can verify their install with no repo checkout:

```bash
python statement-reconciliation/scripts/selftest.py
```

These golden tests are the repo-level complement: they pin exact expected
output across versions, which a self-contained self-test cannot do.
