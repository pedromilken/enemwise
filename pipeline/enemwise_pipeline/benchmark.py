"""Linhas de base no dataset do ENEM, avaliadas prequencialmente nos estudantes de teste.

Teste de falsificação por permutação. Comparar BKT com e sem P(T) não basta: P(T) > 0
também funciona como regularização (impede P(L) de colar em 0 ou 1), e melhora o
log-loss mesmo sem aprendizagem nenhuma. Os dados sintéticos mostram isso.

Por isso o ganho é medido duas vezes: na ordem real do caderno e com a ordem embaralhada
dentro de cada participante. O ganho que sobrevive ao embaralhamento é regularização.
A diferença entre os dois ainda NÃO é aprendizagem: mistura efeito de posição, fadiga e a
ordenação das dificuldades no caderno (o BKT ignora a dificuldade do item). Os dados
sintéticos, sem aprendizagem e sem efeito de posição, já mostram diferença pela ordenação.

A identificação limpa usa o desenho do próprio ENEM: o mesmo item aparece em posições
diferentes nos cadernos de cores diferentes. Isso é o que o pipeline dos confundidores
explora com AFM, efeitos fixos de item e permutação; este benchmark é só a triagem.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import avaliacao, dataset

GRID = np.linspace(-4, 4, 81)


def _tri_prequencial(df: pd.DataFrame, D: float = 1.0) -> np.ndarray:
    """P(acerto) antes de cada resposta, com theta EAP atualizado ao longo da sequência."""
    df = df.sort_values(["uid", "ordem_exame"])
    uids, pos = np.unique(df["uid"].to_numpy(), return_inverse=True)
    passo = df.groupby("uid").cumcount().to_numpy()
    logpost = np.tile(-0.5 * GRID ** 2, (len(uids), 1))
    pred = np.empty(len(df))
    a, b, c, y = (df[k].to_numpy(float) for k in ("a", "b", "c", "correct"))
    ordem = np.argsort(passo, kind="stable")
    for t in np.unique(passo):
        sel = ordem[passo[ordem] == t]
        u = pos[sel]
        p = c[sel, None] + (1 - c[sel, None]) / (1 + np.exp(-D * a[sel, None] * (GRID[None, :] - b[sel, None])))
        w = np.exp(logpost[u] - logpost[u].max(1, keepdims=True))
        w /= w.sum(1, keepdims=True)
        pred[sel] = (w * p).sum(1)
        logpost[u] += np.where(y[sel, None] == 1, np.log(p), np.log(1 - p))
    return pd.Series(pred, index=df.index).reindex(df.index).to_numpy(), df


def _bkt_prequencial(df: pd.DataFrame, pl0: pd.Series, learn: float, slip: float = 0.1) -> np.ndarray:
    df = df.sort_values(["uid", "ordem_exame"])
    pred = np.empty(len(df))
    estado: dict[tuple, float] = {}
    for i, (uid, k, g, y) in enumerate(zip(df["uid"], df["chave"], df["c"].clip(0, 0.35), df["correct"])):
        pl = estado.get((uid, k), pl0.get(k, 0.3))
        pred[i] = pl * (1 - slip) + (1 - pl) * g
        num = pl * (1 - slip) if y else pl * slip
        den = num + ((1 - pl) * g if y else (1 - pl) * (1 - g))
        post = num / den if den > 0 else pl
        estado[(uid, k)] = post + (1 - post) * learn
    return pred, df


def _ganho_pt(teste: pd.DataFrame, pl0: pd.Series, y_col="correct") -> float:
    """Diferença de log-loss (com P(T) menos sem P(T)); negativo = P(T) ajudou."""
    b0, d0 = _bkt_prequencial(teste, pl0, learn=0.0)
    b1, _ = _bkt_prequencial(teste, pl0, learn=0.12)
    y = d0[y_col].to_numpy()
    return metr(y, b1)["log_loss"] - metr(y, b0)["log_loss"]


def rodar(out, ano: int, area: str, max_estudantes: int | None = 20_000, permutacoes: int = 5, seed: int = 0) -> dict:
    import pyarrow.dataset as ds
    df = dataset.carregar(out, [ano], [area])
    par = ds.dataset(out / "participantes", format="parquet", partitioning="hive").to_table(
        filter=ds.field("ano") == ano).to_pandas()[["uid", "teste"]]
    itens = pd.read_csv(out / "itens.csv").rename(columns={"CO_ITEM": "co_item", "NU_PARAM_A": "a", "NU_PARAM_B": "b",
                                                           "NU_PARAM_C": "c"})
    df = (df[df["anulado"] == 0].merge(par, on="uid").merge(itens[["ano", "co_item", "a", "b", "c"]], on=["ano", "co_item"])
            .dropna(subset=["a", "b", "c", "habilidade"]))
    df["chave"] = df["area"] + "-H" + df["habilidade"].astype(int).astype(str)
    treino, teste = df[~df["teste"]], df[df["teste"]]
    if max_estudantes:
        manter = teste["uid"].drop_duplicates().head(max_estudantes)
        teste = teste[teste["uid"].isin(manter)]
    y_sorted = teste.sort_values(["uid", "ordem_exame"])["correct"].to_numpy()

    prev = float(treino["correct"].mean())
    item_p = treino.groupby("co_item")["correct"].mean()
    # P(L0) de treino, descontando chute pelo c médio da habilidade
    g = treino.groupby("chave").agg(p=("correct", "mean"), c=("c", "mean"))
    pl0 = ((g["p"] - g["c"]) / (1 - 0.1 - g["c"]).clip(lower=0.05)).clip(0.01, 0.99)

    t_sorted = teste.sort_values(["uid", "ordem_exame"])
    tri, _ = _tri_prequencial(teste)
    bkt0, _ = _bkt_prequencial(teste, pl0, learn=0.0)
    bkt1, _ = _bkt_prequencial(teste, pl0, learn=0.12)
    res = {
        "ano": ano, "area": area, "estudantes_teste": int(t_sorted["uid"].nunique()), "interacoes_teste": int(len(t_sorted)),
        "prevalencia_treino": metr(y_sorted, np.full(len(y_sorted), prev)),
        "dificuldade_do_item_treino": metr(y_sorted, t_sorted["co_item"].map(item_p).fillna(prev).to_numpy()),
        "tri_3pl_inep_prequencial": metr(y_sorted, tri),
        "bkt_sem_aprendizagem": metr(y_sorted, bkt0),
        "bkt_com_aprendizagem": metr(y_sorted, bkt1),
    }
    rng = np.random.default_rng(seed)
    ganho_real = res["bkt_com_aprendizagem"]["log_loss"] - res["bkt_sem_aprendizagem"]["log_loss"]
    ganhos_perm = []
    for _ in range(permutacoes):
        emb = teste.copy()
        emb["ordem_exame"] = emb.groupby("uid")["ordem_exame"].transform(lambda s: rng.permutation(s.to_numpy()))
        ganhos_perm.append(_ganho_pt(emb, pl0))
    res["falsificacao"] = {
        "ganho_logloss_pt_ordem_real": round(float(ganho_real), 4),
        "ganho_logloss_pt_ordem_embaralhada_media": round(float(np.mean(ganhos_perm)), 4) if ganhos_perm else None,
        "diferenca_ordem_real_menos_embaralhada": round(float(ganho_real - np.mean(ganhos_perm)), 4) if ganhos_perm else None,
        "p_permutacao": round((1 + sum(g <= ganho_real for g in ganhos_perm)) / (1 + len(ganhos_perm)), 3) if ganhos_perm else None,
        "leitura": ("Ganho que sobrevive ao embaralhamento é regularização, não aprendizagem. A diferença entre ordem real "
                    "e embaralhada mistura posição, fadiga e ordenação de dificuldade no caderno; num exame sem ensino, "
                    "nenhuma parte dela é aprendizagem. Para identificar efeito de posição, compare cadernos de cores "
                    "diferentes com efeitos fixos de item. Com poucas permutações o p tem piso alto; use --permutacoes 500."),
    }
    return res


def metr(y, p):
    m = avaliacao.metricas(np.asarray(y, int), np.asarray(p, float))
    return {k: m[k] for k in ("n", "auc", "acuracia", "brier", "log_loss", "ece", "f1_macro")} | {"classe_erro": m["classe_erro"]}
