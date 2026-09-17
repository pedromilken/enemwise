"""Testes da camada estatística e pedagógica.

Os testes do SPPA usam os números publicados em Alalawi et al. (2025) como regressão:
se o módulo reproduz o artigo, sabemos que ele calcula o que diz calcular.
"""
import json

import numpy as np
import pandas as pd
import pytest

from enemwise_pipeline import avaliacao, bloom, estatistica as est

# ---------------------------------------------------------------- reprodução do SPPA
RQ2 = pd.DataFrame({"aprovado": [26, 6], "reprovado": [16, 40], "desistiu": [15, 9]}, index=["2021", "2019"])
RQ3 = pd.DataFrame({"aprovado": [153, 115], "reprovado": [65, 106], "desistiu": [30, 27]}, index=["2021", "2019"])


def test_reproduz_qui_quadrado_rq2_e_rq3():
    r2, r3 = est.qui_quadrado(RQ2), est.qui_quadrado(RQ3)
    assert r2["chi2"] == pytest.approx(24.258, abs=1e-3)
    assert r3["chi2"] == pytest.approx(15.376, abs=1e-3)
    assert [p["significativo"] for p in r2["posthoc"]] == [True, True, False]


def test_teste_t_do_sppa_so_bate_excluindo_desistentes():
    # Texto do artigo: 41,1557 (19,38583) vs 32,6362 (16,20588); t(80,247) = 2,225
    todos = est.welch_resumo(41.1557, 19.38583, 57, 32.6362, 16.20588, 55)
    concluintes = est.welch_resumo(41.1557, 19.38583, 42, 32.6362, 16.20588, 46)
    assert concluintes.t == pytest.approx(2.225, abs=1e-3) and concluintes.gl == pytest.approx(80.25, abs=0.01)
    assert todos.gl > 100  # com os 57/55 o gl seria ~108, não 80
    # Com o desvio e a média do grupo controle da Tabela 5, o efeito deixa de ser significativo
    tabela5 = est.welch_resumo(41.1557, 19.38583, 42, 35.6130, 19.99442, 46)
    assert tabela5.p > 0.05


# ---------------------------------------------------------------- propensão
def test_pareamento_sem_reposicao_equilibra():
    rng = np.random.default_rng(0)
    n = 800
    idade = rng.normal(17, 1.5, n)
    escola_publica = rng.random(n) < 0.6
    p = 1 / (1 + np.exp(-(0.8 * (idade - 17) + 0.9 * escola_publica - 0.5)))
    df = pd.DataFrame({"tratado": rng.random(n) < p, "idade": idade, "escola_publica": escola_publica})
    r = est.pareamento_propensao(df, "tratado", ["idade", "escola_publica"])
    controles = [c for _, c in r["pares"]]
    assert len(controles) == len(set(controles))  # sem reposição
    assert abs(r["balanco_smd"]["idade"]["antes"]) > 0.1
    assert r["balanceado"]


def test_comparar_medias_relata_os_dois_recortes():
    df = pd.DataFrame({"grupo": ["t"] * 6 + ["c"] * 6, "nota": [60, 55, 70, np.nan, 65, 50, 40, 45, 50, 55, np.nan, 42],
                       "desistiu": [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0]})
    r = est.comparar_medias(df, "grupo", "nota", "desistiu")
    assert {"concluintes", "todos_com_nota", "taxa_desistencia"} <= r.keys()


# ---------------------------------------------------------------- avaliação prequencial
def test_metricas_reportam_a_classe_de_erro_e_linhas_de_base(tmp_path):
    rng = np.random.default_rng(1)
    for k in range(5):
        tent = []
        for i in range(40):
            p = rng.uniform(0.1, 0.9)
            tent.append({"itemId": f"x-{i}", "resposta": "A", "correta": bool(rng.random() < p), "usouDica": False,
                         "ts": i, "pPrevisto": p, "pBanda": 0.5, "confianca": ["chute", "duvida", "certeza"][i % 3]})
        (tmp_path / f"e{k}.json").write_text(json.dumps({"versao": 1, "nome": f"e{k}", "tentativas": tent}), encoding="utf-8")
    rel = avaliacao.avaliar(avaliacao.carregar_exportacoes(tmp_path))
    assert rel["tentativas"] == 200
    assert rel["modelo_bkt"]["auc"] > rel["base_prevalencia"]["auc"]
    assert "classe_erro" in rel["modelo_bkt"] and rel["modelo_bkt"]["ece"] < 0.1
    assert set(rel["autoavaliacao"]) == {"chute", "duvida", "certeza"}


def test_auc_perfeita_e_aleatoria():
    y = np.array([0, 0, 1, 1])
    assert avaliacao.auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert avaliacao.auc(y, np.array([0.5, 0.5, 0.5, 0.5])) == 0.5


# ---------------------------------------------------------------- Bloom
def test_bloom_sugere_pelo_verbo_e_marca_para_revisao(tmp_path):
    assert bloom.sugerir("Resolver situação-problema envolvendo porcentagens") == "Aplicação"
    assert bloom.sugerir("Avaliar propostas de intervenção no ambiente") == "Avaliação"
    csvf = tmp_path / "h.csv"
    csvf.write_text("chave,descricao,bloom\nMT-H1,Reconhecer diferentes significados dos números,\nCH-H9,Comparar propostas,Análise\n", encoding="utf-8")
    rel = bloom.arquivo(csvf, tmp_path / "habilidades.json")
    out = json.loads((tmp_path / "habilidades.json").read_text(encoding="utf-8"))
    assert out["MT-H1"] == {"descricao": "Reconhecer diferentes significados dos números", "bloom": "Conhecimento", "bloom_sugerido": True}
    assert out["CH-H9"]["bloom_sugerido"] is False and rel["sem_sugestao"] == []


def test_conteudos_classifica_por_termo_e_habilidade():
    from enemwise_pipeline import conteudos as con
    assert "geometria-analitica" in con.classificar(
        "No plano cartesiano, a equação da reta que passa pelos pontos A e B é", "MT", 22)
    assert "geometria-espacial" in con.classificar(
        "Um reservatório em forma de cilindro tem volume de 500 litros e altura de 2 m", "MT", 12)
    assert "genetica" in con.classificar(
        "O heredograma mostra a herança de um gene recessivo ligado ao cromossomo X", "CN", 13)
    assert "cartografia" in con.classificar(
        "A projeção cartográfica do mapa distorce as áreas em altas latitudes", "CH", 6)
    # texto sem termo característico fica sem tópico, em vez de receber palpite
    assert con.classificar("Considere a situação descrita a seguir e responda.", "MT", 3) == []
    # tema específico só entra com termo forte
    assert "geometria-analitica" not in con.classificar("O gráfico mostra as coordenadas do eixo x", "MT", 20)


def test_conteudos_catalogo_e_cobertura():
    import pandas as pd
    from enemwise_pipeline import conteudos as con
    cat = con.catalogo()
    assert len(cat) >= 40 and {c["area"] for c in cat} == {"CN", "CH", "LC", "MT"}
    assert len({c["id"] for c in cat}) == len(cat)  # ids únicos
    itens = pd.DataFrame({
        "area": ["MT", "MT"], "habilidade": [12, 3],
        "enunciado": ["O volume do cilindro em litros", "Considere o texto"], "alternativas": ["", ""]})
    r = con.rotular(itens)
    assert list(r["topicos"].apply(bool)) == [True, False]
    assert con.cobertura(r).iloc[0]["cobertura"] == 0.5
