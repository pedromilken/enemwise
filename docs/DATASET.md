# Microdados do ENEM como dataset de Knowledge Tracing

O mesmo pipeline que calibra o app exporta os microdados no formato usado por modelos de KT.

---

## O que o dataset é, e o que não é

Pense numa **fotografia de 3 milhões de pessoas fazendo a mesma prova**, não num filme de alguém estudando.

| É | Não é |
|---|---|
| Respostas reais, em escala nacional, com habilidade anotada pelo INEP em cada questão | Registro de aprendizagem: não há ensino entre as questões |
| Parâmetros TRI oficiais por item | Sequência temporal: **a ordem é a posição no caderno**, e o participante pode responder em outra ordem |
| Um **controle nulo** para KT: ganho atribuído a "aprendizagem" aqui é confundidor | Benchmark para comparar quem aprende mais rápido |

---

## Gerar a partir da exportação da v9.2 (recomendado)

Os acertos vêm do alinhamento certificado de `enem_kt_confounds/src/prepare.py`, nas quatro áreas e em todas as edições. O ENEMWise não realinha nada.

**1. Exportar no projeto dos confundidores** (ver `LEIAME_EXPORT_ENEMWISE.md` lá):

```powershell
python export_enemwise.py --data-dir $HOME\Downloads\enem --anos 2009-2025 --frac 0.05 --out $HOME\projetos\enem_export
```

Os caches `long_cache_n100000_s42.parquet` das fases 2 e 3 **não servem**: não guardam o id do participante e vêm do primeiro bloco do CSV.

**2. Mapear as colunas** (a sugestão já sai certa para esse formato):

```powershell
$arq = Get-ChildItem $HOME\projetos\enem_export\ano=2019\area=LC -Filter *.parquet | Select-Object -First 1
enemwise longo-inspecionar --arquivo $arq.FullName --saida v92.json
```

No `v92.json`, ajuste `caminho` para `C:/Users/<voce>/projetos/enem_export/ano={ano}/area={area}/*.parquet`.

| Campo | Coluna da exportação | Observação |
|---|---|---|
| `uid` | `participante` | liga as quatro áreas |
| `co_item`, `correct`, `nota` | `item`, `correct`, `score` | |
| `posicao` | `position` | **preferida**: é a ordem certificada da folha, inclusive em LC com espanhol |
| `co_prova` | `prova` | usada só se não houver `posicao` |

**3. Gerar o dataset e conciliar com a grade do artigo:**

```powershell
enemwise dataset-longo --config v92.json --raiz-inep $HOME\Downloads\enem --anos 2009-2025 `
  --fracao 1.0 --grade $HOME\projetos\enem_kt_confounds\grid_v9\grid_metrics.csv --out $HOME\projetos\enem-kt
```

- `--fracao 1.0` porque o sorteio já foi feito na exportação.
- A conciliação lê o `_manifesto.json` de cada célula e compara a **população alinhada** com `students` da grade, com tolerância de 0,1%. A grade descartou brancos e a exportação conta branco como erro, então quem deixou a área inteira em branco explica diferenças pequenas e positivas.

**4. Priors do app pela mesma fonte:**

```powershell
enemwise batch --raiz $HOME\Downloads\enem --anos 2009-2025 --longo-config v92.json --out out
```

## Gerar a partir dos microdados brutos (sem LC)

```bash
enemwise baixar  --anos 2009-2025 --destino /dados/inep
enemwise dataset --raiz /dados/inep --anos 2009-2025 --fracao 0.02 --out /dados/enem-kt
enemwise dataset-pykt --dataset /dados/enem-kt --nome enem_mt_2019 --anos 2019 --areas MT
enemwise dataset-benchmark --dataset /dados/enem-kt --ano 2019 --area MT --permutacoes 500
```

- `--fracao 1.0` exporta todos os presentes. Isso dá centenas de milhões de linhas por edição (≈ presentes × 45 × áreas), grande demais para ferramentas de KT que carregam tudo em memória, como o pyKT.
- **A amostra é determinística:** hash de (ano, linha). A mesma semente seleciona os mesmos participantes em qualquer máquina e com qualquer tamanho de chunk.
- **LC entra pelo formato longo auditado**, como no resto do pipeline.

---

## Estrutura

```
enem-kt/
  interacoes/ano=<ano>/part-*.parquet
  participantes/ano=<ano>/part-*.parquet
  itens.csv  habilidades.csv
  pykt/<nome>/data.txt
  relatorios/<ano>.json
  DATASHEET.md  SHA256SUMS
```

**`interacoes`** (uma linha por participante × questão)

| Coluna | Significado |
|---|---|
| `uid` | ano × 10⁸ + linha no arquivo do INEP; estável entre reexecuções |
| `ano` | partição |
| `area`, `dia` | área e dia de aplicação (a ordem dos dias mudou em 2017) |
| `ordem_exame` | ordem dentro do exame: dia, bloco da área, posição |
| `posicao_caderno`, `co_prova` | posição e caderno de origem |
| `co_item`, `habilidade`, `anulado` | item, habilidade da Matriz, marca de anulação |
| `resposta`, `correct` | letra marcada (`.` branco, `*` dupla) e acerto |
| `nota_area`, `banda` | nota na área e faixa de 100 pontos |

**`participantes`**: `uid`, `fold` (0–4), `teste` (20% dos participantes) e notas por área. **Não inclui o questionário socioeconômico**, por risco de reidentificação.

**`itens.csv` e `habilidades.csv`** trazem ids inteiros. Isso importa porque o leitor do pyKT descarta a linha inteira se o texto contiver `NA`.

---

## Auditorias automáticas

- **Gabarito linha a linha.** Cada participante traz `TX_GABARITO_<área>`. O relatório mostra a fração de linhas em que ele confere com o gabarito do caderno. É uma checagem de alinhamento mais direta que a correlação com o parâmetro b.
- **Tamanho da resposta.** Strings com comprimento diferente do caderno são descartadas e contadas.
- **Formato pyKT.** O `data.txt` foi validado com `read_data` do próprio pyKT-toolkit.

---

## O benchmark e sua falsificação

As linhas de base são prevalência, dificuldade do item, TRI 3PL prequencial e BKT com e sem P(T).

Os dados sintéticos, **sem aprendizagem nenhuma**, mostraram algo importante: **P(T) > 0 melhora o log-loss mesmo assim.** Aprender não tem nada a ver com isso: P(T) impede que P(L) cole em 0 ou 1, funcionando como regularização. Por isso o benchmark mede o ganho de duas formas:

1. **com a ordem embaralhada** dentro de cada participante: o ganho que sobra é regularização;
2. **com a ordem real**: a diferença para o embaralhado ainda mistura efeito de posição, fadiga e a ordenação das dificuldades no caderno.

Nenhuma das duas é aprendizagem. A identificação limpa do efeito de posição usa o desenho do ENEM: **o mesmo item em posições diferentes nos cadernos de cores diferentes**, com efeitos fixos de item. É o que faz o pipeline dos confundidores; este benchmark é uma triagem.

---

## Distribuição

Antes de publicar o dataset gerado (por exemplo, no Zenodo), confira os termos no Leia-me de cada pacote. O rodapé do portal gov.br declara CC BY-ND 3.0 para o conteúdo do site, o que conflitaria com derivados se valesse para os microdados. Na dúvida, publique o código, a semente e o manifesto com sha256: qualquer pessoa regenera o mesmo dataset.
