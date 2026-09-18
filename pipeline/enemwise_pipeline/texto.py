"""Fórmulas verbalizadas viram notação legível.

As fontes abertas de enunciados descrevem fórmulas por extenso, para modelos de linguagem:
"V de x é igual a, abre parêntese, x ao quadrado sobre 4, fecha parêntese, menos 10 vezes x".
Para quem estuda, isso é ilegível. As substituições abaixo só são aplicadas em frases que
tenham um marcador claro de fórmula, para não mexer em "sobre" e "vezes" da prosa comum.
"""
from __future__ import annotations

import re

MARCADORES = ("abre parêntese", "fração,", "é igual a", "ao quadrado", "ao cubo", "fatorial", "índice ",
              "elevado a", "raiz quadrada", "menor ou igual a", "maior ou igual a", "fecha parêntese")
SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _frase_de_formula(frase: str) -> bool:
    return any(m in frase for m in MARCADORES)


def _formatar(f: str) -> str:
    f = re.sub(r"fração,\s*numerador\s+(.+?),\s*denominador,?\s*(.+?)(?=(?:,\s*fecha parêntese|\.|,\s*mais\b|,\s*menos\b|$))",
               r"(\1)/(\2)", f)
    f = re.sub(r",?\s*abre parêntese,?\s*", " (", f)
    f = re.sub(r",?\s*fecha parêntese,?\s*", ") ", f)
    f = re.sub(r"\bé igual a\b", "=", f)
    f = re.sub(r"\bmenor ou igual a\b", "≤", f)
    f = re.sub(r"\bmaior ou igual a\b", "≥", f)
    f = re.sub(r"(\w)\s+ao quadrado", r"\1²", f)
    f = re.sub(r"(\w)\s+ao cubo", r"\1³", f)
    f = re.sub(r"(\w)\s+fatorial", r"\1!", f)
    f = re.sub(r"(\w)\s+índice\s+(\d)\b", lambda m: m.group(1) + m.group(2).translate(SUB), f)
    f = re.sub(r"\belevado a menos\s+(\d+)", r"^(−\1)", f)
    f = re.sub(r"\belevado a\s+(\d+)", r"^\1", f)
    f = re.sub(r"\braiz quadrada de\s+", "√", f)
    f = re.sub(r"\s+vezes\s+", " · ", f)
    f = re.sub(r"\s+sobre\s+", " / ", f)
    f = re.sub(r"\s+dividido por\s+", " / ", f)
    f = re.sub(r"\(\s+", "(", f)
    f = re.sub(r"\s+\)", ")", f)
    f = re.sub(r"\)\s*([.,])", r")\1", f)
    return re.sub(r"[ \t]{2,}", " ", f).strip()


def formatar_formulas(texto: str | None) -> str | None:
    if not texto:
        return texto
    # comparações entre um símbolo e um número são inequívocas mesmo fora de frase de fórmula
    texto = re.sub(r"(\b[A-Za-z]\d?|\d+(?:,\d+)?)\s+menor que\s+(\d)", r"\1 < \2", texto)
    texto = re.sub(r"(\b[A-Za-z]\d?|\d+(?:,\d+)?)\s+maior que\s+(\d)", r"\1 > \2", texto)
    # separa frases preservando quebras de linha e espaços originais
    partes = re.split(r"((?<=[.!?])\s+)", texto)
    return "".join(p if i % 2 else (_formatar(p) if _frase_de_formula(p) else p) for i, p in enumerate(partes))
