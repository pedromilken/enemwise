"""Exportação longa no estilo v9.2 (nomes de colunas diferentes, LC incluída, participantes
espalhados entre arquivos) alimentando dataset, priors e conciliação com a grade."""
import json

import numpy as np
import pandas as pd
import pytest

pa = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq  # noqa: E402

from enemwise_pipeline import benchmark, dataset, items as itm, longo, synth  # noqa: E402
from enemwise_pipeline.edicao import build_edition  # noqa: E402

N = 1200


def _exportacao_v92(world, raiz, ano, rng):
    booklets = itm.filter_booklets(itm.load_itens(world[ano]["itens"]), lingua=0)
    layout = itm.booklet_layout(booklets)
    params = booklets.drop_duplicates("CO_ITEM").set_index("CO_ITEM")
    theta = rng.normal(0, 1, N)
    grade = []
    for area in ("CN", "CH", "LC", "MT"):
        provas = [k for k, v in layout.items() if v["SG_AREA"].iloc[0] == area]
        escolha = rng.integers(0, len(provas), N)
        rows = []
        for i in range(N):
            lay = layout[provas[escolha[i]]]
            a, b, c = (params.loc[lay["CO_ITEM"], k].to_numpy() for k in ("NU_PARAM_A", "NU_PARAM_B", "NU_PARAM_C"))
            p = synth.p3pl(theta[i], a, b, c)
            y = (rng.random(len(p)) < p).astype(int)
            rows.append(pd.DataFrame({"NU_INSCRICAO": i + 1, "CO_PROVA": provas[escolha[i]], "CO_ITEM": lay["CO_ITEM"],
                                      "ACERTO": y, "TX_RESPOSTA": np.where(y == 1, lay["TX_GABARITO"], "Z"),
                                      "NU_NOTA": round(500 + 100 * theta[i], 1)}))
        df = pd.concat(rows).sample(frac=1, random_state=1)  # participante espalhado entre arquivos
        pasta = raiz / f"ano={ano}" / f"area={area}"
        pasta.mkdir(parents=True)
        metade = len(df) // 2
        pq.write_table(pa.Table.from_pandas(df.iloc[:metade], preserve_index=False), pasta / "p0.parquet")
        pq.write_table(pa.Table.from_pandas(df.iloc[metade:], preserve_index=False), pasta / "p1.parquet")
        grade.append({"ano": ano, "area": area, "n_participantes": N})
    return grade


@pytest.fixture(scope="module")
def v92(tmp_path_factory):
    root = tmp_path_factory.mktemp("v92")
    world = synth.generate(root / "w", n=50, seed=5)
    rng = np.random.default_rng(3)
    grade = []
    for ano in (2097, 2099):
        grade += _exportacao_v92(world, root / "long", ano, rng)
    pd.DataFrame(grade).to_csv(root / "grade.csv", index=False)
    cfgp = root / "v92.json"
    cfgp.write_text(json.dumps({"caminho": str(root / "long" / "ano={ano}" / "area={area}" / "*.parquet"),
                                "colunas": {"uid": "NU_INSCRICAO", "co_item": "CO_ITEM", "correct": "ACERTO",
                                            "nota": "NU_NOTA", "co_prova": "CO_PROVA", "posicao": None, "resposta": "TX_RESPOSTA"}}), encoding="utf-8")
    return world, root, longo.ConfigLongo.ler(cfgp)


def test_inspecionar_sugere_mapeamento(v92):
    _, root, _ = v92
    arq = next((root / "long").rglob("*.parquet"))
    sug = longo.inspecionar(str(arq))["sugestao"]["colunas"]
    assert sug == {"uid": "NU_INSCRICAO", "co_item": "CO_ITEM", "correct": "ACERTO", "nota": "NU_NOTA",
                   "co_prova": "CO_PROVA", "posicao": None, "resposta": "TX_RESPOSTA"}


