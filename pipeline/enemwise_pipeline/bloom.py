"""Sugestão de nível da Taxonomia de Bloom (1956) para habilidades da Matriz de Referência.

É uma heurística pelo verbo inicial do descritor, não uma classificação validada.
Por isso toda saída sai marcada com bloom_sugerido = true, para revisão humana,
do mesmo jeito que no SPPA o mapeamento de alinhamento é feito pelos docentes.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

NIVEIS = ["Conhecimento", "Compreensão", "Aplicação", "Análise", "Síntese", "Avaliação"]

VERBOS = {
    "Conhecimento": ["reconhecer", "identificar", "nomear", "listar", "definir", "localizar"],
    "Compreensão": ["compreender", "interpretar", "explicar", "descrever", "associar", "relacionar", "caracterizar", "diferenciar"],
    "Aplicação": ["aplicar", "utilizar", "usar", "resolver", "calcular", "empregar", "operar", "recorrer", "dimensionar"],
    "Análise": ["analisar", "comparar", "confrontar", "inferir", "distinguir", "estabelecer"],
    "Síntese": ["elaborar", "propor", "construir", "planejar", "formular", "organizar"],
    "Avaliação": ["avaliar", "julgar", "criticar", "argumentar", "justificar", "selecionar", "posicionar"],
}
_INDEX = {v: n for n, vs in VERBOS.items() for v in vs}


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def sugerir(descricao: str) -> str | None:
    """Usa o primeiro verbo reconhecido no início do descritor."""
    palavras = re.findall(r"[a-zà-ú]+", descricao.lower())[:6]
    alvo = {_norm(k): n for k, n in _INDEX.items()}
    for w in palavras:
        if _norm(w) in alvo:
            return alvo[_norm(w)]
    return None


def arquivo(entrada: str | Path, saida: str | Path) -> dict:
    """CSV com colunas chave (ex.: MT-H17) e descricao -> habilidades.json do app."""
    out, sem = {}, []
    from .leitura import ler_texto
    try:
        texto = ler_texto(entrada)
    except UnicodeDecodeError:  # CSV salvo pelo Excel em cp1252
        texto = Path(entrada).read_bytes().decode("cp1252")
    sep = ";" if texto.splitlines()[0].count(";") > texto.splitlines()[0].count(",") else ","
    if True:
        for row in csv.DictReader(texto.splitlines(), delimiter=sep):
            nivel = row.get("bloom") or sugerir(row["descricao"])
            rec = {"descricao": row["descricao"].strip()}
            if nivel:
                rec["bloom"] = nivel
                rec["bloom_sugerido"] = not bool(row.get("bloom"))
            else:
                sem.append(row["chave"])
            out[row["chave"].strip()] = rec
    Path(saida).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"habilidades": len(out), "sem_sugestao": sem}
