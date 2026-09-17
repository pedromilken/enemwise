# Rodar todas as edições (2009–2025)

Roteiro para processar localmente e devolver só o pacote agregado.

---

## 1. Instalar

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,parquet,textos]"
pytest -q        # 11 testes, todos com dados sintéticos
```

## 2. Organizar as entradas

**Microdados.** Baixe direto da [página oficial do INEP](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem):

```bash
enemwise baixar --anos 2009-2025 --destino /dados/inep
```

O comando grava `manifesto.json` com URL, data, tamanho e sha256, e extrai só o ITENS_PROVA,
o MICRODADOS e os PDFs das provas. O zip é apagado depois; use `--manter-zip` para guardá-lo.
Edições de 1998 a 2008 são ignoradas: não usam TRI nem a Matriz de Referência atual.

**Já tem os zips?** Confira se algum é anterior às correções que o INEP publicou sem mudar o nome do arquivo:

```bash
enemwise verificar --raiz /pasta/dos/zips
```

| Edição | Republicado em | O que mudou |
|---|---|---|
| 2009 | 05/04/2023 | `CO_POSICAO` dos itens de CH e CN no ITENS_PROVA |
| 2012 | 08/09/2023 | `CO_POSICAO` e `TX_GABARITO` no ITENS_PROVA |
| 2022 | 08/08/2024 | ajustes na base de itens |
| 2025 | 01/09/2026 | ajuste no Leia-me |

2009 e 2012 afetam exatamente as colunas de alinhamento. Um zip antigo passa na leitura, mas desalinha o caderno.

Com os zips extraídos em qualquer estrutura, o `batch` acha `ITENS_PROVA_<ano>.csv` e
`MICRODADOS_ENEM_<ano>.csv` sozinho, sem diferenciar maiúsculas.

**Textos das questões.** Exporte as fontes abertas para JSONL. A ordem em `--questoes` é a
prioridade: maritaca primeiro, porque traz descrição das imagens.

```python
from datasets import load_dataset
for ano in ("2022", "2023", "2024"):
    load_dataset("maritaca-ai/enem", ano, split="train").to_json(f"textos/maritaca_{ano}.jsonl", force_ascii=False)
load_dataset("eduagarcia/enem_challenge", split="train").to_json("textos/enem_challenge.jsonl", force_ascii=False)
```

O carregador detecta as colunas usuais. Ao rodar, ele imprime quantas questões leu por
fonte e por edição: se aparecer 0, a fonte tem um schema que ele não reconheceu.

**Exportação longa v9.2 nas quatro áreas (recomendado).** Gere o mapeamento com
`enemwise longo-inspecionar` e passe `--longo-config v92.json` ao `batch`. Ela substitui o
caminho bruto em todas as áreas. Detalhes em [`DATASET.md`](DATASET.md).

**Formato longo por arquivo (alternativa antiga).** Se quiser reaproveitar o alinhamento auditado do
pipeline dos confundidores, grave um arquivo por célula em `--long-dir`:

```
<long-dir>/2019_LC.parquet     colunas: co_item, correct (0/1), nota (NU_NOTA da área)
```

Quando existe arquivo longo para uma área, ele tem precedência sobre o caminho bruto.
Dá para usar em todas as áreas, não só LC.

## 3. Ensaio rápido

```bash
enemwise batch --raiz /dados/inep --anos 2023 --questoes textos/*.jsonl --nrows 200000 --out ensaio
```

Confira `ensaio/2023/relatorio.json`: auditoria com `ok: true` e vínculo de texto `aceito: true`.

## 4. Rodada completa

```bash
enemwise batch --raiz /dados/inep --anos 2009-2025 \
  --questoes textos/maritaca_2022.jsonl textos/maritaca_2023.jsonl textos/maritaca_2024.jsonl textos/enem_challenge.jsonl \
  --long-dir /dados/long --jobs 3 --out out

enemwise merge --entrada out --web ../web/public/data
```

- Cada edição lê o CSV uma vez por área bruta. `--jobs` roda edições em paralelo, cerca de 2 GB de RAM cada.
- Uma edição que falhar não interrompe as outras. O motivo fica em `out/batch_status.json`.

## 5. O que conferir

| Onde | O quê | Sinal de problema |
|---|---|---|
| `out/batch_status.json` | status por edição | qualquer `erro` |
| `meta.json → auditoria_reprovada` | células fora dos priors | lista não vazia |
| `meta.json → auditoria` | `rho_p_b` por célula | acima de −0,4 |
| `meta.json → vinculo_texto` | casamento por caderno | `match` abaixo de 0,9 |
| `priors.json → p_l0_sd` | variação entre edições | acima de ~0,15 sugere não agregar |
| saída do `merge` | `tamanho_mb` | acima de 25 MB |

Erro de coluna ausente? Acrescente o nome antigo em `schema.RESP_ALIASES` e rode só aquela edição de novo.

## 6. O que devolver

Só isto, compactado:

```
web/public/data/meta.json
web/public/data/priors.json
web/public/data/items/*.json
out/batch_status.json
out/*/relatorio.json
```

Não inclua `counts.csv`, `items_full.json` nem nada dos microdados.

## Cobertura esperada

| Edições | Priors (calibração) | Questões praticáveis no app |
|---|---|---|
| 2009–2017 | sim | parcial: questões sem imagem, via enem_challenge |
| 2018–2021 | sim | não há fonte aberta estruturada; os PDFs das provas vêm no zip do INEP |
| 2022–2024 | sim | completas, via maritaca |
| 2025 | sim | idem 2018–2021 |

Edições sem parâmetros TRI ou sem `CO_HABILIDADE` no ITENS_PROVA não geram priors; o
relatório mostra `itens_utilizaveis` baixo nesses casos.
