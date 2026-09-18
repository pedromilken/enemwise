"""Liga CO_ITEM ao texto da questão.

Os microdados não trazem enunciado. Fontes abertas cobrem só parte das edições e numeram
as questões por um caderno que nem sempre é informado. Em vez de supor a cor e a ordem
dos dias, comparamos gabaritos: a sequência de letras funciona como impressão digital do
caderno. Isso vale mesmo com cobertura parcial (fontes que omitem questões com imagem).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from . import texto
from .schema import BLOCK_STARTS

NORM = ["ano", "aplicacao", "numero", "enunciado", "alternativas", "gabarito", "descricao", "figuras", "fonte"]


def _first(d: dict, keys: list[str]):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _alternativas(v) -> list[str] | None:
    if isinstance(v, dict) and "text" in v:
        v = v["text"]
    if hasattr(v, "tolist"):
        v = v.tolist()
    return [str(x) for x in v] if isinstance(v, (list, tuple)) and len(v) == 5 else None


def _records(path: Path) -> list[dict]:
    if path.suffix == ".parquet":
        return pd.read_parquet(path).to_dict("records")
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("data", [])
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_questions(path: str | Path, ano_padrao: int | None = None) -> pd.DataFrame:
    """Normaliza fontes conhecidas (maritaca-ai/enem) e genéricas com colunas usuais.

    O ano vem de `exam`/`exam_id`/`ano` ou do prefixo do id ("2016_45"). Sufixo de
    aplicação ("2016_2") vira `aplicacao`; só a aplicação 1 é vinculada por padrão.
    """
    path = Path(path)
    out = []
    for r in _records(path):
        rid = str(_first(r, ["id", "question_id"]) or "")
        exam = str(_first(r, ["exam_id", "exam", "ano", "year"]) or "")
        m_exam = re.match(r"^(\d{4})(?:_(\d))?", exam)
        m_id = re.match(r"^(\d{4})(?:_(\d))?_(\d+)$", rid)
        ano = int(m_exam.group(1)) if m_exam else (int(m_id.group(1)) if m_id else ano_padrao)
        aplic = int((m_exam and m_exam.group(2)) or (m_id and m_id.group(2)) or 1)
        num = re.findall(r"(\d+)", rid)
        alts = _alternativas(_first(r, ["alternatives", "alternativas", "choices", "options"]))
        if ano is None or not num or alts is None:
            continue
        out.append({
            "ano": ano, "aplicacao": aplic, "numero": int(num[-1]),
            "enunciado": texto.formatar_formulas(str(_first(r, ["question", "enunciado", "stem", "context"]) or "")),
            "alternativas": [texto.formatar_formulas(a) or "" for a in alts],
            "gabarito": str(_first(r, ["label", "answerKey", "answer", "gabarito"]) or "").strip().upper()[:1],
            "descricao": list(_first(r, ["description", "descricao"]) or []),
            "figuras": list(_first(r, ["figures", "figuras"]) or []),
            "fonte": path.name,
        })
    return pd.DataFrame(out, columns=NORM)


def _numberings(lay: pd.DataFrame) -> dict[str, pd.Series]:
    """Hipóteses de numeração do caderno: posição absoluta ou bloco de 45 em cada início."""
    rank = pd.Series(range(len(lay)), index=lay.index)
    hyp = {"absoluta": lay["CO_POSICAO"].astype(int)}
    for s in BLOCK_STARTS:
        hyp[f"bloco_{s}"] = rank + s
    return hyp


def fingerprint_link(questions: pd.DataFrame, layout: dict[int, pd.DataFrame],
                     min_match: float = 0.9, min_overlap: int = 12) -> tuple[pd.DataFrame, list[dict]]:
    q = (questions[questions["aplicacao"] == 1]
         .drop_duplicates("numero").set_index("numero"))
    links, report = [], []
    areas = sorted({a for lay in layout.values() for a in lay["SG_AREA"].unique()})
    for area in areas:
        best = None
        for co_prova, lay in layout.items():
            la = lay[lay["SG_AREA"] == area]
            if la.empty:
                continue
            for hname, nums in _numberings(la).items():
                common = nums[nums.isin(q.index)]
                if len(common) < min_overlap:
                    continue
                gab = la.loc[common.index, "TX_GABARITO"].to_numpy()
                match = float((gab == q.loc[common.to_numpy(), "gabarito"].to_numpy()).mean())
                score = (match, len(common))
                if best is None or score > best[0]:
                    best = (score, co_prova, hname, la, common)
        if best is None:
            report.append({"area": area, "aceito": False, "motivo": "sem sobreposição suficiente"})
            continue
        (match, overlap), co_prova, hname, la, common = best
        aceito = match >= min_match
        report.append({"area": area, "co_prova": co_prova, "numeracao": hname, "match": round(match, 4),
                       "questoes_vinculadas": overlap if aceito else 0, "aceito": aceito})
        if not aceito:
            continue
        cor = str(la["TX_COR"].dropna().iloc[0]).strip().title() if "TX_COR" in la and la["TX_COR"].notna().any() else None
        report[-1]["cor"] = cor
        for idx, numero in common.items():
            row = q.loc[numero]
            links.append({"co_item": int(la.loc[idx, "CO_ITEM"]), "numero": int(numero), "cor_caderno": cor,
                          "enunciado": row["enunciado"], "alternativas": row["alternativas"],
                          "descricao": row["descricao"], "figuras": row["figuras"], "fonte_texto": row["fonte"]})
    return pd.DataFrame(links), report
