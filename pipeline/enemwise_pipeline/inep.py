"""Download e verificação dos microdados na página oficial do INEP.

Fonte: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem

O INEP republica pacotes sem mudar o nome do arquivo. Se você baixou antes da
correção, o zip parece igual mas as colunas de alinhamento são outras. Por isso o
download grava um manifesto (data, tamanho, sha256) e a verificação compara a data
interna do ITENS_PROVA com a data de cada correção anunciada.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

URL = "https://download.inep.gov.br/microdados/microdados_enem_{ano}.zip"
PRIMEIRA_EDICAO_TRI = 2009

# Correções anunciadas na página do INEP (consulta em 17/09/2026)
CORRECOES = {
    2009: (date(2023, 4, 5), "CO_POSICAO dos itens de CH e CN no ITENS_PROVA_2009"),
    2012: (date(2023, 9, 8), "CO_POSICAO e TX_GABARITO no ITENS_PROVA_2012"),
    2022: (date(2024, 8, 8), "ajustes na base de itens"),
    2025: (date(2026, 9, 1), "ajuste no arquivo Leia-me"),
}

ALVOS = [
    re.compile(r"(^|/)ITENS_PROVA_\d{4}\.(csv|txt)$", re.I),
    re.compile(r"(^|/)MICRODADOS_ENEM_\d{4}\.(csv|txt)$", re.I),
]
PDF = re.compile(r"\.pdf$", re.I)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _baixar_arquivo(url: str, destino: Path, timeout: int = 60) -> dict:
    """Download em streaming com retomada (Range) se já houver arquivo parcial."""
    parcial = destino.with_suffix(destino.suffix + ".parcial")
    inicio = parcial.stat().st_size if parcial.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "ENEMWise/0.3"})
    if inicio:
        req.add_header("Range", f"bytes={inicio}-")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        modo = "ab" if inicio and resp.status == 206 else "wb"
        last_modified = resp.headers.get("Last-Modified")
        with parcial.open(modo) as f:
            shutil.copyfileobj(resp, f, length=1 << 20)
    parcial.replace(destino)
    return {"last_modified": last_modified}


def _extrair(zip_path: Path, pasta: Path, incluir_provas: bool) -> dict:
    extraidos, provas = [], []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            nome = info.filename
            quer = any(r.search(nome) for r in ALVOS) or (incluir_provas and PDF.search(nome))
            if not quer or info.is_dir():
                continue
            alvo = pasta / Path(nome).name if not PDF.search(nome) else pasta / "provas" / Path(nome).name
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, alvo.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1 << 20)
            registro = {"arquivo": str(alvo.relative_to(pasta)), "data_no_zip": datetime(*info.date_time).date().isoformat(),
                        "bytes": info.file_size}
            (provas if PDF.search(nome) else extraidos).append(registro)
    return {"dados": extraidos, "provas": provas}


def verificar_zip(zip_path: Path, ano: int) -> dict:
    """Compara a data interna do ITENS_PROVA com a data da correção anunciada."""
    if ano not in CORRECOES:
        return {"ano": ano, "status": "sem correção anunciada"}
    data_corr, motivo = CORRECOES[ano]
    with zipfile.ZipFile(zip_path) as z:
        itens = [i for i in z.infolist() if re.search(r"ITENS_PROVA", i.filename, re.I)]
        if not itens:
            return {"ano": ano, "status": "ITENS_PROVA ausente no zip"}
        data_zip = max(datetime(*i.date_time).date() for i in itens)
    antigo = data_zip < data_corr
    return {"ano": ano, "data_itens_no_zip": data_zip.isoformat(), "correcao": data_corr.isoformat(), "motivo": motivo,
            "status": "ANTERIOR À CORREÇÃO: baixe de novo" if antigo else "ok",
            "nota": "heurística pela data interna do zip; o sha256 no manifesto é a referência definitiva"}


def baixar(anos: list[int], destino: str | Path, incluir_provas: bool = True, manter_zip: bool = False,
           url_template: str = URL) -> dict:
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    manifesto_path = destino / "manifesto.json"
    manifesto = json.loads(manifesto_path.read_text(encoding="utf-8")) if manifesto_path.exists() else {}
    for ano in anos:
        if ano < PRIMEIRA_EDICAO_TRI:
            manifesto[str(ano)] = {"status": "ignorado: edição anterior a 2009, sem TRI nem Matriz de Referência atual"}
            continue
        pasta = destino / str(ano)
        pasta.mkdir(exist_ok=True)
        zip_path = pasta / f"microdados_enem_{ano}.zip"
        url = url_template.format(ano=ano)
        try:
            meta = _baixar_arquivo(url, zip_path)
            reg = {"url": url, "baixado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), **meta,
                   "verificacao": verificar_zip(zip_path, ano), **_extrair(zip_path, pasta, incluir_provas)}
            if not manter_zip:
                zip_path.unlink()
            manifesto[str(ano)] = reg
        except Exception as e:  # uma edição que falhar não interrompe as outras
            manifesto[str(ano)] = {"url": url, "erro": f"{type(e).__name__}: {e}"}
        manifesto_path.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifesto


def verificar_pasta(raiz: str | Path) -> list[dict]:
    """Para zips que você já tem: acha microdados_enem_<ano>.zip e checa cada um."""
    out = []
    for z in sorted(Path(raiz).rglob("*.zip")):
        m = re.search(r"microdados_enem_(\d{4})", z.name, re.I)
        if m:
            out.append({"zip": str(z), **verificar_zip(z, int(m.group(1)))})
    return out
