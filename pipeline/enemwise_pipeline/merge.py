"""Junta as pastas de todas as edições no pacote servido pelo app.

Saída em web/public/data:
  meta.json            edições, bandas, auditorias e vínculos
  priors.json          priors agregados de todas as edições (com p_l0_sd entre edições)
  items/<ano>.json     só itens com texto, que são os praticáveis no app
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import audit as aud_mod, conteudos as con, priors as pri
from .schema import AREA_NOME, BANDAS, banda_label

LIMITE_MB = 25


def _clean(records: list[dict]) -> list[dict]:
    for r in records:
        for k in [k for k, v in r.items() if v is None or (isinstance(v, float) and pd.isna(v))]:
            del r[k]
    return records


def merge(entrada: Path, web: Path, D: float = 1.0, sintetico: bool = False, incluir_reprovadas: bool = False) -> dict:
    pastas = sorted(p for p in Path(entrada).iterdir() if (p / "relatorio.json").exists())
    if not pastas:
        raise SystemExit(f"Nenhuma edição processada em {entrada}.")
    counts, itens, relatorios = [], [], []
    for p in pastas:
        relatorios.append(json.loads((p / "relatorio.json").read_text(encoding="utf-8")))
        c = pd.read_csv(p / "counts.csv")
        if not c.empty:
            counts.append(c)
        itens.append(pd.read_json(p / "items_full.json", orient="records"))
    counts_all = pd.concat(counts, ignore_index=True) if counts else pd.DataFrame()
    items_all = pd.concat(itens, ignore_index=True)

    aud = []
    for r in relatorios:
        for a in r["auditoria"]:
            a = dict(a)
            if not counts_all.empty:  # recalcula com o critério atual e o D informado, sem rodar o batch de novo
                cel = items_all[(items_all["ano"] == r["ano"]) & (items_all["area"] == a["area"])]
                a.update(aud_mod.metricas_celula(counts_all[counts_all["ano"] == r["ano"]], cel, D))
            a["ok"] = aud_mod.aprovado(a)
            # célula da exportação v9.2: cadernos já certificados contra o gabarito impresso (>= 90%)
            a["certificada"] = (r.get("respostas", {}).get(a["area"]) or {}).get("fonte") == "v9.2"
            aud.append(a)
    reprovadas = {(int(a["ano"]), a["area"]) for a in aud if a.get("ok") is False and not a["certificada"]}
    alertas = [a for a in aud if a.get("ok") is False and a["certificada"]]
    if reprovadas and not incluir_reprovadas and not counts_all.empty:
        # célula reprovada na auditoria não contamina os priors agregados
        area_of = items_all.set_index(["ano", "co_item"])["area"]
        cell = pd.MultiIndex.from_frame(counts_all[["ano", "co_item"]]).map(lambda k: (k[0], area_of.get(k)))
        counts_all = counts_all[[c not in reprovadas for c in cell]]
    # alerta em célula certificada: alinhamento confiável, parâmetros publicados não. Reestima a e b.
    if alertas:
        for col in ("a_inep", "b_inep", "parametros"):
            if col not in items_all:
                items_all[col] = pd.Series([None] * len(items_all), dtype=object if col == "parametros" else float)
    for a in alertas:
        mask = (items_all["ano"] == a["ano"]) & (items_all["area"] == a["area"])
        cnt = counts_all[counts_all["ano"] == a["ano"]]
        items_all.loc[mask] = aud_mod.reajustar_parametros(cnt, items_all.loc[mask], D)
        depois = aud_mod.metricas_celula(cnt, items_all.loc[mask], D)
        a["rho_p_esperado_reajustado"] = depois.get("rho_p_esperado")
        a["itens_reajustados"] = int(items_all.loc[mask].get("parametros", pd.Series(dtype=object)).notna().sum())
    cache_res = Path(entrada) / "resolucoes.json"
    if cache_res.exists():
        res = json.loads(cache_res.read_text(encoding="utf-8"))
        items_all["resolucao"] = items_all["id"].map(res)
    priors = pri.skill_priors(counts_all, items_all) if not counts_all.empty else pd.DataFrame()
    web = Path(web)
    (web / "items").mkdir(parents=True, exist_ok=True)
    for old in (web / "items").glob("*.json"):
        old.unlink()
    edicoes_texto = []
    for ano, g in items_all.groupby("ano"):
        if "enunciado" not in g or g["enunciado"].notna().sum() == 0:
            continue
        g = g[g["enunciado"].notna()]
        (web / "items" / f"{int(ano)}.json").write_text(
            json.dumps(_clean(json.loads(g.to_json(orient="records", force_ascii=False))), ensure_ascii=False),
            encoding="utf-8")
        edicoes_texto.append(int(ano))
    (web / "priors.json").write_text(priors.to_json(orient="records", force_ascii=False), encoding="utf-8")

    meta = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sintetico": sintetico, "D": D,
        "areas": AREA_NOME, "bandas": [banda_label(*b) for b in BANDAS],
        "edicoes": sorted(int(r["ano"]) for r in relatorios),
        "edicoes_com_texto": edicoes_texto,
        "n_itens_com_texto": int(sum(r["itens_com_texto"] for r in relatorios)),
        "auditoria_reprovada": sorted(f"{ano}-{area}" for ano, area in reprovadas),
        "auditoria_alertas_certificadas": sorted(f'{a["ano"]}-{a["area"]}' for a in alertas),
        "parametros_reajustados": [{k: a.get(k) for k in ("ano", "area", "rho_p_esperado", "rho_p_esperado_reajustado",
                                                          "itens_reajustados")} for a in alertas],
        "reprovadas_nos_priors": bool(incluir_reprovadas),
        "auditoria": aud,
        "vinculo_texto": [dict(v, ano=r["ano"]) for r in relatorios for v in r["vinculo_texto"]],
        "conteudos": con.catalogo(),
        "n_itens_com_resolucao": int(items_all["resolucao"].notna().sum()) if "resolucao" in items_all else 0,
        "cobertura_conteudos": (con.cobertura(items_all[items_all["enunciado"].notna()]).to_dict(orient="records")
                                if "topicos" in items_all and "enunciado" in items_all else []),
        "diagnostico_monotonia": pri.monotonic_share(priors) if not priors.empty else None,
        "fonte": "Microdados do ENEM (INEP)" + ("; dados sintéticos de demonstração" if sintetico else ""),
    }
    (web / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    mb = sum(f.stat().st_size for f in web.rglob("*.json")) / 1e6
    meta["tamanho_mb"] = round(mb, 2)
    if mb > LIMITE_MB:
        print(f"AVISO: pacote com {mb:.1f} MB. Considere carregar edições sob demanda.")
    return meta
