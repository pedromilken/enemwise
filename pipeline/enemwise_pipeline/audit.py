"""Auditoria automática de alinhamento por (edição, área).

Analogia: se o caderno estiver desalinhado, é como corrigir a prova com o gabarito de
outra cor. O acerto observado deixa de acompanhar o que a TRI prevê para cada item.

Critério principal: correlação de Spearman entre o acerto observado e o acerto ESPERADO
pelo 3PL (a, b, c do INEP), dada a composição de faixas de nota de quem respondeu
cada item. Tem de ficar acima de 0,6.

Por que não usar só o parâmetro b: em provas difíceis (MT e CN do ENEM, acerto médio
perto de 25%), muitos itens ficam no piso do chute. No piso, o acerto é dado por c, não
por b, e a correlação com b despenca mesmo com alinhamento perfeito. Em simulação com
b médio 2,5 ela chega a -0,14, enquanto a correlação com o acerto esperado fica em 0,99.
A correlação com b e a fração perto do acaso seguem no relatório, só como informação.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import BANDAS

RHO_ESPERADO_MIN = 0.6  # Spearman(acerto observado, acerto esperado pelo 3PL)
RHO_MAX = -0.4          # critério antigo, usado só quando não há parâmetros para o esperado
FRAC_ACASO_MAX = 0.30   # informativo


def aprovado(rec: dict) -> bool | None:
    if rec.get("rho_p_esperado") is not None:
        return bool(rec["rho_p_esperado"] >= RHO_ESPERADO_MIN)
    rho = rec.get("rho_p_b")
    return None if rho is None else bool(rho <= RHO_MAX)


def _theta_banda() -> np.ndarray:
    centros = [(400 if lo == 0 else (lo + min(hi, 1000)) / 2 if hi <= 1000 else 800) for lo, hi in BANDAS]
    return (np.array(centros, dtype=float) - 500) / 100


def metricas_celula(counts: pd.DataFrame, items: pd.DataFrame, D: float = 1.0) -> dict:
    """counts de UMA célula (co_item, banda, acertos, n) + itens com a, b, c."""
    it = items.drop_duplicates("co_item").set_index("co_item")
    g = counts[counts["co_item"].isin(it.index)]
    if g.empty:
        return {}
    th = _theta_banda()
    g = g.assign(a=g["co_item"].map(it["a"]), b=g["co_item"].map(it["b"]), c=g["co_item"].map(it["c"]))
    g = g.assign(esp=g["c"] + (1 - g["c"]) / (1 + np.exp(-D * g["a"] * (th[g["banda"].to_numpy()] - g["b"]))))
    por = g.assign(esp_n=g["esp"] * g["n"]).groupby("co_item").agg(acertos=("acertos", "sum"), n=("n", "sum"), esp_n=("esp_n", "sum"))
    por["p"] = por["acertos"] / por["n"]
    por["esp"] = por["esp_n"] / por["n"]
    por = por.join(it[["b", "c"]])
    if len(por) < 10:
        return {"itens_com_respostas": int(len(por))}
    return {"itens_com_respostas": int(len(por)),
            "rho_p_esperado": round(float(por["p"].corr(por["esp"], method="spearman")), 3),
            "erro_medio_esperado": round(float((por["p"] - por["esp"]).abs().mean()), 3),
            "rho_p_b": round(float(por["p"].corr(por["b"], method="spearman")), 3),
            "frac_perto_acaso": round(float((por["p"] <= por["c"] + 0.03).mean()), 3),
            "p_medio": round(float(por["p"].mean()), 3)}


def alignment_audit(counts: pd.DataFrame, items: pd.DataFrame, raw_items: pd.DataFrame, ano: int,
                    D: float = 1.0) -> list[dict]:
    rows = []
    for area, ra in raw_items.groupby("SG_AREA"):
        canon = items[items["area"] == area]
        rec = {"ano": ano, "area": area, "itens_no_arquivo": int(ra["CO_ITEM"].nunique()),
               "itens_utilizaveis": int(len(canon))}
        rec.update(metricas_celula(counts, canon, D))
        rec["ok"] = aprovado(rec)
        rows.append(rec)
    return rows


def reajustar_parametros(counts: pd.DataFrame, items: pd.DataFrame, D: float = 1.0) -> pd.DataFrame:
    """Reestima a e b de cada item pelas respostas por faixa, mantendo o c do INEP.

    Usado só em células certificadas cuja auditoria falhou: o alinhamento é confiável
    (gabarito conferido), mas os parâmetros publicados não acompanham o acerto observado.
    Máxima verossimilhança binomial sobre as 5 faixas de nota, com limites plausíveis.
    """
    from scipy.optimize import minimize

    th = _theta_banda()
    out = items.copy()
    for idx, it in items.iterrows():
        g = counts[counts["co_item"] == it["co_item"]]
        if g["n"].sum() < 200 or g["banda"].nunique() < 3:
            continue
        t, n, y = th[g["banda"].to_numpy()], g["n"].to_numpy(float), g["acertos"].to_numpy(float)
        c = float(np.clip(it["c"], 0.0, 0.45))

        def nll(x):
            a, b = x
            p = np.clip(c + (1 - c) / (1 + np.exp(-D * a * (t - b))), 1e-6, 1 - 1e-6)
            return -np.sum(y * np.log(p) + (n - y) * np.log(1 - p))

        p_obs = np.clip(y.sum() / n.sum(), c + 0.01, 0.99)
        b0 = float(np.clip(-np.log((1 - c) / (p_obs - c) - 1) / (D * 1.0), -3, 5))
        r = minimize(nll, x0=[1.0, b0], method="L-BFGS-B", bounds=[(0.2, 5.0), (-4.0, 6.0)])
        if r.success:
            out.loc[idx, ["a_inep", "b_inep"]] = [it["a"], it["b"]]
            out.loc[idx, ["a", "b"]] = [round(float(r.x[0]), 4), round(float(r.x[1]), 4)]
            out.loc[idx, "parametros"] = "reajustados pelas respostas (c do INEP)"
    return out