def test_config_exige_ordem(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"caminho": "x", "colunas": {"uid": "a", "co_item": "b", "correct": "c", "nota": "d"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="co_prova ou posicao"):
        longo.ConfigLongo.ler(f)


def test_dataset_quatro_areas_independe_do_lote(v92, tmp_path):
    world, root, cfg = v92
    a = tmp_path / "a"
    b = tmp_path / "b"
    for ano in (2097, 2099):
        dataset.exportar_de_longo(cfg, ano, world[ano]["itens"], a, fracao=0.5, seed=2)
        dataset.exportar_de_longo(cfg, ano, world[ano]["itens"], b, fracao=0.5, seed=2, tamanho_lote=997)
    da, db = (dataset.carregar(x).sort_values(["uid", "ordem_exame"]).reset_index(drop=True) for x in (a, b))
    pd.testing.assert_frame_equal(da, db)
    assert set(da["area"]) == {"CN", "CH", "LC", "MT"}
    por = da.groupby(["ano", "uid", "area"]).size()
    assert (por == 45).all()
    assert (da.groupby(["ano", "uid"])["ordem_exame"].nunique() == da.groupby(["ano", "uid"]).size()).all()
    d97 = da[da["ano"] == 2097]
    assert set(d97.loc[d97["area"] == "LC", "dia"]) == {dataset.dia_da_area(2097, "LC")[0]}
    # regra real do ENEM: até 2016, LC no 2º dia; a partir de 2017, LC no 1º dia
    assert dataset.dia_da_area(2016, "LC") == (2, 0) and dataset.dia_da_area(2017, "LC") == (1, 0)
    rel = json.loads((a / "relatorios" / "2099.json").read_text(encoding="utf-8"))
    assert all(s["participantes_lidos"] == N and s["itens_fora_do_itens_prova"] == 0 for s in rel["areas"].values())


def test_conciliacao_com_a_grade(v92, tmp_path):
    world, root, cfg = v92
    out = tmp_path / "d"
    for ano in (2097, 2099):
        dataset.exportar_de_longo(cfg, ano, world[ano]["itens"], out, fracao=0.1)
    assert dataset.conciliar_grade(out, root / "grade.csv")["conferem"] == 8
    errada = pd.read_csv(root / "grade.csv")
    errada.loc[0, "n_participantes"] += 50  # acima da tolerância de 0,1%
    errada.to_csv(tmp_path / "g.csv", index=False)
    assert len(dataset.conciliar_grade(out, tmp_path / "g.csv")["divergentes"]) == 1


def test_lacuna_interrompe_por_padrao(v92, tmp_path):
    world, root, cfg = v92
    with pytest.raises(FileNotFoundError):
        dataset.exportar_de_longo(cfg, 2098, world[2098]["itens"], tmp_path / "x")
    rel = dataset.exportar_de_longo(cfg, 2098, world[2098]["itens"], tmp_path / "y", permitir_lacunas=True)
    assert len(rel["lacunas"]) == 4


def test_pykt_e_benchmark_incluem_lc(v92, tmp_path):
    world, root, cfg = v92
    out = tmp_path / "d"
    dataset.exportar_de_longo(cfg, 2099, world[2099]["itens"], out, fracao=1.0)
    dataset.dicionarios(out)
    rel = dataset.exportar_pykt(out, "enem_2099_todas", anos=[2099])
    assert rel["exportadas"] == N * (45 * 4 - 1)  # um item anulado em MT
    res = benchmark.rodar(out, 2099, "LC", permutacoes=2)
    assert res["tri_3pl_inep_prequencial"]["auc"] > 0.6


def test_priors_do_app_da_mesma_fonte(v92, tmp_path):
    world, root, cfg = v92
    rel = build_edition(2099, world[2099]["itens"], None, tmp_path / "e", longo_cfg=cfg)
    lc = next(a for a in rel["auditoria"] if a["area"] == "LC")
    assert lc["ok"] is True and all(s == {"fonte": "v9.2"} for s in rel["respostas"].values())


def test_config_gravada_pelo_powershell(tmp_path):
    """PowerShell 5.1: '>' grava UTF-16 LE com BOM; Out-File -Encoding utf8 grava UTF-8 com BOM."""
    conteudo = json.dumps({"caminho": "D:\\v92\\long\\ano={ano}\\area={area}\\*.parquet",
                           "colunas": {"uid": "NU_INSCRICAO", "co_item": "CO_ITEM", "correct": "ACERTO",
                                       "nota": "NU_NOTA", "co_prova": "CO_PROVA"}}, ensure_ascii=False)
    for nome, dados in [("utf16.json", b"\xff\xfe" + conteudo.encode("utf-16-le")),
                        ("utf8bom.json", b"\xef\xbb\xbf" + conteudo.encode("utf-8"))]:
        (tmp_path / nome).write_bytes(dados)
        cfg = longo.ConfigLongo.ler(tmp_path / nome)
        assert cfg.colunas["uid"] == "NU_INSCRICAO"
    assert "\\" not in cfg.caminho.replace("\\", "/").format(ano=2019, area="LC")


def test_inspecionar_com_saida(v92, tmp_path):
    import subprocess
    import sys
    _, root, _ = v92
    arq = next((root / "long").rglob("*.parquet"))
    r = subprocess.run([sys.executable, "-m", "enemwise_pipeline.cli", "longo-inspecionar", "--arquivo", str(arq),
                        "--saida", str(tmp_path / "v92.json")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert json.loads((tmp_path / "v92.json").read_text(encoding="utf-8"))["colunas"]["correct"] == "ACERTO"
    r2 = subprocess.run([sys.executable, "-m", "enemwise_pipeline.cli", "longo-inspecionar", "--arquivo", "/dados/nao/existe.parquet"],
                        capture_output=True, text=True, encoding="utf-8")
    assert r2.returncode != 0 and "Get-ChildItem" in r2.stderr



def _exportacao_formato_v92_real(world, raiz, ano, rng, n=800):
    """Mesmas colunas do export_enemwise.py da v9.2, com metade de LC em espanhol."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    raw = itm.load_itens(world[ano]["itens"])
    params = raw.drop_duplicates("CO_ITEM").set_index("CO_ITEM")
    theta = rng.normal(0, 1, n)
    for area in ("CN", "CH", "LC", "MT"):
        partes = []
        for lingua in (0, 1):
            lay_all = itm.booklet_layout(itm.filter_booklets(raw, lingua=lingua))
            provas = [k for k, v in lay_all.items() if v["SG_AREA"].iloc[0] == area]
            for i in range(n):
                if area == "LC" and i % 2 != lingua:
                    continue
                if area != "LC" and lingua == 1:
                    continue
                prova = provas[i % len(provas)]
                lay = lay_all[prova]
                a, b, c = (params.loc[lay["CO_ITEM"], k].to_numpy() for k in ("NU_PARAM_A", "NU_PARAM_B", "NU_PARAM_C"))
                y = (rng.random(len(lay)) < synth.p3pl(theta[i], a, b, c)).astype("int8")
                partes.append(pd.DataFrame({"student": i, "prova": prova, "score": 500 + 100 * theta[i],
                                            "item": lay["CO_ITEM"].to_numpy(), "skill": 1,
                                            "position": np.arange(1, len(lay) + 1), "a": a, "b": b, "c": c,
                                            "correct": y, "participante": f"{ano}{i:08d}"}))
        df = pd.concat(partes)
        pasta = raiz / f"ano={ano}" / f"area={area}"
        pasta.mkdir(parents=True)
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), pasta / "part-0000.parquet")
        (pasta / "_manifesto.json").write_text(json.dumps({"frac": 1.0, "blank_policy": "wrong",
                                                           "n_populacao_alinhada": int(df["participante"].nunique())}),
                                               encoding="utf-8")


def test_formato_real_da_v92_com_espanhol_e_grade(tmp_path):
    world = synth.generate(tmp_path / "w", n=20, seed=8)
    _exportacao_formato_v92_real(world, tmp_path / "exp", 2099, np.random.default_rng(1))
    arq = next((tmp_path / "exp").rglob("*.parquet"))
    sug = longo.inspecionar(str(arq))["sugestao"]["colunas"]
    assert sug["uid"] == "participante" and sug["co_item"] == "item" and sug["posicao"] == "position"
    cfgp = tmp_path / "v92.json"
    cfgp.write_text(json.dumps({"caminho": str(tmp_path / "exp" / "ano={ano}" / "area={area}" / "*.parquet"),
                                "colunas": sug}), encoding="utf-8")
    cfg = longo.ConfigLongo.ler(cfgp)
    out = tmp_path / "ds"
    rel = dataset.exportar_de_longo(cfg, 2099, world[2099]["itens"], out, fracao=1.0)
    lc = rel["areas"]["LC"]
    assert lc["sem_posicao"] == 0 and lc["itens_por_participante"] == {45: 800}
    df = dataset.carregar(out, [2099], ["LC"])
    raw = itm.load_itens(world[2099]["itens"])
    espanhol = set(raw.loc[raw["TP_LINGUA"] == 1, "CO_ITEM"])
    assert df["co_item"].isin(espanhol).any()  # participantes de espanhol mantêm os itens de espanhol
    assert (df.groupby("uid")["ordem_exame"].nunique() == 45).all()
    # 4 áreas do mesmo participante no mesmo uid
    todas = dataset.carregar(out, [2099])
    assert (todas.groupby("uid")["area"].nunique() == 4).all()
    # grade no formato grid_metrics.csv da v9.2 (year, area, students) contra a população do manifesto
    pd.DataFrame({"year": 2099, "area": ["CN", "CH", "LC", "MT"], "students": 800}).to_csv(tmp_path / "grid.csv", index=False)
    conc = dataset.conciliar_grade(out, tmp_path / "grid.csv")
    assert conc["conferem"] == 4 and all(r["base"].startswith("população") for r in [] + conc["divergentes"])


def test_layout_2024_resultados(tmp_path):
    from enemwise_pipeline import leitura
    (tmp_path / "microdados_enem_2024" / "DADOS").mkdir(parents=True)
    (tmp_path / "microdados_enem_2024" / "DADOS" / "RESULTADOS_2024.csv").write_text("x\n", encoding="utf-8")
    (tmp_path / "microdados_enem_2024" / "DADOS" / "PARTICIPANTES_2024.csv").write_text("x\n", encoding="utf-8")
    assert leitura.find_microdados(tmp_path, 2024).name == "RESULTADOS_2024.csv"
