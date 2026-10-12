# Modo prova: agentes fazendo a 1ª etapa do ENEM

O laboratório de agentes avalia os modelos de KT com questões soltas, por habilidade. O modo prova faz outra coisa: põe o agente no lugar do candidato, com o caderno do ano, o relógio oficial e nenhuma correção até o fim do dia. A saída tem o mesmo formato da exportação longa do v9.2, então as análises do estudo dos confundidores rodam sem mudança nas 68 células (4 áreas × 17 edições), pareadas com os candidatos reais.

Analogia: o laboratório é a lista de exercícios; o modo prova é o simulado no domingo, com fiscal e relógio na parede.

## O que é igual ao cenário real de cada ano

| Elemento | Fonte |
|---|---|
| Dias, áreas de cada dia e ordem no caderno | `cronograma.json` (conferido nos rodapés dos cadernos oficiais) |
| Duração oficial de cada dia | `cronograma.json`: 4h30 / 5h30 até 2016; 5h30 / 4h30 em 2017; 5h30 / 5h a partir de 2018 |
| Questões e texto | cadernos oficiais do INEP (PDF), com figuras e fórmulas descritas por um modelo de visão |
| Ordem das questões em cada cor de caderno | `ITENS_PROVA` (todas as cores regulares, sorteadas por candidato) |
| Língua estrangeira | inglês por padrão (`--lingua espanhol` ou `sorteio`) |
| Correção | só depois do dia inteiro; antes do 2º dia o agente confere o gabarito do 1º |

Duas correções que saíram desse trabalho:
- **2009**: o 1º dia começava por CN (questões 1-45) e só depois CH. O `dataset.py` supunha CH antes; o arquivo corrigido vai junto.
- **2010**: o "gabarito" oficial é o caderno com a alternativa circulada. O leitor reconhece o círculo e acertou 41 de 41 questões conferíveis.

## O relógio

O relógio é virtual: o tempo que o computador leva não conta. Cada ação custa um tempo declarado:

- **resolver** = (palavras ÷ 200 por minuto + tempo de resolução da área) × ritmo do candidato
  - resolução: LC 1,2 min, CH 1,4 min, CN 2,4 min, MT 2,8 min (`--resolucao`)
  - ritmo: sorteado por candidato, lognormal com desvio 0,25 (`--dispersao`). Uns são mais rápidos, outros mais lentos, como numa sala de prova.
- **chutar**: desligado por padrão (`--chute nao`). No piloto v1.2 o qwen3 chutava sem relação com o tempo (6% com folga, 0% no aperto) nem com a dificuldade (chutava as mais fáceis): era ruído, não estratégia, e o DeepSeek nunca chutava. Sem a opção, todos os cérebros têm as mesmas ações (resolver ou pular) e o chute real do fim da prova fica com o tempo esgotado. `--chute sim` religa (letra sorteada, 0,5 min)
- **pular** = 30% da leitura; a questão volta no fim se sobrar tempo
- no dia da redação, 60 min ficam reservados para ela (`--redacao-min`)

Antes de cada questão o agente vê o tempo restante, quantas questões faltam e o ritmo necessário para terminar. Decidir chutar é escolha dele.

**Tempo esgotado:** as questões que faltam viram chute (`--esgotado chute`, padrão, porque no ENEM não há desconto por erro) ou branco (`--esgotado branco`).

Com esses parâmetros, um candidato de ritmo mediano usa:
- 85% a 97% do tempo nos dias até 2016;
- cerca de 72% no 1º dia a partir de 2017;
- 109% no 2º dia de 2017;
- 96% a 101% no 2º dia de 2018 em diante.

O 2º dia de 2017 é o único em que o relógio não fecha. Isso confere com a história: foi por falta de tempo que o INEP acrescentou 30 minutos às provas de exatas em 2018.

Os parâmetros são declarados, não medidos. Por isso entram na análise de sensibilidade: rode também com `--wpm 150` e `--wpm 250`.

## Memória do agente durante o dia

- `completa`: o agente vê todo o caderno do dia até ali. É o mais fiel. Precisa de contexto grande, uns 30 mil tokens no fim do dia. É o padrão para as APIs.
- `janela:6`: o agente vê só as 6 questões anteriores. É o padrão nos modelos locais, porque 12 GB de VRAM não comportam o dia inteiro.
- `nenhuma`: cada questão é isolada e só o relógio liga uma à outra.

Atenção: um LLM não cansa como um adolescente. Se o acerto cair ao longo do caderno, o efeito é de contexto longo, não de fadiga biológica. O paralelo com o artigo é de **efeito de posição**, não de mecanismo.

## Passo a passo (Windows, na pasta do ENEMWise)

