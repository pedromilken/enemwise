"""Adaptador para a exportação longa do pipeline v9.2 (estudo dos confundidores).

A ideia é usar o alinhamento já auditado (68 células, 4 áreas x 17 edições, com as
correções de LC multilíngue e de itens anulados) como ÚNICA fonte de acertos, tanto
para o dataset de KT quanto para os priors do app. Nada é realinhado aqui.

O esquema do v9.2 é descrito num JSON de mapeamento, gerado por `longo-inspecionar`:

{
  "caminho": "/dados/v92/long/ano={ano}/area={area}/*.parquet",
  "colunas": {"uid": "NU_INSCRICAO", "co_item": "CO_ITEM", "correct": "ACERTO",
              "nota": "NU_NOTA", "co_prova": "CO_PROVA", "posicao": null, "resposta": "RESPOSTA"}
}

Obrigatórias: uid, co_item, correct, nota. Para reconstruir a ordem do caderno é
preciso co_prova OU posicao: os cadernos de cores diferentes embaralham os itens.
"""
from __future__ import annotations

import glob
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

OBRIGATORIAS = ("uid", "co_item", "correct", "nota")
OPCIONAIS = ("co_prova", "posicao", "resposta")
CANDIDATOS = {
    "uid": ["uid", "nu_inscricao", "id_participante", "participante", "student_id", "user_id", "id"],
    "co_item": ["co_item", "item", "item_id", "question_id"],
    "correct": ["correct", "acerto", "acertou", "correta", "is_correct", "resposta_correta", "y"],
    "nota": ["nota", "nu_nota", "proficiencia", "theta_inep", "score"],
    "co_prova": ["co_prova", "caderno", "prova", "booklet"],
    "posicao": ["posicao", "co_posicao", "position", "ordem", "pos"],
    "resposta": ["resposta", "tx_resposta", "answer", "letra", "marcada"],
}


@dataclass
class ConfigLongo:
    caminho: str
    colunas: dict[str, str | None]
    formato: str = "auto"
    extras: dict = field(default_factory=dict)

    @classmethod
    def ler(cls, path: str | Path) -> "ConfigLongo":
        from .leitura import ler_texto
        d = json.loads(ler_texto(path))
        cfg = cls(caminho=d["caminho"], colunas=d["colunas"], formato=d.get("formato", "auto"), extras=d.get("extras", {}))
        faltam = [k for k in OBRIGATORIAS if not cfg.colunas.get(k)]
        if faltam:
            raise ValueError(f"Mapeamento sem colunas obrigatórias: {faltam}")
        if not (cfg.colunas.get("co_prova") or cfg.colunas.get("posicao")):
            raise ValueError("Informe co_prova ou posicao: sem isso não dá para reconstruir a ordem do caderno.")
        return cfg

    def arquivos(self, ano: int, area: str) -> list[str]:
        padrao = self.caminho.replace("\\", "/").format(ano=ano, area=area, AREA=area.upper(), area_min=area.lower())
        return sorted(glob.glob(padrao, recursive=True))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _esquema(arquivo: str) -> tuple[list[str], pd.DataFrame]:
    if arquivo.endswith(".parquet"):
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(arquivo)
        amostra = next(pf.iter_batches(batch_size=200)).to_pandas()
        return list(pf.schema_arrow.names), amostra
    amostra = pd.read_csv(arquivo, nrows=200, sep=None, engine="python")
    return list(amostra.columns), amostra


def inspecionar(arquivo: str) -> dict:
    """Lê o esquema e sugere o mapeamento. Confere também se 'correct' parece binária."""
    cols, amostra = _esquema(arquivo)
    sugestao: dict[str, str | None] = {}
    for campo, cands in CANDIDATOS.items():
        achou = next((c for cand in cands for c in cols if _norm(c) == _norm(cand)), None)
        sugestao[campo] = achou
    avisos = []
    if sugestao["correct"] and not set(pd.unique(amostra[sugestao["correct"]].dropna())) <= {0, 1, True, False}:
        avisos.append(f"coluna {sugestao['correct']} não parece binária")
    for k in OBRIGATORIAS:
        if not sugestao[k]:
            avisos.append(f"não encontrei '{k}': preencha à mão")
    if not (sugestao["co_prova"] or sugestao["posicao"]):
        avisos.append("sem co_prova nem posicao: a ordem do caderno não poderá ser reconstruída")
    return {"arquivo": arquivo, "colunas": cols, "tipos": {c: str(t) for c, t in amostra.dtypes.items()},
            "sugestao": {"caminho": "AJUSTE: ex. /dados/v92/long/ano={ano}/area={area}/*.parquet", "colunas": sugestao},
            "avisos": avisos, "amostra": amostra.head(3).to_dict(orient="records")}


def lotes(cfg: ConfigLongo, ano: int, area: str, tamanho: int = 1_000_000) -> Iterator[pd.DataFrame]:
    """Lê uma célula (ano, área) em lotes, só com as colunas mapeadas, já renomeadas."""
    arqs = cfg.arquivos(ano, area)
    if not arqs:
        raise FileNotFoundError(f"Sem arquivos para {ano}-{area} em {cfg.caminho}")
    mapa = {v: k for k, v in cfg.colunas.items() if v}
    for arq in arqs:
        if arq.endswith(".parquet"):
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(arq)
            usar = [c for c in mapa if c in pf.schema_arrow.names]
            for b in pf.iter_batches(batch_size=tamanho, columns=usar):
                yield b.to_pandas().rename(columns=mapa)
        else:
            head = pd.read_csv(arq, nrows=0, sep=None, engine="python")
            usar = [c for c in mapa if c in head.columns]
            for df in pd.read_csv(arq, usecols=usar, chunksize=tamanho, sep=None, engine="python"):
                yield df.rename(columns=mapa)


def uid_int(uid: pd.Series, ano: int) -> np.ndarray:
    """uid do v9.2 (número ou texto) -> int64 estável. Numérico vira ano*1e8 + id quando cabe."""
    num = pd.to_numeric(uid, errors="coerce")
    if num.notna().all() and (num >= 0).all() and (num < 1e8).all():
        return (np.int64(ano) * 100_000_000 + num.astype(np.int64)).to_numpy()
    h = pd.util.hash_pandas_object(uid.astype(str) + f"|{ano}", index=False).to_numpy(np.uint64)
    return (h >> np.uint64(1)).astype(np.int64)  # 63 bits, colisão desprezível na escala do ENEM


def ler_grade(path: str | Path) -> pd.DataFrame:
    """Grade certificada do artigo: colunas ano, area e ao menos uma de n_participantes / n_interacoes."""
    g = pd.read_csv(path)
    g.columns = [c.strip().lower() for c in g.columns]
    return g.rename(columns={"year": "ano"})  # grid_metrics.csv da v9.2 usa year/area/students
