"""MICRODADOS_ENEM -> contagens de acerto por (item, banda de nota).

Não materializa o formato longo: milhões de participantes x 45 itens não cabem em memória.
Agrega por chunk e soma.

Dois caminhos:
- bruto (CN, CH, MT): alinha a string de respostas com o layout do caderno.
- longo (qualquer área): recebe acerto já alinhado por outro pipeline, como o auditado
  dos confundidores. É o caminho recomendado para LC, cuja string mistura os idiomas.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import leitura as io
from .schema import BANDAS, RESP_ALIASES, banda_label

COLS = ["ano", "co_item", "banda", "banda_label", "acertos", "n"]


def _banda(notas: np.ndarray) -> np.ndarray:
    return np.digitize(notas, [lo for lo, _ in BANDAS[1:]])


def _acc(acc, co_item: int, b: int, hits: int, n: int):
    cur = acc.setdefault((co_item, b), np.zeros(2, dtype=np.int64))
    cur[0] += hits
    cur[1] += n


def aggregate_area(microdados: str | Path, area: str, layout: dict[int, pd.DataFrame], ano: int,
                   chunksize: int = 500_000, nrows: int | None = None) -> tuple[pd.DataFrame, dict]:
    if area == "LC":
        raise NotImplementedError("LC: use o caminho longo com o alinhamento multilíngue auditado.")
    cols = io.columns(microdados)
    names = {k: io.resolve(cols, v, area) for k, v in RESP_ALIASES.items()}
    missing = [k for k, v in names.items() if v is None]
    if missing:
        raise ValueError(f"{Path(microdados).name}: sem {missing} para {area}. Acrescente o alias em schema.RESP_ALIASES.")
    pres, prova, nota, resp = names["presenca"], names["prova"], names["nota"], names["respostas"]
    acc: dict = {}
    stats = {"linhas_presentes": 0, "descartadas_tamanho": 0, "cadernos_sem_layout": set()}
    reader = pd.read_csv(microdados, usecols=[pres, prova, nota, resp], chunksize=chunksize, nrows=nrows,
                         dtype={resp: "string"}, **io.sniff(microdados))
    for chunk in reader:
        chunk = chunk[(pd.to_numeric(chunk[pres], errors="coerce") == 1) & chunk[resp].notna() & chunk[nota].notna()]
        stats["linhas_presentes"] += len(chunk)
        for co_prova, grp in chunk.groupby(prova):
            lay = layout.get(int(co_prova))
            if lay is None:
                stats["cadernos_sem_layout"].add(int(co_prova))
                continue
            lay = lay[lay["SG_AREA"] == area]
            n_it = len(lay)
            strings = grp[resp].astype(str).str.strip()
            ok = strings.str.len() == n_it
            stats["descartadas_tamanho"] += int((~ok).sum())
            strings = strings[ok]
            if strings.empty:
                continue
            mat = np.frombuffer("".join(strings).encode("latin-1"), dtype="S1").reshape(-1, n_it)
            gab = np.array(lay["TX_GABARITO"].str.encode("latin-1"), dtype="S1")
            correct = (mat == gab).astype(np.int32)  # branco e dupla marcação contam como erro
            bandas = _banda(pd.to_numeric(grp.loc[strings.index, nota], errors="coerce").to_numpy(float))
            for b in np.unique(bandas):
                sel = correct[bandas == b]
                for j, co_item in enumerate(lay["CO_ITEM"].astype(int)):
                    _acc(acc, co_item, int(b), int(sel[:, j].sum()), sel.shape[0])
    stats["cadernos_sem_layout"] = sorted(stats["cadernos_sem_layout"])
    return _to_frame(acc, ano), stats


def aggregate_long(path: str | Path, ano: int, chunksize: int = 2_000_000) -> pd.DataFrame:
    """Entrada longa já alinhada: colunas co_item, correct (0/1), nota. CSV ou parquet."""
    path = Path(path)
    frames = [pd.read_parquet(path)] if path.suffix == ".parquet" else \
        pd.read_csv(path, usecols=["co_item", "correct", "nota"], chunksize=chunksize, **io.sniff(path))
    acc: dict = {}
    for df in frames:
        df = df.dropna(subset=["nota"]).assign(banda=lambda d: _banda(d["nota"].to_numpy(float)))
        g = df.groupby(["co_item", "banda"])["correct"].agg(["sum", "count"]).reset_index()
        for r in g.itertuples(index=False):
            _acc(acc, int(r.co_item), int(r.banda), int(r[2]), int(r[3]))
    return _to_frame(acc, ano)


def aggregate_longo_cfg(cfg, ano: int, area: str) -> pd.DataFrame:
    """Mesma agregação, lendo a célula pelo mapeamento do v9.2 (longo.ConfigLongo)."""
    from . import longo
    acc: dict = {}
    for df in longo.lotes(cfg, ano, area):
        df = df.assign(nota=pd.to_numeric(df["nota"], errors="coerce"), correct=pd.to_numeric(df["correct"], errors="coerce"),
                       co_item=pd.to_numeric(df["co_item"], errors="coerce")).dropna(subset=["nota", "correct", "co_item"])
        df = df.assign(banda=_banda(df["nota"].to_numpy(float)))
        g = df.groupby(["co_item", "banda"])["correct"].agg(["sum", "count"]).reset_index()
        for rec in g.itertuples(index=False):
            _acc(acc, int(rec.co_item), int(rec.banda), int(rec[2]), int(rec[3]))
    return _to_frame(acc, ano)


def _to_frame(acc: dict, ano: int) -> pd.DataFrame:
    recs = [(ano, k[0], k[1], banda_label(*BANDAS[k[1]]), int(v[0]), int(v[1])) for k, v in acc.items()]
    return pd.DataFrame(recs, columns=COLS)
