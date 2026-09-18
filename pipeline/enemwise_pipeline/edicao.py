"""Processa UMA edição e grava a pasta de saída dela (entrada do merge)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

from . import audit, conteudos as con, items as itm, link_text, priors as pri, responses

AREAS_BRUTAS = ("CN", "CH", "MT")


def build_edition(ano: int, itens: Path, microdados: Path | None, out: Path,
                  questoes: list[pd.DataFrame] | None = None, longos: dict[str, Path] | None = None,
                  lingua: int = 0, nrows: int | None = None, longo_cfg=None) -> dict:
    t0 = time.time()
    out.mkdir(parents=True, exist_ok=True)
    longos = longos or {}
    raw = itm.load_itens(itens)
    booklets = itm.filter_booklets(raw, lingua=lingua)
    canon = itm.canonical_items(itm.usable_items(booklets), ano)
    layout = itm.booklet_layout(booklets)

    frames, stats = [], {}
    for area in ("CN", "CH", "LC", "MT"):
        if longo_cfg is not None:  # fonte única: exportação longa auditada, as quatro áreas
            print(f"[{ano}] {area}: exportação longa v9.2", file=sys.stderr)
            frames.append(responses.aggregate_longo_cfg(longo_cfg, ano, area))
            stats[area] = {"fonte": "v9.2"}
        elif area in longos:
            print(f"[{ano}] {area}: caminho longo {longos[area].name}", file=sys.stderr)
            frames.append(responses.aggregate_long(longos[area], ano))
        elif area in AREAS_BRUTAS and microdados is not None:
            print(f"[{ano}] {area}: caminho bruto", file=sys.stderr)
            c, s = responses.aggregate_area(microdados, area, layout, ano, nrows=nrows)
            frames.append(c)
            stats[area] = s
        else:
            stats[area] = {"ignorada": "sem arquivo longo" if area == "LC" else "sem microdados"}
    counts = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=responses.COLS)

    links, vinculo = pd.DataFrame(), []
    for qdf in questoes or []:
        qa = qdf[qdf["ano"] == ano]
        if qa.empty:
            continue
        lk, rep = link_text.fingerprint_link(qa, layout)
        vinculo += [dict(r, fonte=qa["fonte"].iloc[0]) for r in rep]
        links = pd.concat([links, lk], ignore_index=True)
    if not links.empty:  # fontes listadas primeiro têm prioridade (ex.: maritaca, com descrição de imagens)
        links = links.drop_duplicates("co_item", keep="first")

    full = canon.copy()
    if not counts.empty:
        pb = (counts.assign(p=lambda d: (d["acertos"] / d["n"]).round(3))
                    .pivot_table(index="co_item", columns="banda", values="p"))
        full["p_banda"] = full["co_item"].map(
            lambda i: [None if pd.isna(v) else float(v) for v in pb.loc[i]] if i in pb.index else None)
    if not links.empty:
        full = full.merge(links, on="co_item", how="left")
    if "cor_caderno" in full:
        full["cor_caderno"] = full["cor_caderno"].where(full["cor_caderno"].notna(), None)
    if "enunciado" in full:
        full = con.rotular(full)  # conteúdos programáticos a partir do texto da questão

    auditoria = audit.alignment_audit(counts, canon, booklets, ano) if not counts.empty else []
    relatorio = {
        "ano": ano, "segundos": round(time.time() - t0, 1),
        "itens_utilizaveis": int(len(canon)),
        "itens_com_texto": int(full["enunciado"].notna().sum()) if "enunciado" in full else 0,
        "auditoria": auditoria, "vinculo_texto": vinculo, "respostas": stats,
    }
    counts.to_csv(out / "counts.csv", index=False)
    (out / "items_full.json").write_text(full.to_json(orient="records", force_ascii=False), encoding="utf-8")
    if not counts.empty:
        pri.skill_priors_by_edition(counts, canon).to_csv(out / "priors_edicao.csv", index=False)
    (out / "relatorio.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return relatorio
