# Public test data

Third-party, synthetic reconciliation datasets with answer keys the skill did
not produce. The golden fixtures in `tests/fixtures/` prove the skill still
behaves as blessed; this data checks it against an outside truth.

Every file is pinned in `PROVENANCE.json` (source URL at a fixed commit, sha256,
license). Nothing here is client data.

## Layout

Each dataset keeps what the skill reads apart from the answers:

```
public/
  README.md            this file
  PROVENANCE.json      source, sha256 and license of every file
  fetch_public.py      verify committed files; fetch the ones kept out of git
  licenses/            license texts that must travel with the data
  mindweave-us/        bank + general ledger, 24 months (2024-2025)
    inputs/bank/       bank_accounts, bank_statements, bank_transactions, companies
    inputs/gl/         chart_of_accounts, journal_entries, journal_entry_lines,
                       trial_balances, companies
    expected/          derived_*.csv answer keys + derive_expected.py
  reconriver/          internal ledger vs payment processor vs bank
    inputs/<pack>/     internal_transactions, processor_transactions, bank_settlements
    inputs/rules.json  fee policy, settlement window, currency rule
    expected/<pack>/   expected_reconciliation.csv (published answer key),
                       scenario_manifest.json, README.md
  ledger-recon-multi-account/   3 bank accounts vs one ledger, no shared id
    inputs/            statement_YYYY-MM-DD.csv, ledger_*.csv, rules.json
    expected/          SAMPLE_OUTPUT.md (the source tool's published output)
  cuadrador/           bank statement vs books (fetched, not committed)
    expected/expected_results.csv   per-case expected difference
```

`inputs/` never contains an answer. Open `expected/` only to score a run.

## Datasets

| Dataset | Tests | Rows | Answer key | In git | License |
|---|---|---|---|---|---|
| `mindweave-us` | Roll-forward per account per month; bank vs GL account 1-1000 | 17,027 journal lines, 380 trial-balance rows, 3,232 bank lines | Derived from the data's own ids and balances (`expected/derive_expected.py`); none is published | Yes | CC BY-NC 4.0 |
| `reconriver` | Order matching (internal vs processor) and settlement matching (processor batches vs bank) | 100 and 1,000 payments committed; 10,000-payment packs fetched | Published with the data | `clean-settlement`, `mixed-exceptions` | CC BY 4.0 (data), MIT (generator) |
| `ledger-recon-multi-account` | Bank credits vs ledger by embedded payment reference, wrong-account routing | ~70 bank rows on each of 2 days | Published by the source tool, partial (summary counts and the unmatched rows for 2026-01-05) | Yes | MIT |
| `cuadrador` | Bank vs books with deposits in transit, outstanding checks, one transposed-digit error | 62 bank lines | Published per line (`expected.csv`) + per-case difference | Summary only | None stated |

Sources:

- https://huggingface.co/datasets/mindweave/bank-transactions-us and https://huggingface.co/datasets/mindweave/accounting-ledger-us
- https://github.com/heybadrinath/reconriver (`datasets/`, commit `ddeced7`), also https://huggingface.co/datasets/heybadrinath/reconriver-synthetic-reconciliation
- https://github.com/dikaakid/ledger-reconciliation-tool (`examples/dummy_data/`, commit `79a9ad7`)
- https://github.com/d2fzrsthmj-source/cuadrador (`sample_data/`, commit `f8649b6`)

## How the skill uses it

**As golden fixtures.** Three fixtures are reshaped from `mindweave-us` by
builders in `tests/make_fixtures.py`, so CI regenerates them and fails if they
drift. Their contracts restate the answer key:

| Fixture | Built from | Contract (from the answer key) |
|---|---|---|
| `07-public-gl-clean` | GL, 2024-06 | 16/16 accounts tie, zero gap |
| `08-public-gl-tb-offset` | GL, 2025-10 | `1-2010` breaks by -77.06 and `6-2800` by +77.06; every other account ties |
| `09-public-bank-vs-gl` | Operating bank vs GL 1-1000 | 3,208 exact pairs; 24 bank fees (-445.85) bank-only; the 200,000.00 opening equity GL-only; nothing else matched |

**By hand, for the other sets.** Reshape the inputs into the engine's format
(the builders in `make_fixtures.py` show the pattern), run the scripts, and
compare with `expected/`. For `reconriver`, join on `result_scope` + `work_key`.

`ledger-recon-multi-account` and `cuadrador` need intake first (payment
references live inside free-text bank descriptions; three bank layouts differ),
so they test the agent's discovery and intake phases rather than an engine
script on its own.

## What the first evaluation found (2026-10-30)

- **mindweave-us:** every engine figure matches the answer key to the cent.
  In 08 the two breaks are reported as `ITEM_LEVEL_BREAK` with no cause: the
  gaps offset exactly, but across accounts with different parents (`1-2010`,
  `6-2800`), so the sibling detector does not pair them. The agent has to
  reason that one depreciation entry disagrees with the trial balance on both
  sides.
- **reconriver, order level** (`mixed-exceptions`, internal vs processor on
  `merchant_order_id` + `gross_amount`): 960 exact pairs and 9 `SUBSET`
  matches. All 9 subset matches are false: each pairs one internal payment with
  four unrelated orders whose amounts happen to sum to it within 0.01. Among
  the exact pairs, 20 fee mismatches and 10 currency mismatches pair as clean,
  because matching compares gross amount only.

## Fair-testing notes

- `reconriver`: some IDs contain the answer category (`SYNTH-BATCH-AMOUNT-BREAK-…`,
  `SYNTH-ORDER-PROC-ONLY-…`). Do not let matching read meaning from ID text.
- `cuadrador`: the folder name `sample_data_error` reveals that case has an error.
- `mindweave-us`: the answer key is computed, not published. Check
  `derive_expected.py` if the skill disagrees with it.

## Integrity and fetching

```bash
python tests/public/fetch_public.py --verify   # sha256 of everything on disk
python tests/public/fetch_public.py            # fetch the non-committed files
```

Fetched: the ReconRiver `month-end-close` and `failure-recovery` packs (~10 MB,
kept out of git for size) and the cuadrador set (no license is stated in its
source repository, so it is never redistributed from here). Their paths are in
`.gitignore`. `pytest tests/` checks every committed file against its sha256.

## Licenses

- `mindweave-us`: Creative Commons Attribution-NonCommercial 4.0. Generated by
  Mindweave Technologies (https://mindweave.tech); free sample, unmodified
  (its empty `bank_reconciliations.csv` table is omitted). Non-commercial use only.
- `reconriver`: data under Creative Commons Attribution 4.0, generator code
  under MIT (`licenses/reconriver-MIT.txt`); data unmodified. `rules.json` is
  transcribed from the dataset READMEs.
- `ledger-recon-multi-account`: MIT (`licenses/ledger-reconciliation-tool-MIT.txt`);
  data unmodified. `rules.json` is transcribed from `ledger_recon/config.py`.
- `cuadrador`: no license stated. Only our per-case summary is committed.
