#!/usr/bin/env python3
"""Profile reconciliation source files: structure and masked previews.

Reveals the SHAPE of data without exposing values, so an agent can guide a
user through intake without reading confidential figures. Digits become '#',
letters 'X'; punctuation and length are preserved.

Usage
-----
    python profile_files.py FILE [FILE ...] [--rows N] [--sample N] [--json]

    --rows N     preview rows per file/sheet/table (default 8)
    --sample N   additionally emit a stratified sample of N masked rows
    --json       machine-readable output
    --unmasked   show real values (only with explicit user consent)

Supports .csv/.tsv/.txt, .xlsx/.xlsm (needs openpyxl), .pdf (needs pdfplumber).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

# Decimal-style detection comes from lib.py so the profiler and the engine
# can never disagree about what a number is. Vendored by tools/sync_lib.py.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import detect_style as _detect_style  # noqa: E402


def detect_decimal_style(samples) -> str | None:
    """Thin adapter: lib works on a Series, callers here pass a list."""
    import pandas as _pd
    return _detect_style(_pd.Series(list(samples), dtype="object"))


MASK_LEN = 24


def mask(v) -> str:
    s = "" if v is None else str(v)
    if s == "" or s.lower() == "nan":
        return ""
    out = []
    for ch in s[:MASK_LEN]:
        out.append("#" if ch.isdigit() else "X" if ch.isalpha() else ch)
    return "".join(out) + ("…" if len(s) > MASK_LEN else "")


def kind_of(v) -> str:
    s = "" if v is None else str(v).strip()
    if s == "" or s.lower() == "nan":
        return "blank"
    if re.fullmatch(r"[-(]?\s*[\d.,\s]+\)?%?", s):
        return "number"
    if re.search(r"\d", s) and re.search(r"[A-Za-z]", s):
        return "mixed"
    return "text"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def guess_header_row(rows: list[list[dict]]) -> int | None:
    """First row that is mostly text and followed by mostly non-text."""
    for i, row in enumerate(rows):
        cells = [c for c in row if c["kind"] != "blank"]
        if len(cells) < 2:
            continue
        texts = sum(1 for c in cells if c["kind"] == "text")
        if texts >= max(2, len(cells) * 0.6):
            nxt = rows[i + 1] if i + 1 < len(rows) else None
            if nxt is None:
                return i
            nxt_cells = [c for c in nxt if c["kind"] != "blank"]
            if nxt_cells and sum(1 for c in nxt_cells if c["kind"] == "text") < len(nxt_cells) * 0.6:
                return i
    return None


def amount_columns(cols: list[str]) -> list[str]:
    toks = ("amount", "value", "debit", "credit", "balance", "saldo", "valor",
            "montant", "betrag", "importe", "total", "sum")
    return [c for c in cols if any(t in str(c).lower() for t in toks)]




# --------------------------------------------------------------------------
def profile_csv(path: str, nrows: int, unmasked: bool) -> dict:
    import pandas as pd
    try:
        head = pd.read_csv(path, dtype=str, nrows=nrows, keep_default_na=False)
    except Exception:
        head = pd.read_csv(path, dtype=str, nrows=nrows, sep=None,
                           engine="python", keep_default_na=False)
    with open(path, "r", errors="ignore") as fh:
        total = sum(1 for _ in fh) - 1
    show = (lambda v: str(v)) if unmasked else mask
    preview = [[{"v": show(v), "kind": kind_of(v)} for v in rec]
               for rec in head.values.tolist()]
    amt = amount_columns(list(head.columns))
    style = None
    if amt:
        style = detect_decimal_style(head[amt[0]].tolist())
    return {"format": "csv", "rows_total": total, "columns": list(head.columns),
            "amount_columns": amt, "decimal_style": style, "preview": preview}


def profile_excel(path: str, nrows: int, unmasked: bool) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    show = (lambda v: str(v) if v is not None else "") if unmasked else mask
    sheets = []
    for ws in wb.worksheets:
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= nrows:
                break
            rows.append([{"v": show(c), "kind": kind_of(c)} for c in row])
        sheets.append({"name": ws.title,
                       "rows": ws.max_row, "cols": ws.max_column,
                       "likely_header_row": guess_header_row(rows),
                       "preview": rows})
    wb.close()
    return {"format": "excel", "sheets": [s["name"] for s in sheets], "detail": sheets}


def profile_pdf(path: str, nrows: int, unmasked: bool, max_pages: int = 3) -> dict:
    import pdfplumber
    show = (lambda v: str(v) if v is not None else "") if unmasked else mask
    pages = []
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        for i, page in enumerate(pdf.pages[:max_pages]):
            tables = page.extract_tables() or []
            pages.append({
                "page": i + 1, "tables_found": len(tables),
                "tables": [{"rows": len(t), "cols": len(t[0]) if t else 0,
                            "preview": [[show(c) for c in r] for r in t[:nrows]]}
                           for t in tables]})
    return {"format": "pdf", "pages_total": n, "pages_scanned": len(pages),
            "detail": pages,
            "warning": "PDF extraction is error-prone: check for repeated rows at "
                       "page breaks, wrapped lines, column drift and inline totals."}


def profile(path: str, nrows: int, unmasked: bool) -> dict:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if not os.path.isfile(path):
        return {"path": path, "error": "file not found"}
    base = {"path": path, "size_bytes": os.path.getsize(path), "sha256": sha256(path)}
    try:
        if ext in ("xlsx", "xlsm"):
            base.update(profile_excel(path, nrows, unmasked))
        elif ext == "pdf":
            base.update(profile_pdf(path, nrows, unmasked))
        elif ext in ("csv", "tsv", "txt"):
            base.update(profile_csv(path, nrows, unmasked))
        else:
            base["error"] = f"unsupported extension '.{ext}'"
    except Exception as e:
        base["error"] = f"{type(e).__name__}: {e}"
    return base


def render(p: dict) -> None:
    if "size_bytes" not in p:
        print(f"\n=== {os.path.basename(p['path'])} ===\n  ERROR: {p.get('error')}")
        return
    print(f"\n=== {os.path.basename(p['path'])} "
          f"({p['size_bytes']:,} bytes, sha256 {p['sha256'][:12]}…) ===")
    if "error" in p:
        print(f"  ERROR: {p['error']}")
        return
    if p["format"] == "csv":
        print(f"  rows: {p['rows_total']:,} | columns: {', '.join(map(str, p['columns']))}")
        if p["amount_columns"]:
            print(f"  amount columns: {p['amount_columns']} | decimal style: {p['decimal_style']}")
        for i, row in enumerate(p["preview"]):
            print(f"    r{i}: " + " | ".join(f"{c['v']}[{c['kind']}]" for c in row))
    elif p["format"] == "excel":
        print(f"  sheets: {p['sheets']}")
        for sh in p["detail"]:
            print(f"  -- '{sh['name']}' {sh['rows']}x{sh['cols']} "
                  f"likely_header_row={sh['likely_header_row']}")
            for i, row in enumerate(sh["preview"]):
                cells = " | ".join(f"{c['v']}[{c['kind']}]" for c in row if c["v"] or c["kind"] != "blank")
                print(f"    r{i}: {cells}")
    elif p["format"] == "pdf":
        print(f"  pages: {p['pages_total']} (scanned {p['pages_scanned']})")
        print(f"  ! {p['warning']}")
        for pg in p["detail"]:
            print(f"  -- page {pg['page']}: {pg['tables_found']} table(s)")
            for j, t in enumerate(pg["tables"]):
                print(f"     table {j}: {t['rows']}x{t['cols']}")
                for r in t["preview"][:4]:
                    print("       " + " | ".join(r))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--rows", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--unmasked", action="store_true",
                    help="show real values; use only with explicit user consent")
    a = ap.parse_args()
    out = [profile(f, a.rows, a.unmasked) for f in a.files]
    if a.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        for p in out:
            render(p)
        print("\nValues are masked (# digit, X letter). Confirm interpretations "
              "with the user, who can see the real file.")


if __name__ == "__main__":
    sys.exit(main())
