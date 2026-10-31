#!/usr/bin/env python3
"""Generate the test fixtures (source files only — never the expected output).

Fixtures are committed, so this script exists to make them *reproducible and
reviewable*: you can see exactly how each defect was constructed rather than
trusting a CSV that appeared from nowhere.

    python tests/make_fixtures.py            # write sources for every fixture
    python tests/make_fixtures.py --only 02-faults

Expected outputs are NOT written here. They are produced by the skill's own
scripts and blessed deliberately:

    python tests/run_tests.py --update

Deliberately synthetic. The ledgers that motivated this skill are real client
accounting data, which does not belong in a git history — history is permanent
and a private repo can be shared later. These fixtures instead reproduce the
*structural* characteristics that make real reconciliations hard:

  - account keys embedded in free-text descriptions, zero-padded
  - comma decimal separators (pt-BR / European exports)
  - offsetting sibling sub-accounts (a misposting, not missing money)
  - a x1000 decimal-shift keying error
  - accounts present on one side only (scope mismatch)
  - consecutive duplicate rows (page-break artifact vs real instalments)
  - a transaction whose account cannot be derived at all
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")

# Fixed so generated binary fixtures (.xlsx) are byte-reproducible.
_FIXED_TS = datetime.datetime(2026, 1, 1, 0, 0, 0)


def _freeze_zip_times(path: str) -> None:
    """Make an OOXML archive byte-reproducible.

    Pinning the workbook's docProps is not enough: openpyxl stamps each ZIP
    entry with the wall-clock time of the save, so the archive's bytes - and
    therefore its sha256 - change on every build. Rewriting the entries with a
    fixed date makes the fixture genuinely byte-reproducible, which CI asserts.
    Entry order is preserved, not sorted, so the file stays a valid workbook.
    """
    import re
    import zipfile
    stamp = _FIXED_TS.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    with zipfile.ZipFile(path) as zin:
        entries = []
        for i in zin.infolist():
            data = zin.read(i.filename)
            if i.filename == "docProps/core.xml":
                # openpyxl overwrites dcterms:modified with the save time no
                # matter what wb.properties.modified is set to, so it has to
                # be normalised here or the bytes change every second.
                # A replacement FUNCTION, not a template: the stamp starts
                # with a digit, so a "\1" template would be read as group 12
                # and silently corrupt the XML.
                data = re.sub(
                    rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
                    lambda m: m.group(1) + stamp + m.group(2), data)
            entries.append((i, data))
    # Keep the real extension: openpyxl refuses to open a path it does not
    # recognise as a workbook, so a bare ".tmp" would fail validation for the
    # wrong reason.
    root, ext = os.path.splitext(path)
    tmp = f"{root}.normalising{ext}"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, data in entries:
            ni = zipfile.ZipInfo(info.filename,
                                 date_time=(_FIXED_TS.year, _FIXED_TS.month,
                                            _FIXED_TS.day, 0, 0, 0))
            ni.compress_type = info.compress_type
            ni.external_attr = info.external_attr
            zout.writestr(ni, data)

    # Rewriting an archive by hand can produce a file that still hashes and
    # still unzips but is no longer a valid workbook. Verify before swapping
    # it in: a corrupted fixture would otherwise sail through the golden tests,
    # which compare hashes and masked structure, not loadability.
    try:
        import openpyxl
        openpyxl.load_workbook(tmp).close()
    except Exception as e:
        os.remove(tmp)
        raise RuntimeError(
            f"normalising {os.path.basename(path)} produced an invalid "
            f"workbook ({type(e).__name__}: {e}); the original was kept") from e
    shutil.move(tmp, path)


def br(x: float) -> str:
    """Format as a comma-decimal amount, as a pt-BR/European export would."""
    return f"{x:.2f}".replace(".", ",")


def dump(path: str, header: list[str], rows: list[list]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def datamap(path: str, *, decimal_style: str = "comma",
            key_from: bool = True) -> None:
    """Write the datamap describing the three sides to the engine."""
    key_spec_bal = ({"key_from": ["account_description"]} if key_from
                    else {"key": "account"})
    cfg = {
        "opening": dict(path="sources/opening.csv", amount="saldo_inicial",
                        **key_spec_bal),
        "closing": dict(path="sources/closing.csv", amount="saldo_final",
                        **key_spec_bal),
        "movements": {"path": "sources/movements.csv", "amount": "valor",
                      "key_from": ["historico1", "historico2"],
                      "rules": [{"name": "S0", "pattern": None}]},
        "decimal_style": decimal_style,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(cfg, open(path, "w"), indent=2)


# --------------------------------------------------------------------------
# A small payables ledger. Columns and descriptions imitate a real
# Portuguese-language auxiliary ledger: the account key is embedded at the
# head of the description, zero-padded, followed by the supplier name.
#
#   key        name                       opening       movement
ACCOUNTS = [
    ("8241-01", "AGGREKO ENERGIA LTDA",    600193.40,    83098.68),
    ("4363-01", "ECOLAB QUIMICA LTDA",     214503.34,    85280.59),
    ("4363-02", "ECOLAB SERVICOS LTDA",    -20849.25,    -1773.07),
    ("8722-01", "SANDRA JULIANA PEREIRA",   42539.68,     8006.67),
    ("8722-02", "SANDRA J PEREIRA ME",     -59022.49,    13202.36),
    ("5690-01", "TRANSPORTES UNIAO SA",   -111039.10,   -23200.00),
    ("4187-01", "FOLHA DE PAGAMENTO",     -200000.00,        0.00),
    ("9284-01", "RECEITA DE SERVICOS",   -1480520.14,  -309332.22),
    ("6652-01", "CUSTO MERCADORIA",        567198.67,   106756.03),
    ("6652-04", "CUSTO FRETE",              21227.06,     4326.43),
    ("2271-01", "ENCARGOS SOCIAIS",         20849.25,     1773.07),
    ("2432-01", "DEPRECIACAO ACUMULADA",     7317.20,      731.72),
]


def desc(key: str, name: str) -> str:
    """'8241-01' + name -> '008241-01 -AGGREKO ENERGIA LTDA' (zero-padded)."""
    code, sub = key.split("-")
    return f"{code.zfill(6)}-{sub} -{name}"


def split3(total: float) -> list[float]:
    """Split a period movement into three DISTINCT postings summing to it.

    Deliberately unequal: equal postings on the same account are
    indistinguishable from duplicates, which would make the clean fixture
    ambiguous and its "no false positives" contract meaningless.
    """
    a = round(total * 0.45, 2)
    b = round(total * 0.35, 2)
    return [a, b, round(total - a - b, 2)]


def build(name: str, *, faults: bool = False, scope: bool = False,
          pagebreak: bool = False) -> None:
    d = os.path.join(FIX, name)
    shutil.rmtree(os.path.join(d, "sources"), ignore_errors=True)

    op, cl, mv = [], [], []
    for i, (key, nm, opening, movement) in enumerate(ACCOUNTS):
        k_desc = desc(key, nm)
        closing = round(opening + movement, 2)

        # ---- scope mismatch: a closing-only account with no opening/movements
        if scope and key == "2432-01":
            cl.append([k_desc, br(closing)])
            continue

        op.append([i + 1, k_desc, br(opening)])
        cl.append([k_desc, br(closing)])

        for j, part in enumerate(split3(movement)):
            # F1 MISSING_MOVEMENTS — every posting for this account is absent
            if faults and key == "8722-01":
                continue

            value, target = part, k_desc

            # F2 DECIMAL_SHIFT — keyed 1000x too large
            if faults and key == "6652-04" and j == 0:
                value = part * 1000

            # F3 SUBACCOUNT_MISATTRIBUTION — posted to the sibling -01
            if faults and key == "4363-02" and j == 0:
                target = desc("4363-01", "ECOLAB QUIMICA LTDA")

            mv.append([br(value), target, "PAGTO", f"mv_{i:02d}_{j}"])

    if faults:
        # F4 DUPLICATE_POSTING — same posting, different row id
        mv.append(mv[0][:3] + ["mv_DUP"])
        # F5 UNATTRIBUTED — no derivable account
        mv.append([br(12345.67), "AJUSTE DIVERSOS SEM CONTA", "", "mv_ORPHAN"])
        # REVERSAL_PAIR — a posting and its explicit reversal (net zero)
        rev = desc("5690-01", "TRANSPORTES UNIAO SA")
        mv.append([br(4400.00), rev, "PAGTO", "mv_REV_A"])
        mv.append([br(-4400.00), rev, "RECLAS. PAGTO", "mv_REV_B"])

    if pagebreak:
        # Consecutive identical rows: a paginated-source artifact, OR genuine
        # repeated instalments. Indistinguishable from the data alone - which
        # is exactly the point of the PAGEBREAK_DUPLICATION fixture.
        inst = [br(2500.00), desc("8241-01", "AGGREKO ENERGIA LTDA"),
                "PARCELA", "mv_INST"]
        mv += [list(inst) for _ in range(4)]

    dump(f"{d}/sources/opening.csv",
         ["id", "account_description", "saldo_inicial"], op)
    dump(f"{d}/sources/closing.csv",
         ["account_description", "saldo_final"], cl)
    dump(f"{d}/sources/movements.csv",
         ["valor", "historico1", "historico2", "source_id"], mv)
    datamap(f"{d}/datamap.json")


def build_decisions(name: str) -> None:
    """Same defects as 02, plus a decision log the engine must replay."""
    build(name, faults=True)
    d = os.path.join(FIX, name)
    # Keys are written the way a human writes them ("8722-01"); the engine
    # canonicalises them. That is deliberately exercised here.
    entries = [
        {"id": "d-0001", "ts": "2026-10-01T09:00:00+00:00", "actor": "engine",
         "kind": "convention",
         "statement": {"equation": "closing = opening + movements",
                       "movement_sign": 1},
         "reason": "Both conventions tested across shared keys; addition "
                   "reconciled every account that is not otherwise defective.",
         "evidence": {"reconciled_plus": 8, "reconciled_minus": 0},
         "confidence": "HIGH", "run_id": "run-001"},
        {"id": "d-0002", "ts": "2026-10-01T09:14:00+00:00", "actor": "user",
         "kind": "exclude_scope", "statement": {"keys": ["8722-01"]},
         "reason": "Conta reconciliada separadamente pela equipe fiscal; "
                   "fora do escopo desta conciliacao.",
         "evidence": {"gap": 8006.67, "movements_found": 0},
         "confidence": "HIGH",
         "impact": {"accounts_affected": 1}, "run_id": "run-002"},
        {"id": "d-0003", "ts": "2026-10-01T09:21:00+00:00", "actor": "user",
         "kind": "attribute",
         "statement": {"source_id": "mv_ORPHAN", "key": "5690-01"},
         "reason": "Confirmado pelo cliente: ajuste pertence a TRANSPORTES "
                   "UNIAO SA conforme documento de origem.",
         "evidence": {"amount": 12345.67, "fuzzy_score": 0.44},
         "confidence": "MEDIUM", "run_id": "run-002"},
        {"id": "d-0004", "ts": "2026-10-01T09:30:00+00:00", "actor": "agent",
         "kind": "classify",
         "statement": {"keys": ["4363-01", "4363-02"],
                       "category": "SUBACCOUNT_MISATTRIBUTION"},
         "reason": "As duas subcontas irmas apresentam diferencas que se "
                   "anulam exatamente: valor lancado na subconta errada.",
         "evidence": {"shared_parent": "4363"},
         "confidence": "HIGH", "run_id": "run-002"},
        # A superseded decision: proves replay honours `supersedes`.
        {"id": "d-0005", "ts": "2026-10-01T09:35:00+00:00", "actor": "user",
         "kind": "tolerance", "statement": {"materiality": 1.0},
         "reason": "Tentativa inicial de elevar a materialidade.",
         "evidence": {}, "confidence": "LOW", "run_id": "run-002"},
        {"id": "d-0006", "ts": "2026-10-01T09:41:00+00:00", "actor": "user",
         "kind": "tolerance", "statement": {"materiality": 0.01},
         "reason": "Materialidade revertida para centavos: a auditoria exige "
                   "conciliacao exata nesta conta.",
         "evidence": {}, "confidence": "HIGH", "supersedes": "d-0005",
         "run_id": "run-003"},
    ]
    with open(f"{d}/decisions.jsonl", "w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")


def build_items(name: str) -> None:
    """Item-level matching: exact, amount-only, subset-sum and timing."""
    d = os.path.join(FIX, name)
    shutil.rmtree(os.path.join(d, "sources"), ignore_errors=True)
    # Open invoices on the ledger side
    left = [
        ["NF-1001", "1200.00", "2026-09-03"],
        ["NF-1002", "800.50",  "2026-09-07"],
        ["NF-1003", "450.25",  "2026-09-11"],
        ["NF-1004", "9900.00", "2026-09-15"],
        ["NF-1005", "75.00",   "2026-09-21"],
        ["NF-1006", "640.00",  "2026-09-28"],
    ]
    # Bank statement side: one exact hit, one lump settling three invoices,
    # one timing difference in the next period, one genuinely unmatched line.
    right = [
        ["PAY-A",   "2450.75", "2026-09-30"],   # = 1001 + 1002 + 1003
        ["NF-1004", "9900.00", "2026-09-16"],   # exact on reference + amount
        ["PAY-B",   "640.00",  "2026-10-04"],   # timing: next period
        ["PAY-C",   "60.00",   "2026-09-29"],   # unmatched on the right
    ]
    dump(f"{d}/sources/open_items.csv", ["doc", "valor", "data"], left)
    dump(f"{d}/sources/statement.csv", ["doc", "valor", "data"], right)
    json.dump({"amount": "valor", "ref": "doc", "date": "data",
               "tolerance": 0.01, "max_subset": 4, "node_cap": 200000},
              open(f"{d}/match.json", "w"), indent=2)


def build_profile(name: str) -> None:
    """A deliberately messy workbook, for the masked-profiler golden test."""
    d = os.path.join(FIX, name)
    shutil.rmtree(os.path.join(d, "sources"), ignore_errors=True)
    os.makedirs(f"{d}/sources", exist_ok=True)
    try:
        import openpyxl
    except ImportError:
        print(f"  {name}: openpyxl missing - skipping the .xlsx source")
        openpyxl = None
    if openpyxl:
        wb = openpyxl.Workbook()
        # openpyxl stamps creation/modification times into docProps, so an
        # otherwise identical workbook hashes differently on every build.
        # Pinning them keeps the fixture byte-reproducible, which CI asserts
        # and which the profiler's sha256 golden depends on.
        wb.properties.created = _FIXED_TS
        wb.properties.modified = _FIXED_TS
        ws = wb.active
        ws.title = "Saldos"
        ws.append(["ACME INDUSTRIA LTDA - Balancete"])     # title banner
        ws.append(["Periodo: 2026-09", None, None, None])  # metadata
        ws.append([])                                      # blank separator
        ws.append(["conta", "descricao", "saldo_m", "saldo_o"])  # real header
        ws.append(["1001", desc("8241-01", "AGGREKO ENERGIA LTDA"),
                   "1200,50", "300,00"])
        ws.append(["1002", desc("4363-02", "ECOLAB SERVICOS LTDA"),
                   "0,00", "5000,00"])
        ws.append([None, None, None, None])                # stray blank row
        ws.append(["1003", desc("4187-01", "FOLHA DE PAGAMENTO"),
                   "250,00", "250,00"])
        ws.append(["TOTAL", None, "1450,50", "5550,00"])   # inline totals row
        wb.create_sheet("Notas").append(["planilha auxiliar - ignorar"])
        xp = f"{d}/sources/balancete_messy.xlsx"
        wb.save(xp)
        _freeze_zip_times(xp)
    # A CSV with the same shape, so the fixture is still useful without openpyxl
    dump(f"{d}/sources/movimento_messy.csv",
         ["valor", "historico1", "historico2", "source_id"],
         [[br(1200.50), desc("8241-01", "AGGREKO ENERGIA LTDA"), "PAGTO", "a1"],
          [br(-300.00), desc("8241-01", "AGGREKO ENERGIA LTDA"), "", "a2"],
          [br(5000.00), desc("4363-02", "ECOLAB SERVICOS LTDA"), "COMPRA", "a3"],
          ["", "LINHA SEM VALOR", "", "a4"]])


BUILDERS = {
    "01-clean":          lambda n: build(n),
    "02-faults":         lambda n: build(n, faults=True),
    "03-decisions":      build_decisions,
    "04-scope-pagebreak": lambda n: build(n, faults=True, scope=True,
                                          pagebreak=True),
    "05-item-matching":  build_items,
    "06-profile":        build_profile,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="build just this fixture")
    a = ap.parse_args()
    names = [a.only] if a.only else list(BUILDERS)
    for n in names:
        if n not in BUILDERS:
            raise SystemExit(f"unknown fixture '{n}'; have {list(BUILDERS)}")
        BUILDERS[n](n)
        print(f"  built {n}")
    print(f"\n{len(names)} fixture source set(s) written under tests/fixtures/")
    print("Bless expected output with:  python tests/run_tests.py --update")


if __name__ == "__main__":
    main()
