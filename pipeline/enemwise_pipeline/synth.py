"""Microdados sintéticos no layout do INEP, com as variações reais entre edições.

- ordem dos dias antiga (CH, CN, LC, MT) e nova (LC, CH, CN, MT)
- nomes de colunas antigos (IN_PRESENCA, NU_NT) e separador vírgula
- item anulado e língua estrangeira duplicada nas posições de LC
- fonte de texto completa (formato maritaca) e parcial genérica (sem questões "com imagem")

Nenhum dado real de participante vai para o repositório.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

LETRAS = np.array(list("ABCDE"))
D = 1.0
ORDEM_NOVA = ("LC", "CH", "CN", "MT")
ORDEM_ANTIGA = ("CH", "CN", "LC", "MT")


def p3pl(theta, a, b, c):
    return c + (1 - c) / (1 + np.exp(-D * a * (theta - b)))


def _edition(root: Path, ano: int, n: int, rng, ordem, antigo: bool) -> dict:
    pasta = root / f"microdados_enem_{ano}" / "DADOS"
    pasta.mkdir(parents=True, exist_ok=True)
    rows, co_item = [], ano * 1000
    provas = {a: (ano * 10 + i * 2 + 1, ano * 10 + i * 2 + 2) for i, a in enumerate(ORDEM_NOVA)}
    for bloco, area in enumerate(ordem):
        lo = 1 + 45 * bloco
        k = 45
        it = pd.DataFrame({
            "CO_ITEM": np.arange(co_item, co_item + k), "SG_AREA": area,
            "CO_HABILIDADE": rng.integers(1, 31, k),
            "NU_PARAM_A": rng.lognormal(0.7, 0.3, k).round(4),
            "NU_PARAM_B": rng.normal(0.8, 0.9, k).round(4),
            "NU_PARAM_C": rng.beta(4, 18, k).round(4),
            "TX_GABARITO": rng.choice(LETRAS, k), "TP_LINGUA": np.nan,
            "IN_ITEM_ABAN": 0, "IN_ITEM_ADAPTADO": 0,
        })
        co_item += k
        esp = None
        if area == "LC":
            it.loc[:4, "TP_LINGUA"] = 0
            esp = it.iloc[:5].copy()
            esp["CO_ITEM"] = np.arange(co_item, co_item + 5)
            esp["TP_LINGUA"], esp["TX_GABARITO"] = 1, rng.choice(LETRAS, 5)
            co_item += 5
        if area == "MT":
            it.loc[10, "IN_ITEM_ABAN"] = 1
        for cor, (co_prova, perm) in enumerate([(provas[area][0], np.arange(k)), (provas[area][1], rng.permutation(k))]):
            b = it.iloc[perm].copy()
            b["CO_POSICAO"] = np.arange(lo, lo + k)
            b["CO_PROVA"], b["TX_COR"] = co_prova, ["AZUL", "AMARELA"][cor]
            rows.append(b)
            if esp is not None:
                e = esp.copy()
                e["CO_POSICAO"] = b["CO_POSICAO"].iloc[:5].to_numpy() if cor == 0 else np.arange(lo, lo + 5)
                e["CO_PROVA"], e["TX_COR"] = co_prova, ["AZUL", "AMARELA"][cor]
                rows.append(e)
    itens = pd.concat(rows, ignore_index=True)
    sep = "," if antigo else ";"
    itens_path = pasta / f"ITENS_PROVA_{ano}.csv"
    itens.to_csv(itens_path, sep=sep, index=False, encoding="latin-1")

    g = rng.normal(0, 1, n)
    pres_col, nota_col = ("IN_PRESENCA_{a}", "NU_NT_{a}") if antigo else ("TP_PRESENCA_{a}", "NU_NOTA_{a}")
    micro = {"NU_INSCRICAO": np.arange(n)}
    for area in ("CH", "CN", "MT"):
        theta = 0.7 * g + np.sqrt(1 - 0.49) * rng.normal(0, 1, n)
        present = rng.random(n) > 0.05
        booklet = rng.integers(0, 2, n)
        strings = np.empty(n, dtype=object)
        gabaritos = np.empty(n, dtype=object)
        for bi, co_prova in enumerate(provas[area]):
            lay = itens[itens["CO_PROVA"] == co_prova].sort_values("CO_POSICAO")
            a, b, c = (lay[x].to_numpy() for x in ("NU_PARAM_A", "NU_PARAM_B", "NU_PARAM_C"))
            idx = np.where(booklet == bi)[0]
            p = p3pl(theta[idx, None], a, b, c)
            hit = rng.random(p.shape) < p
            wrong = np.array([[l for l in LETRAS if l != gab] for gab in lay["TX_GABARITO"]])
            resp = np.where(hit, lay["TX_GABARITO"].to_numpy()[None, :],
                            wrong[np.arange(len(lay))[None, :], rng.integers(0, 4, p.shape)])
            resp[rng.random(p.shape) < 0.02] = "."
            strings[idx] = ["".join(r) for r in resp]
            gabaritos[idx] = "".join(lay["TX_GABARITO"])
        micro[pres_col.format(a=area)] = present.astype(int)
        micro[f"CO_PROVA_{area}"] = np.where(present, np.array(provas[area])[booklet], np.nan)
        micro[nota_col.format(a=area)] = np.where(
            present, np.clip(500 + 100 * theta + rng.normal(0, 25, n), 300, 950).round(1), np.nan)
        micro[f"TX_RESPOSTAS_{area}"] = np.where(present, strings, None)
        micro[f"TX_GABARITO_{area}"] = np.where(present, gabaritos, None)
    micro_path = pasta / f"MICRODADOS_ENEM_{ano}.csv"
    pd.DataFrame(micro).to_csv(micro_path, sep=sep, index=False, encoding="latin-1")
    return {"itens": itens_path, "microdados": micro_path, "tabela": itens, "provas": provas}


def _azul(itens: pd.DataFrame, provas: dict) -> pd.DataFrame:
    azul = itens[itens["CO_PROVA"].isin([p[0] for p in provas.values()])]
    return azul[azul["TP_LINGUA"].isna() | (azul["TP_LINGUA"] == 0)].sort_values("CO_POSICAO")


def _texto(r, ano) -> str:
    return (f"Item sintético de demonstração ({ano}). Área {r.SG_AREA}, habilidade H{int(r.CO_HABILIDADE)}. "
            f"Dificuldade TRI b = {r.NU_PARAM_B:.2f}. Marque a alternativa {r.TX_GABARITO} para acertar.")


def generate(out: str | Path, anos=(2097, 2098, 2099), n: int = 8000, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    root = Path(out) / "inep"
    textos = Path(out) / "textos"
    textos.mkdir(parents=True, exist_ok=True)
    result = {"raiz": root, "questoes": []}
    for i, ano in enumerate(anos):
        antigo = i == 0
        ed = _edition(root, ano, n, rng, ORDEM_ANTIGA if antigo else ORDEM_NOVA, antigo)
        result[ano] = {k: ed[k] for k in ("itens", "microdados")}
        azul = _azul(ed["tabela"], ed["provas"])
        if i == len(anos) - 1:  # fonte completa, formato maritaca-ai/enem
            lines = [json.dumps({"id": f"questao_{int(r.CO_POSICAO):02d}", "exam": str(ano), "IU": False,
                                 "ledor": True, "question": _texto(r, ano), "description": [], "figures": [],
                                 "alternatives": [f"Alternativa {l} do item {int(r.CO_ITEM)}." for l in LETRAS],
                                 "label": r.TX_GABARITO}, ensure_ascii=False) for r in azul.itertuples()]
            path = textos / f"maritaca_{ano}.jsonl"
        elif antigo:  # fonte parcial genérica: ~60% das questões, choices em dicionário
            keep = azul.sample(frac=0.6, random_state=seed)
            lines = [json.dumps({"id": f"{ano}_{int(r.CO_POSICAO)}", "exam": str(ano), "question": _texto(r, ano),
                                 "choices": {"text": [f"Alternativa {l}." for l in LETRAS], "label": list(LETRAS)},
                                 "answerKey": r.TX_GABARITO}, ensure_ascii=False) for r in keep.itertuples()]
            path = textos / f"challenge_{ano}.jsonl"
        else:
            continue  # edição sem texto aberto: entra só nos priors
        path.write_text("\n".join(lines), encoding="utf-8")
        result["questoes"].append(path)
    return result
