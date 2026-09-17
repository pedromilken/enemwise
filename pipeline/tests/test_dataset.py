import json

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")

from enemwise_pipeline import benchmark, dataset, datasheet, synth  # noqa: E402


@pytest.fixture(scope="module")
def ds(tmp_path_factory):
    root = tmp_path_factory.mktemp("w")
    world = synth.generate(root, n=3000, seed=11)
    out = root / "dataset"
    for ano in (2097, 2099):  # 2097: ordem antiga dos dias, colunas antigas, separador vírgula
        dataset.exportar_edicao(ano, world[ano]["itens"], world[ano]["microdados"], out, fracao=0.5, seed=1, chunksize=700)
    dataset.dicionarios(out)
    return world, out


def test_amostra_deterministica_independe_do_chunk(ds, tmp_path):
    world, out = ds
    outro = tmp_path / "d2"
    dataset.exportar_edicao(2099, world[2099]["itens"], world[2099]["microdados"], outro, fracao=0.5, seed=1, chunksize=2000)
    a = set(dataset.carregar(out, [2099])["uid"].unique())
    b = set(dataset.carregar(outro, [2099])["uid"].unique())
    assert a == b and 0.4 < len(a) / 3000 < 0.6


def test_estrutura_ordem_e_auditoria_do_gabarito(ds):
    _, out = ds
    df = dataset.carregar(out, [2097])
    por_uid = df.groupby(["uid", "area"]).size()
    assert (por_uid == 45).all()
    # 2097 usa a ordem antiga: CH e CN no dia 1, MT no dia 2
    assert set(df.loc[df["area"] == "CH", "dia"]) == {1} and set(df.loc[df["area"] == "MT", "dia"]) == {2}
    rel = json.loads((out / "relatorios" / "2099.json").read_text(encoding="utf-8"))
    assert all(s["taxa_gabarito_confere"] == 1.0 for s in rel["areas"].values())
    assert df["anulado"].sum() > 0  # anulado permanece marcado


def test_folds_por_participante(ds):
    _, out = ds
    import pyarrow.dataset as pads
    par = pads.dataset(out / "participantes", format="parquet", partitioning="hive").to_table().to_pandas()
    assert par["uid"].is_unique
    assert 0.15 < par["teste"].mean() < 0.25 and set(par["fold"]) == {0, 1, 2, 3, 4}


def test_formato_pykt(ds):
    _, out = ds
    rel = dataset.exportar_pykt(out, "enem_mt", anos=[2099], areas=["MT"])
    linhas = (out / "pykt" / "enem_mt" / "data.txt").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 6 * rel["estudantes"]
    uid, n = linhas[0].split(",")
    q, c, r = (linhas[i].split(",") for i in (1, 2, 3))
    assert int(n) == len(q) == len(c) == len(r) == 44  # 45 menos o anulado
    assert set(r) <= {"0", "1"} and linhas[4] == "NA" and "NA" not in linhas[1] + linhas[2]


def test_benchmark_e_falsificacao(ds):
    _, out = ds
    res = benchmark.rodar(out, 2099, "MT")
    assert res["tri_3pl_inep_prequencial"]["auc"] > res["prevalencia_treino"]["auc"]
    f = res["falsificacao"]
    # P(T) > 0 "ajuda" por regularização mesmo sem aprendizagem nenhuma...
    assert f["ganho_logloss_pt_ordem_real"] < 0
    # ...e continua ajudando com a ordem embaralhada: é regularização, não aprendizagem
    assert f["ganho_logloss_pt_ordem_embaralhada_media"] < 0


def test_datasheet(ds):
    _, out = ds
    texto = datasheet.gerar(out).read_text(encoding="utf-8")
    assert "ordem é posição no caderno, não tempo" in texto and (out / "SHA256SUMS").exists()
