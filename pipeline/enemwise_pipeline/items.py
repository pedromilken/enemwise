"""ITENS_PROVA -> banco canônico de itens com parâmetros TRI e ordem de cada caderno."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import leitura as io
from .schema import ITENS_OPTIONAL, ITENS_REQUIRED


def load_itens(path: str | Path) -> pd.DataFrame:
    cols = io.columns(path)
    keep = [c for c in ITENS_REQUIRED + ITENS_OPTIONAL if io.resolve(cols, [c])]
    missing = set(ITENS_REQUIRED) - set(keep)
    if missing:
        raise ValueError(f"{Path(path).name} sem colunas obrigatórias {sorted(missing)}. Disponíveis: {cols}")
    df = pd.read_csv(path, usecols=[io.resolve(cols, [c]) for c in keep], **io.sniff(path))
    df.columns = [c.upper() for c in df.columns]
    df["TX_GABARITO"] = df["TX_GABARITO"].astype(str).str.strip().str.upper()
    return df


def filter_booklets(df: pd.DataFrame, lingua: int = 0) -> pd.DataFrame:
    """Mantém cadernos regulares e a língua estrangeira escolhida. Itens anulados FICAM:
    ocupam posição na string de respostas e removê-los desalinharia o caderno.

    lingua: 0 = inglês, 1 = espanhol (convenção TP_LINGUA do INEP).
    """
    out = df.copy()
    if "IN_ITEM_ADAPTADO" in out:
        out = out[out["IN_ITEM_ADAPTADO"].fillna(0).astype(int) != 1]
    if "TP_LINGUA" in out:
        out = out[out["TP_LINGUA"].isna() | (out["TP_LINGUA"] == lingua)]
    out["CO_POSICAO"] = out["CO_POSICAO"].astype(int)
    return out.reset_index(drop=True)


SEM_HABILIDADE = 0  # INEP não informou CO_HABILIDADE: o item entra como "H0" da área


def usable_items(df: pd.DataFrame) -> pd.DataFrame:
    """Itens que entram no banco de treino: não anulados e com parâmetros TRI.

    Parâmetros são obrigatórios (sem eles não há TRI). A habilidade não: algumas edições
    não a informam, e descartar o item jogaria fora questões com texto. Esses itens
    ficam na habilidade 0 da área.
    """
    out = df
    if "IN_ITEM_ABAN" in out:
        out = out[out["IN_ITEM_ABAN"].fillna(0).astype(int) != 1]
    need = ["NU_PARAM_A", "NU_PARAM_B", "NU_PARAM_C"]
    if any(c not in out for c in need):
        return out.iloc[0:0]
    out = out.dropna(subset=need).copy()
    if "CO_HABILIDADE" not in out:
        out["CO_HABILIDADE"] = SEM_HABILIDADE
    out["CO_HABILIDADE"] = pd.to_numeric(out["CO_HABILIDADE"], errors="coerce").fillna(SEM_HABILIDADE).astype(int)
    return out.reset_index(drop=True)


def canonical_items(df: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Um registro por CO_ITEM (o mesmo item aparece embaralhado em vários cadernos)."""
    if df.empty:
        return pd.DataFrame(columns=["id", "co_item", "ano", "area", "habilidade", "a", "b", "c", "gabarito"])
    g = df.sort_values("CO_POSICAO").groupby("CO_ITEM", as_index=False).first()
    return pd.DataFrame({
        "id": [f"{ano}-{int(i)}" for i in g["CO_ITEM"]],
        "co_item": g["CO_ITEM"].astype(int),
        "ano": ano,
        "area": g["SG_AREA"].astype(str),
        "habilidade": g["CO_HABILIDADE"].astype(int),
        "a": g["NU_PARAM_A"].astype(float).round(4),
        "b": g["NU_PARAM_B"].astype(float).round(4),
        "c": g["NU_PARAM_C"].astype(float).round(4),
        "gabarito": g["TX_GABARITO"].astype(str),
    })


def booklet_layout(df: pd.DataFrame) -> dict[int, pd.DataFrame]:
    """CO_PROVA -> itens na ordem em que aparecem no caderno (CO_POSICAO crescente)."""
    return {int(k): v.sort_values("CO_POSICAO")[["CO_POSICAO", "CO_ITEM", "TX_GABARITO", "SG_AREA"]]
            .reset_index(drop=True)
            for k, v in df.groupby("CO_PROVA")}