```powershell
# 1. preparar: texto (PDF), figuras e fórmulas (visão local), cadernos de todas as cores (ITENS_PROVA)
powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa preparar -Microdados "D:\microdados"
# 2. piloto: 3 candidatos em 2009 e 2023, para medir tempo e custo
powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa piloto -Cerebros "qwen3:8b" -Apis "deepseek:deepseek-flash"
# 3. completo: 20 candidatos por edição, 2009-2025, e a análise por área
powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa completo -Cerebros "qwen3:8b" -Apis "deepseek:deepseek-flash"
```

`provas-inep\` fica na raiz do repositório, com os PDFs baixados por `baixar-provas-enem.ps1`. Se parar no meio, rode o mesmo comando: ele retoma do que já está salvo. Isso vale para a visão (cache) e para a prova (por candidato e dia).

### O que cada etapa produz

| Arquivo | Conteúdo |
|---|---|
| `dados\provas-inep.jsonl`, `-espanhol.jsonl` | 3.060 + 80 questões, com gabarito oficial e a lista do que precisa de visão |
| `dados\recortes\` | imagem de cada questão com figura ou fórmula |
| `dados\provas-inep-visao.jsonl` | o mesmo, com figuras descritas e fórmulas transcritas |
| `dados\cadernos.json` | ordem de cada cor de caderno, parâmetros TRI, itens anulados |
| `agentes\saida\prova-<cérebro>-<rodada>\RESUMO.md` | acerto, nota, chutes, tempo usado e quem estourou o tempo, por ano e área |
| `...\ANALISE.md` e `analise-celulas.csv` | inclinação de posição dentro do item e γ do AFM, por área, ao lado dos candidatos reais |
| `...\longo\<ano>_<AREA>.csv` | formato longo do v9.2 (uid, co_item, correct, nota, co_prova, posicao, resposta + extras) |

O texto extraído também serve ao app. Para isso, inclua `dados\provas-inep-visao.jsonl` como última fonte em `enemwise batch --questoes ...`. As fontes atuais continuam com prioridade, e o PDF preenche as edições que faltavam: 2018 a 2021, 2025 e as lacunas das demais.

### Estado do texto (antes da visão)

- 3.060 de 3.060 questões separadas, todas com gabarito oficial.
- 2.851 têm as cinco alternativas em texto.
- 1.159 pedem visão, por um ou mais destes motivos:
  - figura: 560;
  - gráfico: 303;
  - fórmula achatada: 428;
  - alternativas em imagem: 133;
  - alternativas não achadas: 209;
  - fonte sem tabela de caracteres, ilegível: 10.
- As fontes cifradas de 2017 e 2018 foram decodificadas.

## Análise completa (o que cada rodada produz e o que fecha cada categoria)

| Arquivo / etapa | O que mede | Tipo de avaliação |
|---|---|---|
| `ANALISE.md` | inclinação de posição dentro do item e γ do AFM por área, com IC por bootstrap de candidatos e teste de γ por bootstrap paramétrico (γ = 0) | simulação (C) |
| `KT.md` | 3PL INEP (teto), 3PL + posição, Elo-3PL, dificuldade dos itens para os agentes, + posição, PFA e BKT; AUC e log-loss em validação cruzada por candidato; p̂(T) do BKT por célula; γ de acertos e erros do PFA | preditiva (A) |
| `-Etapa real` → seção "Agentes × candidatos" | acerto por item (agente × candidato real) e inclinação dos candidatos com o MESMO estimador, a partir da exportação v9.2 (`-LongoConfig`) ou dos microdados (`-Microdados`, sem LC) | psicométrica (B) |
| `-Etapa nulo` | candidatos gerados pela TRI do INEP: sem ordem (nulo) e com efeito conhecido de −0,01 logit por posição (teste de poder) | simulação, categoria 1 |
| `-Persona habilidades` | cada candidato-agente com um perfil (θ ~ N(0,1); domina cada habilidade com P = logística de 1,7(θ − b̄)); seção "Fidelidade da persona" | simulação, categoria 4 |

Ordem sugerida, depois da rodada completa:
```powershell
powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa nulo
powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa real -LongoConfig pipeline\v92.json
powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa analisar -Rodada completo-v13 -Cerebros nenhum -Apis "deepseek:deepseek-flash"
powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa completo -Rodada persona-v14 -Memoria nenhuma -Persona habilidades -Cerebros nenhum -Apis "deepseek:deepseek-flash"
```

O que o nulo já mostrou (teste com 20 candidatos por edição, 17 edições):
- **sem efeito:** inclinações entre −0,02 e +0,06 pp/pos, todos os IC cruzam zero; γ do AFM não significativo (p 0,47–0,73).
- **com −0,01 logit/pos:** LC −0,150 pp/pos (IC −0,169 a −0,020), CH −0,095, CN −0,039, MT −0,044. O efeito de LC nos candidatos reais (−0,151) equivale a ~0,01 logit por posição, e 20 candidatos por edição bastam para vê-lo.
- **PFA tem aprendizagem fantasma até no nulo:** γ de acertos +0,31 a +0,52 (LC, CH, CN) e ganho de AUC de +0,008 a +0,017 sobre a dificuldade do item, sem aprendizagem nenhuma — ele confunde habilidade do candidato com aprendizagem. O BKT fica com p̂(T) mediano 0–0,02, mas 4 a 8 das 17 células passam de 0,05 por acaso. É o mesmo fenômeno do laboratório, agora num nulo puramente psicométrico.
- Correção feita ao testar: o AFM usava ridge 1,0, que encolhia o θ do aluno e empurrava γ para −0,3 no nulo; agora usa 0,01 (viés ≈ −0,03, absorvido pelo teste por bootstrap).

## Simulado no app (estudantes fazendo a mesma prova)

A aba **Simulado** do ENEMWise aplica a estudantes exatamente o que os agentes fazem: mesma edição, dia, cor de caderno, ordem
impressa, texto (com a descrição das figuras quando a questão não está no banco com imagem), gabarito e duração oficial
(com 60 min reservados para a redação, desligável). Navegação livre como no papel, cartão-resposta, "marcar para revisar",
relógio que segue correndo com a aba fechada; ao fim do tempo, o que não foi marcado vale como em branco. O resultado traz
acertos e nota estimada (EAP do 3PL do INEP) por área, o gabarito com o tempo em cada questão, a exportação em CSV no
formato longo (uid, ano, dia, cor, co_prova, posicao, co_item, area, habilidade, resposta, gabarito, correct, tempo_s,
visitas), comparável às saídas dos agentes, e a opção de contar as respostas no treino adaptativo.

Os dados do app saem dos mesmos arquivos dos agentes:

    python tools/modo-prova/exportar_web.py      # dados/cadernos.json + provas-inep*-visao.jsonl -> web/public/data/prova/

## Tabela 1 e Zenodo

    powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa zenodo            # análises de todas as rodadas, Tabela 1 e pacote em zenodo\
    powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa subir -Sandbox    # teste no sandbox.zenodo.org
    powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa subir             # rascunho no Zenodo (não publica)

O pacote traz as rodadas completas (agentes, aleatório, nulos, persona) e o painel do jogo, os cadernos, o acerto real por item ×
posição, o código no commit (git archive), o ambiente (pacotes, modelos do Ollama com digest, GPU) e os SHA-256. A publicação, que
gera o DOI e não pode ser desfeita, é feita na página do rascunho, depois de revisar autores, licença (dados CC BY 4.0) e descrição.

## Custo e tempo (estimativa; o piloto mede de verdade)

- **Visão local (qwen2.5vl:7b, 12 GB):** 1.177 questões a ~20-40 s cada, ou seja, 7 a 13 h, uma vez só.
- **DeepSeek, memória completa:** cada candidato faz ~180 chamadas. Como a memória cresce, a entrada é quase toda repetida e cai no cache.
  - 20 candidatos × 17 edições custam algo entre **US$ 5 e 15** fora do horário de pico, em 3 a 5 h com 8 chamadas em paralelo.
  - Confira o preço na página da DeepSeek antes de rodar.
- **Local (8B, janela de 6):** ~3 s por chamada, cerca de 9 min por candidato.
  - 20 × 17 = **~50 h**. Com 10 candidatos, ~25 h; com `--memoria nenhuma`, ~17 h.

## Quantos candidatos bastam (poder)

A inclinação por posição dos candidatos reais vai de −0,15 (LC) a −0,02 (CN) pontos percentuais por posição. Com agentes, o ruído por célula é grande (teste nulo: ±0,2 pp com 40 candidatos numa edição). Somando as 17 edições, o desvio do agregado fica perto de 0,03 pp com 20 candidatos por edição. Isso basta para ver um efeito do tamanho do de LC, mas não um do tamanho do de CN, que pediria uns 200 por edição.

Analogia: é como medir a inclinação de uma rua com uma régua curta. Em LC a ladeira é visível; em CN ela some no tremor da mão.

## Limites

- **O agente não volta atrás:** ele pode pular e responder no fim, mas não revisa o que já marcou.
- **A visão pode errar uma fórmula:** a descrição nunca indica a resposta, mas a transcrição de matemática merece uma amostra conferida à mão (`visao-cache.jsonl` guarda o original).
- **A nota é estimada:** é o EAP do 3PL com os parâmetros do INEP (D = 1,7, escala 500 + 100θ). Fica próxima da nota oficial, mas não é ela.
- **A redação não é simulada:** só o tempo dela é descontado.
