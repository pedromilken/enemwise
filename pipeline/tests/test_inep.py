import functools
import http.server
import json
import threading
import zipfile

import pytest

from enemwise_pipeline import inep, leitura


def _zip(path, ano, data_itens):
    with zipfile.ZipFile(path, "w") as z:
        info = zipfile.ZipInfo(f"microdados_enem_{ano}/DADOS/ITENS_PROVA_{ano}.csv", date_time=(*data_itens, 12, 0, 0))
        z.writestr(info, "CO_POSICAO;SG_AREA;CO_ITEM;TX_GABARITO;CO_PROVA\n1;MT;10;A;99\n")
        z.writestr(f"microdados_enem_{ano}/DADOS/MICRODADOS_ENEM_{ano}.csv", "NU_INSCRICAO\n1\n")
        z.writestr(f"microdados_enem_{ano}/PROVAS E GABARITOS/ENEM_{ano}_P1_CAD_01_DIA_1_AZUL.pdf", b"%PDF-1.4 fake")
        z.writestr(f"microdados_enem_{ano}/LEIA-ME E DOCUMENTOS TÉCNICOS/leia-me.pdf", b"%PDF-1.4 fake")
        z.writestr(f"microdados_enem_{ano}/INPUTS/INPUT_R_{ano}.R", "x")


@pytest.fixture
def servidor(tmp_path):
    raiz = tmp_path / "srv"
    raiz.mkdir()
    _zip(raiz / "microdados_enem_2012.zip", 2012, (2022, 1, 10))   # anterior à correção de 08/09/2023
    _zip(raiz / "microdados_enem_2019.zip", 2019, (2021, 5, 1))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(raiz))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/microdados_enem_{{ano}}.zip"
    httpd.shutdown()


def test_baixa_extrai_so_o_necessario_e_grava_manifesto(servidor, tmp_path):
    man = inep.baixar([2008, 2012, 2019, 2030], tmp_path / "inep", url_template=servidor)
    assert "ignorado" in man["2008"]["status"]
    assert "erro" in man["2030"]  # 404 não derruba as outras edições
    r = man["2019"]
    assert len(r["sha256"]) == 64 and r["verificacao"]["status"] == "sem correção anunciada"
    assert {d["arquivo"] for d in r["dados"]} == {"ITENS_PROVA_2019.csv", "MICRODADOS_ENEM_2019.csv"}
    assert len(r["provas"]) == 2 and not (tmp_path / "inep" / "2019" / "INPUT_R_2019.R").exists()
    assert not (tmp_path / "inep" / "2019" / "microdados_enem_2019.zip").exists()
    assert leitura.find_file(tmp_path / "inep", "ITENS_PROVA", 2019) is not None  # batch encontra o que foi baixado
    assert json.loads((tmp_path / "inep" / "manifesto.json").read_text(encoding="utf-8"))["2012"]["sha256"] == man["2012"]["sha256"]


def test_detecta_zip_anterior_a_correcao(servidor, tmp_path):
    man = inep.baixar([2012], tmp_path / "inep", url_template=servidor, manter_zip=True)
    assert man["2012"]["verificacao"]["status"].startswith("ANTERIOR")
    rel = inep.verificar_pasta(tmp_path / "inep")
    assert rel[0]["ano"] == 2012 and rel[0]["status"].startswith("ANTERIOR")
