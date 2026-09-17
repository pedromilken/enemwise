"""DATASHEET.md no modelo de Datasheets for Datasets (Gebru et al., 2021), preenchido com os números da exportação."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


def gerar(out: Path) -> Path:
    rels = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((out / "relatorios").glob("[0-9]*.json"))]
    linhas = []
    for r in rels:
        for area, s in r["areas"].items():
            if "participantes_amostrados" in s:  # fonte: exportação longa v9.2
                linhas.append(f"| {r['ano']} | {area} | {s['participantes_amostrados']:,} | "
                              f"{s['itens_fora_do_itens_prova'] + s['sem_posicao']:,} | alinhamento auditado no v9.2 |")
            else:
                linhas.append(f"| {r['ano']} | {area} | {s['amostradas']:,} | {s['tamanho_invalido']:,} | "
                              f"{'' if s['taxa_gabarito_confere'] is None else s['taxa_gabarito_confere']} |")
    itens = pd.read_csv(out / "itens.csv") if (out / "itens.csv").exists() else pd.DataFrame()
    fracao = rels[0]["fracao"] if rels else "?"
    fonte = rels[0].get("fonte", "microdados brutos (CN, CH, MT)") if rels else "?"
    conc = out / "relatorios" / "conciliacao_grade.json"
    if conc.exists():
        c = json.loads(conc.read_text(encoding="utf-8"))
        fonte += f"; conciliação com a grade certificada: {c['conferem']} de {c['celulas']} células conferem"
    texto = f"""# Datasheet: ENEM-KT (derivado dos microdados do INEP)

Modelo: Gebru et al. (2021), *Datasheets for Datasets*, Communications of the ACM 64(12).

## Motivação
Oferecer um conjunto de dados brasileiro, em larga escala, no formato usado por modelos de Knowledge Tracing,
com habilidades já anotadas pelo INEP e parâmetros TRI oficiais.

## Composição
- Unidade: resposta de um participante a uma questão objetiva.
- Edições e áreas exportadas:

| Ano | Área | Participantes amostrados | Linhas descartadas | Verificação de alinhamento |
|---|---|---|---|---|
{chr(10).join(linhas)}

- Questões no dicionário: {len(itens):,}. Habilidades: {pd.read_csv(out / 'habilidades.csv').shape[0] if (out / 'habilidades.csv').exists() else '?'}.
- Amostra: fração {fracao} por edição, sorteio determinístico por hash do participante; o mesmo participante entra nas quatro áreas.
- Divisão: 5 folds por participante e 20% dos participantes separados como teste.
- **Sem dados do questionário socioeconômico** por padrão (risco de reidentificação em recortes pequenos).

## Coleta
Microdados públicos do Enem, página oficial do INEP. Versão de cada pacote identificada pelo sha256 no `manifesto.json` do download.

## Pré-processamento
- Cadernos adaptados removidos; língua estrangeira escolhida mantida.
- Itens anulados permanecem com `anulado = 1` (ocupam posição no caderno).
- Branco e dupla marcação contam como erro, como na correção do exame.
- Fonte dos acertos: {fonte}.
- Linguagens (LC) só entra pelo alinhamento multilíngue auditado.

## Usos recomendados
- Calibração e comparação de modelos de resposta a item.
- **Controle nulo para Knowledge Tracing**: não há ensino entre as questões, então ganho atribuído a
  "aprendizagem" indica confundidor (posição, fadiga, chute).
- Estudo de efeitos de posição e de acerto casual.

## Usos que este dataset NÃO sustenta
- Inferir aprendizagem ao longo da sequência: **ordem é posição no caderno, não tempo**.
- Avaliar ou ranquear escolas, municípios ou indivíduos.
- Qualquer tentativa de reidentificação.

## Distribuição
Confira os termos no Leia-me de cada pacote do INEP antes de redistribuir. O rodapé do portal gov.br
declara CC BY-ND 3.0 para o conteúdo do site; os microdados seguem a política de dados abertos do INEP.
Na dúvida, distribua o código e o manifesto, e deixe cada usuário gerar o dataset.

## Manutenção
Reexecute a partir do manifesto. O INEP republicou pacotes corrigidos (2009, 2012, 2022, 2025) sem mudar o nome.
"""
    p = out / "DATASHEET.md"
    p.write_text(texto, encoding="utf-8")
    with (out / "SHA256SUMS").open("w", encoding="utf-8", newline="\n") as f:
        for arq in sorted(out.rglob("*")):
            if arq.is_file() and arq.name != "SHA256SUMS":
                f.write(f"{hashlib.sha256(arq.read_bytes()).hexdigest()}  {arq.relative_to(out)}\n")
    return p
