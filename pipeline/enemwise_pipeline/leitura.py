"""Leitura tolerante: separador, encoding e nomes de arquivo variam entre edições."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def sniff(path: str | Path) -> dict:
    raw = Path(path).open("rb").read(65536)
    try:
        raw.decode("utf-8")
        enc = "utf-8"
    except UnicodeDecodeError:
        enc = "latin-1"
    header = raw.decode(enc, errors="replace").splitlines()[0]
    sep = max([";", ",", "\t", "|"], key=header.count)
    return {"sep": sep, "encoding": enc}


def ler_texto(path: str | Path) -> str:
    """Lê texto detectando BOM. O Windows PowerShell 5.1 grava UTF-16 com '>' e UTF-8 com BOM com Out-File."""
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def columns(path: str | Path) -> list[str]:
    return list(pd.read_csv(path, nrows=0, **sniff(path)).columns)


def resolve(cols: list[str], candidates: list[str], area: str | None = None) -> str | None:
    upper = {c.upper(): c for c in cols}
    for cand in candidates:
        name = cand.format(a=area) if area else cand
        if name.upper() in upper:
            return upper[name.upper()]
    return None


def find_microdados(root: str | Path, ano: int) -> Path | None:
    """MICRODADOS_ENEM_<ano> até 2023; RESULTADOS_<ano> no layout do INEP a partir de 2024."""
    return find_file(root, "MICRODADOS_ENEM", ano) or find_file(root, "RESULTADOS", ano)


def find_file(root: str | Path, stem: str, ano: int) -> Path | None:
    """Procura, sem diferenciar maiúsculas, arquivos como MICRODADOS_ENEM_2014.csv."""
    rx = re.compile(rf"^{stem}_{ano}\.(csv|txt)$", re.IGNORECASE)
    hits = sorted(p for p in Path(root).rglob("*") if p.is_file() and rx.match(p.name))
    return hits[0] if hits else None
