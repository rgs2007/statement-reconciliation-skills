#!/usr/bin/env python3
"""Generate the auditable reconciliation report.

Builds report.md from a run's metrics/breaks/residual plus the decision log.
Section headings are emitted in the user's language; category and confidence
codes stay in English and are glossed at the end.

The agent should write the narrative prose - the rationale for each finding,
the alternatives rejected - into the placeholders this produces. This script
guarantees the skeleton, the figures and the audit trail are correct and
consistent; it does not invent explanations.

Usage
-----
    python make_report.py runs/run-001 --decisions decisions.jsonl \\
        --lang pt --out report.md [--entity "ACME Ltda"] [--period "2026-01"]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

# Section headings only. Findings prose is written by the agent.
L = {
    "en": dict(title="Reconciliation report", scope="Scope and sources",
               result="Result", findings="Findings", openq="Open questions",
               decisions="Decisions applied", method="Method and limitations",
               glossary="Glossary", period="Period", entity="Entity",
               generated="Generated", materiality="Materiality",
               file="File", rows="Rows", hash="SHA-256",
               reconciled="Reconciled", gap_gross="Gross open gap",
               gap_net="Net open gap", explained="Explained (HIGH)",
               probable="Probable (MEDIUM)", unresolved="Unresolved / suspect (LOW)",
               category="Category", amount="Amount", conf="Confidence",
               evidence="Evidence", rationale="Rationale",
               alternatives="Alternatives considered", remediation="Remediation",
               raise_conf="To raise confidence", at_stake="Amount at stake",
               none="None recorded.", wrote="TO BE WRITTEN BY THE AGENT"),
    "pt": dict(title="Relatório de conciliação", scope="Escopo e fontes",
               result="Resultado", findings="Constatações",
               openq="Questões em aberto", decisions="Decisões aplicadas",
               method="Método e limitações", glossary="Glossário",
               period="Período", entity="Entidade", generated="Gerado em",
               materiality="Materialidade", file="Arquivo", rows="Linhas",
               hash="SHA-256", reconciled="Conciliado",
               gap_gross="Diferença bruta em aberto", gap_net="Diferença líquida em aberto",
               explained="Explicado (HIGH)", probable="Provável (MEDIUM)",
               unresolved="Não resolvido / suspeito (LOW)", category="Categoria",
               amount="Valor", conf="Confiança", evidence="Evidência",
               rationale="Justificativa", alternatives="Alternativas consideradas",
               remediation="Correção", raise_conf="Para aumentar a confiança",
               at_stake="Valor em jogo", none="Nenhuma registrada.",
               wrote="A SER ESCRITO PELO AGENTE"),
    "es": dict(title="Informe de conciliación", scope="Alcance y fuentes",
               result="Resultado", findings="Hallazgos",
               openq="Preguntas abiertas", decisions="Decisiones aplicadas",
               method="Método y limitaciones", glossary="Glosario",
               period="Período", entity="Entidad", generated="Generado",
               materiality="Materialidad", file="Archivo", rows="Filas",
               hash="SHA-256", reconciled="Conciliado",
               gap_gross="Diferencia bruta abierta", gap_net="Diferencia neta abierta",
               explained="Explicado (HIGH)", probable="Probable (MEDIUM)",
               unresolved="Sin resolver / sospechoso (LOW)", category="Categoría",
               amount="Importe", conf="Confianza", evidence="Evidencia",
               rationale="Justificación", alternatives="Alternativas consideradas",
               remediation="Corrección", raise_conf="Para aumentar la confianza",
               at_stake="Importe en juego", none="Ninguna registrada.",
               wrote="A ESCRIBIR POR EL AGENTE"),
}

GLOSSARY = {
    "SCOPE_MISMATCH": "account present on one side only",
    "MISSING_MOVEMENTS": "balances differ but no transactions explain the change",
    "MISSING_BALANCE_ROWS": "transactions exist with no opening/closing row",
    "SUBACCOUNT_MISATTRIBUTION": "posted to a sibling of the correct account",
    "DECIMAL_SHIFT": "decimal point misplaced by a power of ten",
    "DUPLICATE_POSTING": "same transaction recorded more than once",
    "PAGEBREAK_DUPLICATION": "rows repeated as an artifact of a paginated source",
    "REVERSAL_PAIR": "a posting and its explicit reversal",
    "TIMING_DIFFERENCE": "recorded in different periods on the two sides",
    "UNATTRIBUTED": "account could not be determined",
    "ITEM_LEVEL_BREAK": "residual not fitting a more specific cause",
    "FX_TRANSLATION": "difference attributable to exchange rates",
    "HIGH": "arithmetically proven; no other explanation fits",
    "MEDIUM": "strong signature, but alternatives survive",
    "LOW": "suggestive only; unresolved pending evidence",
}

SIGNAL_TO_CATEGORY = {
    "OFFSETTING_SIBLINGS": ("SUBACCOUNT_MISATTRIBUTION", "HIGH"),
    # MEDIUM, not HIGH: legitimate repeated instalments produce the same
    # signature, so the user must confirm before this is treated as settled.
    "DUPLICATE_POSTING": ("DUPLICATE_POSTING", "MEDIUM"),
    # LOW: adjacent repeats may be a paginated-source artifact or real
    # instalments, and the data cannot tell them apart.
    "PAGEBREAK_SUSPECT": ("PAGEBREAK_DUPLICATION", "LOW"),
    "DECIMAL_SHIFT_x10": ("DECIMAL_SHIFT", "HIGH"),
    "DECIMAL_SHIFT_x100": ("DECIMAL_SHIFT", "HIGH"),
    "DECIMAL_SHIFT_x1000": ("DECIMAL_SHIFT", "HIGH"),
}
STATUS_TO_CATEGORY = {
    "CLOSING_ONLY": ("SCOPE_MISMATCH", "HIGH"),
    "OPENING_ONLY": ("SCOPE_MISMATCH", "HIGH"),
    "MOVEMENT_ONLY": ("MISSING_BALANCE_ROWS", "MEDIUM"),
}


def money(x) -> str:
    try:
        return f"{float(x):,.2f}"
    except (TypeError, ValueError):
        return str(x)


def classify_row(r) -> tuple[str, str]:
    sig = str(r.get("signal") or "")
    if sig in SIGNAL_TO_CATEGORY:
        return SIGNAL_TO_CATEGORY[sig]
    st = str(r.get("status") or "")
    if st in STATUS_TO_CATEGORY:
        return STATUS_TO_CATEGORY[st]
    if abs(float(r.get("movements", 0) or 0)) < 0.01:
        return ("MISSING_MOVEMENTS", "MEDIUM")
    return ("ITEM_LEVEL_BREAK", "LOW")


def build(run_dir: str, dec_path: str | None, lang: str,
          entity: str | None, period: str | None) -> str:
    t = L.get(lang, L["en"])
    m = json.load(open(os.path.join(run_dir, "metrics.json")))
    bp = os.path.join(run_dir, "breaks.csv")
    breaks = pd.read_csv(bp) if os.path.exists(bp) else pd.DataFrame()
    rp = os.path.join(run_dir, "residual.csv")
    residual = pd.read_csv(rp) if os.path.exists(rp) else pd.DataFrame()

    entries, eff = [], {}
    if dec_path and os.path.exists(dec_path):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import decisions as dec
        entries = dec.load(dec_path)
        eff = dec.resolve(entries)

    if len(breaks):
        cats = breaks.apply(classify_row, axis=1, result_type="expand")
        breaks["category"], breaks["confidence"] = cats[0], cats[1]
        for k, c in (eff.get("classify") or {}).items():
            breaks.loc[breaks.key.astype(str) == str(k), "category"] = c

    out = [f"# {t['title']}", ""]
    if entity:
        out.append(f"**{t['entity']}:** {entity}  ")
    if period:
        out.append(f"**{t['period']}:** {period}  ")
    out += [f"**{t['generated']}:** {pd.Timestamp.now('UTC').isoformat(timespec='seconds')}  ",
            f"**{t['materiality']}:** {m.get('materiality')}  ", ""]

    # --- scope
    out += [f"## {t['scope']}", ""]
    ds = m.get("datasets") or []
    if ds:
        out += [f"| {t['file']} | role | {t['rows']} | sum | {t['hash']} |",
                "|---|---|---:|---:|---|"]
        out += [f"| `{d.get('path')}` | {d.get('role','')} | {d.get('rows','')} | "
                f"{money(d.get('sum'))} | `{str(d.get('sha256',''))[:16]}…` |" for d in ds]
    else:
        out.append(f"_{t['none']}_")
    out += ["", f"- equation: `{m.get('sign_convention')}`",
            f"- convention evidence: {json.dumps(m.get('convention_evidence', {}))}", ""]

    # --- result
    conf_tot = {"HIGH": 0.0, "MEDIUM": 0.0, "LOW": 0.0}
    if len(breaks):
        for c in conf_tot:
            conf_tot[c] = float(breaks.loc[breaks.confidence == c, "gap"].abs().sum())
    out += [f"## {t['result']}", "",
            f"- **{t['reconciled']}:** {m.get('reconciled')} / {m.get('keys_total')} "
            f"({m.get('reconciled_pct')}%)",
            f"- **{t['gap_gross']}:** {money(m.get('gap_gross'))}",
            f"- **{t['gap_net']}:** {money(m.get('gap_net'))}",
            f"- **{t['explained']}:** {money(conf_tot['HIGH'])}",
            f"- **{t['probable']}:** {money(conf_tot['MEDIUM'])}",
            f"- **{t['unresolved']}:** {money(conf_tot['LOW'])}",
            "",
            f"- attribution rate: {m.get('attribution_rate_pct')}% "
            f"({m.get('movements_unattributed')} unattributed of {m.get('movements_total')})",
            f"- parent-level gross gap: {money(m.get('gap_gross_at_parent'))} "
            f"(vs {money(m.get('gap_gross'))} at leaf level - the difference is "
            f"misposting rather than missing value)", ""]
    if m.get("consecutive_duplicate_rows"):
        out += [f"> ⚠ {m['consecutive_duplicate_rows']} consecutive duplicate row(s) "
                f"detected (gross {money(m.get('duplicate_gross'))}). Classified "
                f"PAGEBREAK_DUPLICATION at LOW confidence and **excluded from the "
                f"explained total** until confirmed against the source document.", ""]

    # --- findings
    out += [f"## {t['findings']}", ""]
    if len(breaks):
        agg = (breaks.assign(g=breaks.gap.abs())
               .groupby(["category", "confidence"])
               .agg(accounts=("key", "count"), gross=("g", "sum"), net=("gap", "sum"))
               .reset_index().sort_values("gross", ascending=False))
        out += [f"| {t['category']} | {t['conf']} | # | {t['amount']} (gross) | (net) |",
                "|---|---|---:|---:|---:|"]
        out += [f"| `{r.category}` | `{r.confidence}` | {r.accounts} | "
                f"{money(r.gross)} | {money(r.net)} |" for r in agg.itertuples()]
        out.append("")
        for r in agg.itertuples():
            sel = breaks[(breaks.category == r.category) & (breaks.confidence == r.confidence)]
            top = sel.reindex(sel.gap.abs().sort_values(ascending=False).index).head(5)
            out += [f"### `{r.category}` · `{r.confidence}` · {money(r.gross)}", "",
                    f"- **{t['evidence']}:** {r.accounts} account(s); largest: "
                    + ", ".join(f"`{x.key}` {money(x.gap)}" for x in top.itertuples()),
                    f"- **{t['rationale']}:** _{t['wrote']}_",
                    f"- **{t['alternatives']}:** _{t['wrote']}_",
                    f"- **{t['remediation']}:** _{t['wrote']}_"]
            if r.confidence != "HIGH":
                out.append(f"- **{t['raise_conf']}:** _{t['wrote']}_")
            out.append("")
    else:
        out += [f"_{t['none']}_", ""]

    # --- open questions
    out += [f"## {t['openq']}", ""]
    q = []
    if m.get("movements_unattributed"):
        q.append((abs(float(m.get("residual_gross") or 0)),
                  f"{m['movements_unattributed']} transaction(s) could not be "
                  f"attributed to an account (gross {money(m.get('residual_gross'))}, "
                  f"net {money(m.get('residual_net'))}). Confirm the mapping for the "
                  f"largest, or supply an extraction rule covering the cluster."))
    if m.get("consecutive_duplicate_rows"):
        q.append((abs(float(m.get("duplicate_gross") or 0)),
                  f"Are the {m['consecutive_duplicate_rows']} consecutive duplicate "
                  f"row(s) page-break artifacts, or legitimate repeated instalments? "
                  f"Checking ten against the source document would settle it."))
    if len(breaks):
        low = breaks[breaks.confidence == "LOW"]
        if len(low):
            q.append((float(low.gap.abs().sum()),
                      f"{len(low)} break(s) have no determined cause "
                      f"(gross {money(low.gap.abs().sum())}). Item-level detail for "
                      f"these accounts would allow matching."))
    if q:
        for amt, text in sorted(q, reverse=True):
            out += [f"- **{t['at_stake']}: {money(amt)}** — {text}"]
    else:
        out.append(f"_{t['none']}_")
    out.append("")

    # --- decisions
    out += [f"## {t['decisions']}", ""]
    if entries:
        out += ["| id | kind | actor | conf | reason |", "|---|---|---|---|---|"]
        dead = {d["supersedes"] for d in entries if d.get("supersedes")}
        for d in entries:
            mark = "~~" if d.get("id") in dead else ""
            reason = str(d.get("reason", "")).replace("|", "\\|")
            out.append(f"| {mark}{d.get('id')}{mark} | `{d.get('kind')}` | "
                       f"{d.get('actor')} | `{d.get('confidence')}` | {reason} |")
        c = eff.get("counts", {})
        out += ["", f"{c.get('live')} live of {c.get('total')} "
                    f"({c.get('superseded')} superseded) · by actor: {c.get('by_actor')}"]
    else:
        out.append(f"_{t['none']}_")
    out.append("")

    # --- method
    out += [f"## {t['method']}", "",
            f"- sign convention established empirically: "
            f"`{m.get('sign_convention')}` "
            f"({json.dumps(m.get('convention_evidence', {}))})",
            f"- extraction rule coverage: {json.dumps(m.get('rule_coverage', {}))}",
            f"- accounts excluded from scope: {m.get('scope_excluded_keys', 0)} "
            f"(see decisions above for authority)",
            f"- decisions replayed this run: {m.get('decisions_applied', 0)}",
            "", "_" + t["wrote"] + ": what this reconciliation does not cover._", ""]

    # --- glossary
    used = set()
    if len(breaks):
        used |= set(breaks.category) | set(breaks.confidence)
    used |= {"HIGH", "MEDIUM", "LOW"}
    out += [f"## {t['glossary']}", ""]
    out += [f"- `{k}` — {GLOSSARY[k]}" for k in sorted(used) if k in GLOSSARY]
    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--decisions")
    ap.add_argument("--lang", default="en",
                    help="report language; en/pt/es have translated headings, "
                         "any other code falls back to English headings which "
                         "the agent should then translate")
    ap.add_argument("--entity")
    ap.add_argument("--period")
    ap.add_argument("--out", default="report.md")
    a = ap.parse_args()

    md = build(a.run_dir, a.decisions, a.lang, a.entity, a.period)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"wrote {a.out} ({len(md):,} chars)")
    if a.lang not in L:
        print(f"! No heading translations for '{a.lang}'. English headings were used; "
              f"translate them and the narrative into the user's language.")
    print("! Rationale, alternatives and remediation are placeholders - the agent "
          "must write them from the evidence. Do not ship the report with "
          "placeholders left in.")


if __name__ == "__main__":
    sys.exit(main())
