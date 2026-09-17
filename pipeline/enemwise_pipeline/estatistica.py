"""Estatística para avaliar intervenções com o ENEMWise.

Segue o desenho quase-experimental do SPPA (Alalawi et al., 2025): qui-quadrado com
post hoc de Bonferroni, teste t e pareamento por escore de propensão. Com três ajustes
motivados pela reprodução numérica daquele artigo (ver docs/FUNDAMENTACAO.md):

1. intenção de tratar por padrão: quem desistiu continua no denominador;
2. teste de médias sempre reporta os dois recortes (todos e concluintes);
3. pareamento sem reposição, com caliper, e balanço verificado por diferença padronizada.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------- qui-quadrado
def qui_quadrado(tabela: pd.DataFrame, alpha: float = 0.05) -> dict:
    """tabela: linhas = grupos, colunas = desfechos (contagens).

    Post hoc: um 2x2 por desfecho (desfecho vs. resto), Bonferroni sobre o número de
    desfechos testados, e resíduos padronizados ajustados por célula
    (Garcia-Perez & Nunez-Anton, 2003).
    """
    obs = tabela.to_numpy(float)
    chi2, p, dof, esp = stats.chi2_contingency(obs, correction=False)
    n = obs.sum()
    r, c = obs.shape
    v = float(np.sqrt(chi2 / (n * (min(r, c) - 1))))
    lin, col = obs.sum(1, keepdims=True) / n, obs.sum(0, keepdims=True) / n
    residuos = (obs - esp) / np.sqrt(esp * (1 - lin) * (1 - col))
    alpha_adj = alpha / c
    posthoc = []
    for j, nome in enumerate(tabela.columns):
        sub = np.column_stack([obs[:, j], obs.sum(1) - obs[:, j]])
        x2, pj, _, _ = stats.chi2_contingency(sub, correction=False)
        posthoc.append({"desfecho": nome, "chi2": round(float(x2), 3), "p": float(pj),
                        "significativo": bool(pj < alpha_adj)})
    return {"chi2": round(float(chi2), 3), "gl": int(dof), "p": float(p), "v_cramer": round(v, 3),
            "alpha_bonferroni": alpha_adj, "posthoc": posthoc,
            "residuos_ajustados": pd.DataFrame(residuos, index=tabela.index, columns=tabela.columns).round(2).to_dict()}


# ---------------------------------------------------------------- médias
@dataclass
class Comparacao:
    n1: int
    n2: int
    media1: float
    media2: float
    diferenca: float
    t: float
    gl: float
    p: float
    hedges_g: float
    ic95_g: tuple[float, float]


def _hedges(m1, s1, n1, m2, s2, n2):
    sp = np.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / (n1 + n2 - 2))
    d = (m1 - m2) / sp
    j = 1 - 3 / (4 * (n1 + n2) - 9)
    g = d * j
    se = np.sqrt((n1 + n2) / (n1 * n2) + g ** 2 / (2 * (n1 + n2)))
    return g, (g - 1.96 * se, g + 1.96 * se)


def welch_resumo(m1: float, s1: float, n1: int, m2: float, s2: float, n2: int) -> Comparacao:
    """Welch a partir de estatísticas resumidas (útil para reanalisar artigos)."""
    t, p = stats.ttest_ind_from_stats(m1, s1, n1, m2, s2, n2, equal_var=False)
    v1, v2 = s1 ** 2 / n1, s2 ** 2 / n2
    gl = (v1 + v2) ** 2 / (v1 ** 2 / (n1 - 1) + v2 ** 2 / (n2 - 1))
    g, ic = _hedges(m1, s1, n1, m2, s2, n2)
    return Comparacao(n1, n2, m1, m2, m1 - m2, round(float(t), 3), round(float(gl), 2), float(p),
                      round(float(g), 3), (round(float(ic[0]), 3), round(float(ic[1]), 3)))


def welch(a: np.ndarray, b: np.ndarray) -> Comparacao:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return welch_resumo(a.mean(), a.std(ddof=1), len(a), b.mean(), b.std(ddof=1), len(b))


def comparar_medias(df: pd.DataFrame, grupo: str, nota: str, desistiu: str) -> dict:
    """Relata os dois recortes. Se divergem, a desistência diferencial está mexendo no resultado."""
    g1, g2 = sorted(df[grupo].unique())[::-1]
    out = {}
    for rotulo, d in [("concluintes", df[~df[desistiu].astype(bool)]), ("todos_com_nota", df.dropna(subset=[nota]))]:
        out[rotulo] = asdict(welch(d.loc[d[grupo] == g1, nota], d.loc[d[grupo] == g2, nota]))
    out["taxa_desistencia"] = df.groupby(grupo)[desistiu].mean().round(3).to_dict()
    return out


# ---------------------------------------------------------------- propensão
def _logit_fit(X: np.ndarray, y: np.ndarray, iters: int = 50) -> np.ndarray:
    X = np.column_stack([np.ones(len(X)), X])
    w = np.zeros(X.shape[1])
    for _ in range(iters):  # IRLS com leve regularização para estabilidade
        p = 1 / (1 + np.exp(-X @ w))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + 1e-6 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - p))
        w += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return X @ w  # logit do escore


def smd(x_t: np.ndarray, x_c: np.ndarray) -> float:
    s = np.sqrt((np.var(x_t, ddof=1) + np.var(x_c, ddof=1)) / 2)
    return float((x_t.mean() - x_c.mean()) / s) if s > 0 else 0.0


def pareamento_propensao(df: pd.DataFrame, tratado: str, covariaveis: list[str],
                         caliper_sd: float = 0.2, seed: int = 0) -> dict:
    """Vizinho mais próximo 1:1, SEM reposição, caliper de 0,2 DP do logit (Austin, 2011).

    Retorna os índices pareados, quantos tratados ficaram sem par e o balanço (SMD)
    antes e depois. |SMD| < 0,1 é o critério usual de balanço adequado.
    """
    X = pd.get_dummies(df[covariaveis], drop_first=True).astype(float).to_numpy()
    X = (X - X.mean(0)) / np.where(X.std(0) > 0, X.std(0), 1)
    y = df[tratado].astype(int).to_numpy()
    logit = _logit_fit(X, y)
    caliper = caliper_sd * logit.std()
    rng = np.random.default_rng(seed)
    trat = rng.permutation(np.where(y == 1)[0])
    livres = set(np.where(y == 0)[0].tolist())
    pares = []
    for i in trat:
        if not livres:
            break
        cand = np.fromiter(livres, int)
        dist = np.abs(logit[cand] - logit[i])
        j = int(np.argmin(dist))
        if dist[j] <= caliper:
            pares.append((int(df.index[i]), int(df.index[cand[j]])))
            livres.remove(int(cand[j]))
    t_idx = [a for a, _ in pares]
    c_idx = [b for _, b in pares]
    num = pd.get_dummies(df[covariaveis], drop_first=True).astype(float)
    balanco = {c: {"antes": round(smd(num.loc[df[tratado] == 1, c].to_numpy(), num.loc[df[tratado] == 0, c].to_numpy()), 3),
                   "depois": round(smd(num.loc[t_idx, c].to_numpy(), num.loc[c_idx, c].to_numpy()), 3) if pares else None}
               for c in num.columns}
    return {"pares": pares, "tratados": int(y.sum()), "pareados": len(pares),
            "sem_par": int(y.sum()) - len(pares), "caliper_logit": round(float(caliper), 4),
            "balanco_smd": balanco,
            "balanceado": all(v["depois"] is not None and abs(v["depois"]) < 0.1 for v in balanco.values())}
