"""Derive the answer keys for the Mindweave US bank + GL sample.

The publisher ships no answer key for this dataset, so these are computed from
the data's own identifiers and balances - nothing is inferred or fuzzy-matched.

    python tests/public/mindweave-us/expected/derive_expected.py

Defaults read ../inputs (bank/ and gl/) and write next to this script.
Optional: derive_expected.py INPUTS_DIR OUT_DIR

Writes:
  derived_gl_rollforward.csv          per month, per GL account: opening + movements - closing
  derived_bank_vs_gl_transactions.csv bank lines vs GL bank-account (1-1000) lines,
                                      matched on source_module + source_id + amount
  derived_bank_vs_gl_monthly.csv      statement vs GL 1-1000 per month, difference split into causes
Amounts: debit-positive (GL) and deposit-positive (bank), 2 decimals.
"""
import csv
import os
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal as D

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "inputs")
OUT = sys.argv[2] if len(sys.argv) > 2 else HERE
G = os.path.join(SRC, "gl")
B = os.path.join(SRC, "bank")
os.makedirs(OUT, exist_ok=True)
Q = D("0.01")


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def money(x):
    return str(D(x).quantize(Q))


coa = {r["id"]: r for r in rows(os.path.join(G, "chart_of_accounts.csv"))}
je = {r["id"]: r for r in rows(os.path.join(G, "journal_entries.csv"))}
lines = rows(os.path.join(G, "journal_entry_lines.csv"))
tb = rows(os.path.join(G, "trial_balances.csv"))
bank_accounts = rows(os.path.join(B, "bank_accounts.csv"))
statements = rows(os.path.join(B, "bank_statements.csv"))
btx = rows(os.path.join(B, "bank_transactions.csv"))

# ---------- 1. GL roll-forward per month per account ----------
periods = sorted({r["period_end"] for r in tb})
tb_net = {(r["period_end"], r["account_code"]): D(r["debit_balance"]) - D(r["credit_balance"]) for r in tb}
name_by_code = {r["code"]: r["name"] for r in coa.values()}
mov = defaultdict(D)
for l in lines:
    month = je[l["journal_entry_id"]]["entry_date"][:7]
    code = coa[l["account_id"]]["code"]
    mov[(month, code)] += D(l["debit"]) - D(l["credit"])

rf = []
for i, p in enumerate(periods):
    prev = periods[i - 1] if i else None
    month = p[:7]
    codes = {c for (pe, c) in tb_net if pe == p}
    codes |= {c for (pe, c) in tb_net if pe == prev}
    codes |= {c for (m, c) in mov if m == month}
    for c in sorted(codes):
        in_open = prev is not None and (prev, c) in tb_net
        in_close = (p, c) in tb_net
        opening = tb_net.get((prev, c), D(0)) if prev else D(0)
        movement = mov.get((month, c), D(0))
        closing = tb_net.get((p, c), D(0))
        diff = opening + movement - closing
        notes = []
        if not in_open and movement != 0:
            notes.append("first activity this month (no opening balance row)")
        if not in_close:
            notes.append("missing from closing trial balance")
        rf.append({
            "period_start": month + "-01", "period_end": p, "account_code": c,
            "account_name": name_by_code.get(c, ""),
            "opening_balance": money(opening), "movements": money(movement),
            "closing_balance": money(closing), "difference": money(diff),
            "in_opening_tb": in_open, "in_closing_tb": in_close,
            "expected_status": "RECONCILED" if diff == 0 else "DISCREPANCY",
            "notes": "; ".join(notes),
        })

