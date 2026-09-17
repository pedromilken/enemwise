"""Avaliação prequencial do modelo a partir das exportações dos estudantes.

Cada tentativa guarda a previsão feita ANTES da resposta (pPrevisto). Isso evita o
vazamento de avaliar o modelo com dados que ele já viu.

Métricas relatadas para as DUAS classes, com "erro" como classe de interesse (é o
análogo de "em risco"). Motivo: no SPPA as métricas binárias são compatíveis com
"aprovado" como classe positiva, o que infla recall e precisão quando o objetivo é
achar quem vai mal. Toda métrica vem ao lado de linhas de base.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def carregar_exportacoes(pasta: str | Path) -> pd.DataFrame:
    rows = []
    for f in sorted(Path(pasta).glob("*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        if s.get("versao") != 1:
            continue
        for ordem, t in enumerate(s.get("tentativas", [])):
            rows.append({"estudante": s.get("nome", f.stem), "ordem": ordem, **t})
    return pd.DataFrame(rows)


def auc(y: np.ndarray, score: np.ndarray) -> float:
    pos, neg = score[y == 1], score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    u = stats.mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return float(u / (len(pos) * len(neg)))


def _classe(y_true: np.ndarray, y_pred: np.ndarray, positivo: int) -> dict:
    tp = int(((y_pred == positivo) & (y_true == positivo)).sum())
    fp = int(((y_pred == positivo) & (y_true != positivo)).sum())
    fn = int(((y_pred != positivo) & (y_true == positivo)).sum())
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if prec + rec and not np.isnan(prec + rec) else float("nan")
    return {"precisao": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4), "suporte": int((y_true == positivo).sum())}


def calibracao(y: np.ndarray, p: np.ndarray, bins: int = 10) -> tuple[float, list[dict]]:
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    tabela, ece = [], 0.0
    for b in range(bins):
        m = idx == b
        if m.sum() == 0:
            continue
        conf, obs = float(p[m].mean()), float(y[m].mean())
        ece += m.mean() * abs(conf - obs)
        tabela.append({"faixa": f"{edges[b]:.1f}-{edges[b+1]:.1f}", "n": int(m.sum()),
                       "previsto": round(conf, 3), "observado": round(obs, 3)})
    return round(float(ece), 4), tabela


def metricas(y: np.ndarray, p: np.ndarray, limiar: float = 0.5) -> dict:
    """y: 1 = acerto. p: probabilidade prevista de acerto."""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    pred = (p >= limiar).astype(int)
    ece, tab = calibracao(y, p)
    return {
        "n": int(len(y)),
        "acuracia": round(float((pred == y).mean()), 4),
        "auc": round(auc(y, p), 4),
        "brier": round(float(np.mean((p - y) ** 2)), 4),
        "log_loss": round(float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))), 4),
        "ece": ece,
        "classe_erro": _classe(y, pred, 0),
        "classe_acerto": _classe(y, pred, 1),
        "f1_macro": round(float(np.nanmean([_classe(y, pred, 0)["f1"], _classe(y, pred, 1)["f1"]])), 4),
        "calibracao": tab,
    }


def avaliar(df: pd.DataFrame, excluir_dica: bool = True) -> dict:
    d = df.dropna(subset=["pPrevisto"]).copy()
    if excluir_dica and "usouDica" in d:
        d = d[~d["usouDica"].astype(bool)]
    y = d["correta"].astype(int).to_numpy()
    out = {"tentativas": int(len(d)), "estudantes": int(d["estudante"].nunique()),
           "prevalencia_acerto": round(float(y.mean()), 4) if len(y) else None}
    if len(d) < 30:
        out["aviso"] = "Menos de 30 tentativas com previsão registrada: métricas instáveis."
    if len(d) == 0:
        return out
    # linha de base 1: prevalência histórica acumulada (sem olhar o futuro)
    acum = np.concatenate([[0.5], np.cumsum(y)[:-1] / np.arange(1, len(y))])
    out["modelo_bkt"] = metricas(y, d["pPrevisto"].to_numpy(float))
    out["base_prevalencia"] = metricas(y, acum)
    if "pBanda" in d and d["pBanda"].notna().any():
        m = d["pBanda"].notna().to_numpy()
        out["base_acerto_da_faixa"] = metricas(y[m], d.loc[m, "pBanda"].to_numpy(float))
        out["modelo_bkt_mesmo_recorte"] = metricas(y[m], d.loc[m, "pPrevisto"].to_numpy(float))
    if "confianca" in d and d["confianca"].notna().any():
        out["autoavaliacao"] = (d.dropna(subset=["confianca"]).groupby("confianca")["correta"]
                                .agg(["count", "mean"]).round(3).rename(columns={"count": "n", "mean": "acerto"})
                                .to_dict(orient="index"))
    return out
