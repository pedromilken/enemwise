import argparse
import json

import numpy as np
import pandas as pd
import pytest

from enemwise_pipeline import cli, items as itm, leitura, link_text, merge, synth
from enemwise_pipeline.edicao import build_edition


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp("synth")
    return synth.generate(root, n=4000, seed=3)


@pytest.fixture(scope="module")
def pacote(world, tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    web = tmp_path_factory.mktemp("web")
    status = cli.batch(argparse.Namespace(raiz=world["raiz"], anos="2097-2099", questoes=[str(p) for p in world["questoes"]],
                                          long_dir=None, lingua=0, nrows=None, jobs=1, out=out))
    meta = merge.merge(out, web, sintetico=True)
    return status, meta, web


def test_descobre_arquivos_sem_diferenciar_maiusculas(world):
    assert leitura.find_file(world["raiz"], "microdados_enem", 2098) is not None


def test_colunas_antigas_e_separador_virgula(world):
    assert leitura.sniff(world[2097]["microdados"])["sep"] == ","
    cols = leitura.columns(world[2097]["microdados"])
    assert "IN_PRESENCA_CN" in cols and "NU_NT_MT" in cols


def test_anulado_fica_no_layout_mas_sai_do_banco(world):
    booklets = itm.filter_booklets(itm.load_itens(world[2099]["itens"]))
    mt = [lay for lay in itm.booklet_layout(booklets).values() if lay["SG_AREA"].iloc[0] == "MT"][0]
    assert len(mt) == 45
    assert len(itm.canonical_items(itm.usable_items(booklets), 2099).query("area == 'MT'")) == 44


def test_vinculo_ordem_antiga_e_fonte_parcial(world):
    layout = itm.booklet_layout(itm.filter_booklets(itm.load_itens(world[2097]["itens"])))
    q = link_text.load_questions(world["questoes"][0])
    assert set(q["ano"]) == {2097} and len(q) < 180  # cobertura parcial
    links, report = link_text.fingerprint_link(q, layout)
    assert all(r["aceito"] for r in report)
    assert len(links) == len(q)


def test_gabarito_embaralhado_e_rejeitado(world):
    layout = itm.booklet_layout(itm.filter_booklets(itm.load_itens(world[2099]["itens"])))
    q = link_text.load_questions(world["questoes"][1])
    q["gabarito"] = np.random.default_rng(0).permutation(q["gabarito"].to_numpy())
    _, report = link_text.fingerprint_link(q, layout)
    assert not any(r["aceito"] for r in report)


def test_auditoria_pega_desalinhamento(world, tmp_path):
    itens = pd.read_csv(world[2098]["itens"], sep=";", encoding="latin-1")
    rng = np.random.default_rng(1)
    itens["TX_GABARITO"] = rng.choice(list("ABCDE"), len(itens))  # gabarito de "outra cor"
    bad = tmp_path / "ITENS_PROVA_2098.csv"
    itens.to_csv(bad, sep=";", index=False, encoding="latin-1")
    rel = build_edition(2098, bad, world[2098]["microdados"], tmp_path / "o")
    assert all(a["ok"] is False for a in rel["auditoria"] if a["area"] != "LC")


def test_batch_processa_todas_e_merge_agrega(pacote):
    status, meta, web = pacote
    assert all(s.get("ok") for s in status.values())
    assert meta["edicoes"] == [2097, 2098, 2099]
    assert meta["edicoes_com_texto"] == [2097, 2099]  # 2098 sem fonte de texto: só priors
    assert meta["auditoria_reprovada"] == []
    assert meta["diagnostico_monotonia"] > 0.9


def test_merge_exclui_celula_reprovada(world, tmp_path):
    itens = pd.read_csv(world[2098]["itens"], sep=";", encoding="latin-1")
    itens["TX_GABARITO"] = np.random.default_rng(1).choice(list("ABCDE"), len(itens))
    raiz = tmp_path / "inep"
    raiz.mkdir()
    itens.to_csv(raiz / "ITENS_PROVA_2098.csv", sep=";", index=False, encoding="latin-1")
    build_edition(2098, raiz / "ITENS_PROVA_2098.csv", world[2098]["microdados"], tmp_path / "out" / "2098")
    build_edition(2099, world[2099]["itens"], world[2099]["microdados"], tmp_path / "out" / "2099")
    meta = merge.merge(tmp_path / "out", tmp_path / "web")
    pr = pd.DataFrame(json.loads((tmp_path / "web" / "priors.json").read_text(encoding="utf-8")))
    assert "2098-MT" in meta["auditoria_reprovada"]
    assert pr["n_edicoes"].max() == 1  # só 2099 sobrou nos priors


def test_priors_agregados_e_estabilidade(pacote):
    _, _, web = pacote
    pr = pd.DataFrame(json.loads((web / "priors.json").read_text(encoding="utf-8")))
    assert pr["n_edicoes"].max() == 3
    assert pr["p_l0"].between(0.01, 0.99).all()
    assert np.all(np.diff(pr.groupby("banda")["p_l0"].mean().to_numpy()) > 0)


def test_shards_por_edicao_legiveis_pelo_app(pacote):
    _, _, web = pacote
    it = json.loads((web / "items" / "2099.json").read_text(encoding="utf-8"))
    mt = next(i for i in it if i["area"] == "MT")
    assert {"id", "ano", "habilidade", "a", "b", "c", "gabarito", "enunciado", "alternativas"} <= mt.keys()
    assert len(mt["p_banda"]) == 5


def test_caminho_longo_para_lc(world, tmp_path):
    canon = itm.canonical_items(itm.usable_items(itm.filter_booklets(itm.load_itens(world[2099]["itens"]))), 2099)
    lc = canon[canon["area"] == "LC"]
    rng = np.random.default_rng(5)
    theta = rng.normal(0, 1, 3000)
    rows = []
    for r in lc.itertuples():
        p = synth.p3pl(theta, r.a, r.b, r.c)
        rows.append(pd.DataFrame({"co_item": r.co_item, "correct": (rng.random(3000) < p).astype(int),
                                  "nota": 500 + 100 * theta}))
    longdir = tmp_path / "long"
    longdir.mkdir()
    pd.concat(rows).to_csv(longdir / "2099_LC.csv", index=False)
    rel = build_edition(2099, world[2099]["itens"], world[2099]["microdados"], tmp_path / "o",
                        longos=cli._longos(longdir, 2099))
    lc_aud = next(a for a in rel["auditoria"] if a["area"] == "LC")
    assert lc_aud["ok"] is True and lc_aud["itens_com_respostas"] == 45


def test_celula_certificada_nao_sai_dos_priors(world, tmp_path):
    """Célula v9.2 com alerta de auditoria continua nos priors; o merge recalcula a auditoria."""
    from enemwise_pipeline import audit
    assert audit.aprovado({"rho_p_esperado": 0.9, "rho_p_b": -0.1}) is True   # piso do chute: b fraco, esperado forte
    assert audit.aprovado({"rho_p_esperado": 0.2, "rho_p_b": -0.9}) is False
    build_edition(2099, world[2099]["itens"], world[2099]["microdados"], tmp_path / "out" / "2099",
                  questoes=[link_text.load_questions(world["questoes"][1])])
    pasta = tmp_path / "out" / "2099"
    rel = json.loads((pasta / "relatorio.json").read_text(encoding="utf-8"))
    rel["respostas"] = {k: {"fonte": "v9.2"} for k in ("CN", "CH", "LC", "MT")}
    (pasta / "relatorio.json").write_text(json.dumps(rel), encoding="utf-8")
    itens = pd.read_json(pasta / "items_full.json", orient="records")
    mt = itens["area"] == "MT"
    itens.loc[mt, "b"] = np.random.default_rng(0).permutation(itens.loc[mt, "b"].to_numpy())  # parâmetros trocados
    itens.loc[mt, "a"] = np.random.default_rng(1).permutation(itens.loc[mt, "a"].to_numpy())
    (pasta / "items_full.json").write_text(itens.to_json(orient="records", force_ascii=False), encoding="utf-8")
    meta = merge.merge(tmp_path / "out", tmp_path / "web")
    assert meta["auditoria_reprovada"] == [] and meta["auditoria_alertas_certificadas"] == ["2099-MT"]
    pr = pd.DataFrame(json.loads((tmp_path / "web" / "priors.json").read_text(encoding="utf-8")))
    assert "MT" in set(pr["area"])
    # parâmetros trocados são reestimados pelas respostas e voltam a acompanhar o acerto observado
    reaj = meta["parametros_reajustados"][0]
    assert reaj["rho_p_esperado"] < 0.6 and reaj["rho_p_esperado_reajustado"] > 0.9 and reaj["itens_reajustados"] >= 40
    shard = json.loads((tmp_path / "web" / "items" / "2099.json").read_text(encoding="utf-8"))
    mt = [i for i in shard if i["area"] == "MT"]
    assert all("b_inep" in i and i["parametros"].startswith("reajustados") for i in mt)


def test_piso_do_chute_nao_reprova():
    """Prova difícil e bem alinhada: correlação com b fraca, com o esperado forte."""
    from enemwise_pipeline import audit
    rng = np.random.default_rng(0)
    k, n = 45, 20000
    a, b, c = rng.lognormal(np.log(2.5), 0.35, k), rng.normal(2.5, 0.8, k), rng.uniform(0.08, 0.30, k)
    th = rng.normal(0, 1, n)
    banda = np.digitize(500 + 100 * th, [450, 550, 650, 750])
    y = rng.random((n, k)) < c + (1 - c) / (1 + np.exp(-1.7 * a * (th[:, None] - b)))
    counts = pd.DataFrame([{"co_item": j, "banda": bb, "acertos": int(y[banda == bb, j].sum()), "n": int((banda == bb).sum())}
                           for j in range(k) for bb in range(5) if (banda == bb).any()])
    itens = pd.DataFrame({"co_item": range(k), "a": a, "b": b, "c": c})
    m = audit.metricas_celula(counts, itens, D=1.7)
    assert m["rho_p_b"] > -0.6 and m["rho_p_esperado"] > 0.9 and audit.aprovado(m)


def test_itens_sem_habilidade_ficam_como_h0(world, tmp_path):
    itens = pd.read_csv(world[2099]["itens"], sep=";", encoding="latin-1")
    itens.loc[itens["SG_AREA"] == "CN", "CO_HABILIDADE"] = np.nan
    f = tmp_path / "ITENS_PROVA_2099.csv"
    itens.to_csv(f, sep=";", index=False, encoding="latin-1")
    q = link_text.load_questions(world["questoes"][1])
    rel = build_edition(2099, f, world[2099]["microdados"], tmp_path / "o", questoes=[q])
    full = pd.read_json(tmp_path / "o" / "items_full.json", orient="records")
    cn = full[full["area"] == "CN"]
    assert len(cn) == 45 and set(cn["habilidade"]) == {0} and cn["enunciado"].notna().all()
    assert rel["itens_com_texto"] == 179