with open(os.path.join(OUT, "derived_gl_rollforward.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rf[0].keys()))
    w.writeheader()
    w.writerows(rf)

# ---------- 2. Bank vs GL 1-1000, transaction level ----------
op = next(a for a in bank_accounts if a["account_type"] == "operating")
gl_code = op["gl_account_code"]
gl_acct_id = next(i for i, a in coa.items() if a["code"] == gl_code)
gl_lines = []
for l in lines:
    if l["account_id"] != gl_acct_id:
        continue
    j = je[l["journal_entry_id"]]
    gl_lines.append({"line": l, "je": j, "key": (j["source_module"], j["source_id"]),
                     "amount": D(l["debit"]) - D(l["credit"])})
bank_rows = [r for r in btx if r["bank_account_id"] == op["id"]]

gl_by_key = defaultdict(list)
for g in gl_lines:
    if g["key"][1]:
        gl_by_key[g["key"]].append(g)
used_gl = set()
tx_out = []
for r in bank_rows:
    key = (r["source_module"], r["source_id"])
    amt = D(r["amount"])
    match = None
    for g in gl_by_key.get(key, []):
        if id(g) not in used_gl and g["amount"] == amt:
            match = g
            break
    base = {
        "bank_transaction_id": r["id"], "bank_date": r["transaction_date"],
        "bank_description": r["description"], "bank_amount": money(amt),
        "source_module": r["source_module"], "source_id": r["source_id"],
    }
    if match:
        used_gl.add(id(match))
        bd = date.fromisoformat(r["transaction_date"])
        gd = date.fromisoformat(match["je"]["entry_date"])
        tx_out.append({**base, "journal_entry_id": match["je"]["id"], "journal_line_id": match["line"]["id"],
                       "gl_date": match["je"]["entry_date"], "gl_amount": money(match["amount"]),
                       "date_lag_days": (bd - gd).days, "expected_status": "MATCHED",
                       "reason": "same source_module + source_id and amount"})
    else:
        reason = "bank fee not recorded in GL" if r["transaction_type"] == "fee" else "no GL line with this source id and amount"
        tx_out.append({**base, "journal_entry_id": "", "journal_line_id": "", "gl_date": "", "gl_amount": "",
                       "date_lag_days": "", "expected_status": "BANK_ONLY", "reason": reason})
for g in gl_lines:
    if id(g) in used_gl:
        continue
    reason = ("opening owner's equity contribution; not on the bank statement (statement opens at 0.00)"
              if g["key"][0] == "company" else "no bank line with this source id and amount")
    tx_out.append({"bank_transaction_id": "", "bank_date": "", "bank_description": "", "bank_amount": "",
                   "source_module": g["key"][0], "source_id": g["key"][1],
                   "journal_entry_id": g["je"]["id"], "journal_line_id": g["line"]["id"],
                   "gl_date": g["je"]["entry_date"], "gl_amount": money(g["amount"]),
                   "date_lag_days": "", "expected_status": "GL_ONLY", "reason": reason})

with open(os.path.join(OUT, "derived_bank_vs_gl_transactions.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(tx_out[0].keys()))
    w.writeheader()
    w.writerows(tx_out)

# ---------- 3. Bank vs GL 1-1000, monthly ----------
gl_month = defaultdict(lambda: [D(0), D(0)])
for g in gl_lines:
    m = g["je"]["entry_date"][:7]
    if g["amount"] >= 0:
        gl_month[m][0] += g["amount"]
    else:
        gl_month[m][1] -= g["amount"]
bank_only_month = defaultdict(D)
gl_only_month = defaultdict(D)
timing = defaultdict(D)  # matched items booked in a different month on each side
for t in tx_out:
    if t["expected_status"] == "BANK_ONLY":
        bank_only_month[t["bank_date"][:7]] += D(t["bank_amount"])
    elif t["expected_status"] == "GL_ONLY":
        gl_only_month[t["gl_date"][:7]] += D(t["gl_amount"])
    elif t["bank_date"][:7] != t["gl_date"][:7]:
        timing[t["gl_date"][:7]] += D(t["gl_amount"])
        timing[t["bank_date"][:7]] -= D(t["bank_amount"])

monthly = []
cum_bank_only = cum_gl_only = cum_timing = D(0)
gl_close = D(0)
for s in sorted((s for s in statements if s["bank_account_id"] == op["id"]), key=lambda s: s["period_start"]):
    m = s["period_start"][:7]
    deb, cred = gl_month[m]
    gl_open = gl_close
    gl_close = gl_open + deb - cred
    cum_bank_only += bank_only_month[m]
    cum_gl_only += gl_only_month[m]
    cum_timing += timing[m]
    diff = gl_close - D(s["closing_balance"])
    unexplained = diff - cum_gl_only + cum_bank_only - cum_timing
    monthly.append({
        "month": m, "statement_opening": money(s["opening_balance"]),
        "statement_deposits": money(s["total_deposits"]), "statement_withdrawals": money(s["total_withdrawals"]),
        "statement_closing": money(s["closing_balance"]),
        "gl_opening": money(gl_open), "gl_debits": money(deb), "gl_credits": money(cred), "gl_closing": money(gl_close),
        "difference_gl_minus_bank": money(diff),
        "explained_by_gl_only_items": money(cum_gl_only),
        "explained_by_bank_only_items": money(-cum_bank_only),
        "explained_by_timing": money(cum_timing),
        "unexplained": money(unexplained),
    })

with open(os.path.join(OUT, "derived_bank_vs_gl_monthly.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(monthly[0].keys()))
    w.writeheader()
    w.writerows(monthly)

print(f"wrote 3 answer-key files to {os.path.abspath(OUT)}")
