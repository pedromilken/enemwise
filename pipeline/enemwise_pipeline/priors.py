"""Contagens por (edição, item, banda) -> priors de BKT por (habilidade, banda).

O ENEM é uma fotografia, não um filme: não há aprendizagem entre um item e o próximo.
Daqui saem P(L0), guess e slip. P(T) não é identificável e fica com valor padrão.

Com várias edições, os priors são agregados (soma das contagens) e a variação entre
edições é reportada em p_l0_sd, para você decidir se agregar é defensável.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SLIP_MIN, SLIP_MAX = 0.02, 0.25
KEY = ["area", "habilidade", "banda", "banda_label"]


def _estimate(counts: pd.DataFrame, items: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    df = counts.merge(items[["ano", "co_item", "area", "habilidade", "c"]], on=["ano", "co_item"], how="inner")
    if df.empty:
        return pd.DataFrame(columns=by + KEY + ["n", "p_acerto", "guess", "slip", "p_l0"])
    df["c_w"] = df["c"] * df["n"]
    g = df.groupby(by + KEY, as_index=False).agg(acertos=("acertos", "sum"), n=("n", "sum"), c_w=("c_w", "sum"))
    g["p_acerto"] = g["acertos"] / g["n"]
    g["guess"] = (g["c_w"] / g["n"]).clip(0.0, 0.35)
    skill = by + ["area", "habilidade"]
    top = g.sort_values("banda").groupby(skill).tail(1)
    slip = (1 - top.set_index(skill)["p_acerto"]).clip(SLIP_MIN, SLIP_MAX)
    g["slip"] = g.set_index(skill).index.map(slip).to_numpy()
    denom = (1 - g["slip"] - g["guess"]).clip(lower=0.05)
    g["p_l0"] = ((g["p_acerto"] - g["guess"]) / denom).clip(0.01, 0.99)
    return g.drop(columns=["acertos", "c_w"])


def skill_priors(counts: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    pooled = _estimate(counts, items, [])
    per = _estimate(counts, items, ["ano"])
    if not per.empty:
        spread = (per.groupby(KEY)
                     .agg(p_l0_sd=("p_l0", "std"), n_edicoes=("ano", "nunique"))
                     .reset_index())
        pooled = pooled.merge(spread, on=KEY, how="left")
    pooled = pooled.sort_values(["area", "habilidade", "banda"]).reset_index(drop=True)
    for c in ["p_acerto", "guess", "slip", "p_l0", "p_l0_sd"]:
        if c in pooled:
            pooled[c] = pooled[c].astype(float).round(4)
    return pooled


def skill_priors_by_edition(counts: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    return _estimate(counts, items, ["ano"]).round(4)


def monotonic_share(priors: pd.DataFrame) -> float:
    """Fração de habilidades cujo acerto cresce com a banda de nota."""
    ok = [bool(np.all(np.diff(g.sort_values("banda")["p_acerto"].to_numpy()) >= -0.02))
          for _, g in priors.groupby(["area", "habilidade"])]
    return float(np.mean(ok)) if ok else float("nan")
