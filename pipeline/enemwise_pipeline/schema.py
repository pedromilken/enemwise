"""Contrato com os arquivos do INEP. Tudo que depende do layout dos microdados fica aqui.

Os nomes de colunas mudaram entre 2009 e 2025. Cada campo lógico tem uma lista de
aliases; se uma edição usar outro nome, basta acrescentá-lo aqui.
"""
from __future__ import annotations

AREAS = ("CN", "CH", "LC", "MT")

AREA_NOME = {
    "CN": "Ciências da Natureza",
    "CH": "Ciências Humanas",
    "LC": "Linguagens e Códigos",
    "MT": "Matemática",
}

ITENS_REQUIRED = ["CO_POSICAO", "SG_AREA", "CO_ITEM", "TX_GABARITO", "CO_PROVA"]
ITENS_OPTIONAL = ["CO_HABILIDADE", "NU_PARAM_A", "NU_PARAM_B", "NU_PARAM_C",
                  "IN_ITEM_ABAN", "TX_COR", "TP_LINGUA", "IN_ITEM_ADAPTADO"]

RESP_ALIASES = {
    "presenca": ["TP_PRESENCA_{a}", "IN_PRESENCA_{a}"],
    "prova": ["CO_PROVA_{a}", "ID_PROVA_{a}"],
    "nota": ["NU_NOTA_{a}", "NU_NT_{a}"],
    "respostas": ["TX_RESPOSTAS_{a}"],  # vale para MICRODADOS_ENEM (até 2023) e RESULTADOS (2024+)
}

# Primeira questão de cada bloco de 45 no caderno. Serve só como hipótese de numeração
# no vínculo com o texto; a ordem dos dias mudou em 2017 e o vínculo testa todas.
BLOCK_STARTS = (1, 46, 91, 136)

# Faixas na escala do ENEM: interpretáveis para professor e comparáveis entre edições.
BANDAS = [(0, 450), (450, 550), (550, 650), (650, 750), (750, 1001)]


def banda_label(lo: int, hi: int) -> str:
    return f"{lo}-{min(hi, 1000)}"
