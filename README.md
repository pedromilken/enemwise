# ENEMWise

Treino adaptativo para o ENEM com **knowledge tracing** calibrado nos microdados do INEP.
Para estudantes: escolhe a próxima questão pelo que ainda falta dominar. Para professores:
mostra quais habilidades da Matriz de Referência mais pedem aula na turma.

Roda inteiro no navegador e é publicado no **GitHub Pages**. Sem servidor, sem banco de dados, sem dados pessoais trafegando.

---

## Como funciona

**Cozinha central e marmita.** O trabalho pesado (milhões de linhas de microdados) acontece uma vez, na
sua máquina, no `pipeline/`. Ele entrega "marmitas" JSON pequenas em `web/public/data/`. O app só
esquenta: atualiza o modelo a cada resposta, em milissegundos, no próprio navegador.

```
MICRODADOS_ENEM + ITENS_PROVA ──► pipeline (Python) ──► items.json   (TRI a,b,c + habilidade + texto)
maritaca-ai/enem (enunciados) ──┘                   ├─► priors.json  (P(L0), guess, slip por habilidade × faixa)
                                                     └─► meta.json
                                                              │
                                                     web (React, estático, GitHub Pages)
                                                       ├─ BKT por habilidade (guess por item = parâmetro c)
                                                       ├─ θ por área via EAP no 3PL
                                                       └─ política: habilidade mais frágil → item mais informativo
```

### Decisão central de modelagem

**O ENEM é uma fotografia, não um filme.** Mostra onde cada faixa de nota está em cada habilidade,
mas não há aprendizagem entre uma questão e a próxima. Por isso:

| Parâmetro | Origem | Por quê |
|---|---|---|
| P(L0) | microdados, por habilidade × faixa de nota | a fotografia sustenta o "ponto de partida" |
| guess | parâmetro **c** da TRI de cada item | acertar uma questão "chutável" pesa menos |
| slip | erro da faixa mais alta na habilidade | proxy de descuido de quem domina |
| P(T) | valor padrão (0,12) | **não identificável** no ENEM; reajustar com logs de uso do ENEMWise |

Nenhuma habilidade começa consolidada (teto de 0,85 no prior): consolidação exige evidência do próprio estudante.

### O vínculo com o texto das questões

Os microdados não trazem enunciado. O `link_text.py` casa `CO_ITEM` com o dataset
[maritaca-ai/enem](https://huggingface.co/datasets/maritaca-ai/enem) (2022–2024) usando a
**sequência de gabaritos como impressão digital do caderno**: 45 letras por área identificam a cor
da prova sem precisar supor qual foi usada. O relatório de casamento sai em `meta.json`.

---

## Dataset de Knowledge Tracing

Os microdados também saem como dataset de KT: parquet longo, folds por participante, `data.txt` validado com o leitor do pyKT, datasheet e benchmark com teste de falsificação. Detalhes e cuidados em [`docs/DATASET.md`](docs/DATASET.md). Resumo: **ordem é posição no caderno, não tempo, e não há aprendizagem entre questões**, então o dataset funciona como controle nulo.

## Fundamentação pedagógica e estatística

Detalhes em [`docs/FUNDAMENTACAO.md`](docs/FUNDAMENTACAO.md).

- **Estudante**: retorno em três perguntas (Hattie & Timperley), risco por área com incerteza e autoavaliação de confiança como medida indireta.
- **Professor**: ciclo meta, evidências e ação (Walvoord), planilha para contato (SPPA), questões para revisar e domínio por nível de Bloom.
- **Pesquisa**: previsão registrada antes de cada resposta; `enemwise avaliar` calcula métricas prequenciais e o módulo `estatistica` cobre qui-quadrado com Bonferroni, Welch com g de Hedges e pareamento por propensão sem reposição. Os testes reproduzem os números do SPPA.

## Rodar localmente

No Windows, siga [`docs/WINDOWS.md`](docs/WINDOWS.md).

```bash
# app com a demo sintética já incluída
cd web && npm install && npm run dev

# pipeline e testes
cd pipeline && pip install -e ".[dev]" && pytest -q
```

## Gerar o banco real (2009–2025)

Passo a passo completo em [`docs/RODAR-TODAS-AS-EDICOES.md`](docs/RODAR-TODAS-AS-EDICOES.md). Em resumo:

```bash
enemwise baixar --anos 2009-2025 --destino /dados/inep   # manifesto + checagem das correções do INEP
enemwise batch --raiz /dados/inep --anos 2009-2025 \
  --questoes textos/maritaca_2022.jsonl textos/maritaca_2023.jsonl textos/maritaca_2024.jsonl textos/enem_challenge.jsonl \
  --long-dir /dados/long --jobs 3 --out out
enemwise merge --entrada out --web ../web/public/data
```

- **Priors** usam todas as edições, somando contagens. `p_l0_sd` mostra a variação entre edições.
- **Auditoria automática** por edição e área: correlação entre acerto empírico e parâmetro b, e fração de itens no nível do acaso. Célula reprovada fica fora dos priors.
- **Banco praticável** depende de texto aberto: 2022–2024 completos, 2009–2017 parciais (sem questões com imagem). As demais edições entram só na calibração.
- Os JSON gerados são **agregados por faixa**, sem registro individual.

## Publicar

1. Crie o repositório e envie o código para `main`.
2. Em *Settings → Pages*, escolha **GitHub Actions** como fonte.
3. O workflow `pages.yml` compila e publica em `https://<usuario>.github.io/<repo>/`.

## Tutor com IA (opcional)

Modo "traga sua chave": o estudante cola a chave da API no painel e ela fica só no `sessionStorage`
da aba. Sem chave, a dica elimina uma alternativa errada. Para uso em sala, o caminho seguro é um
proxy serverless próprio (fora do escopo do Pages).

## Pontos a verificar antes do banco real

- **Constante D do 3PL** (`--D`, padrão 1,0): conferir contra a fórmula que você usou para replicar as notas.
- **Aliases de colunas** (`schema.RESP_ALIASES`): edições antigas usam outros nomes; o erro diz qual falta.
- **Direitos dos textos**: o dataset é Apache-2.0, mas os enunciados citam obras de terceiros. Avalie servir via download no build em vez de versionar.

## Roadmap

- [ ] Ajustar P(T) com os logs de uso (exportações) e comparar BKT, PFA e DKT offline
- [ ] Texto de 2018–2021 e 2025 extraído dos PDFs que vêm no zip do INEP, vinculado pela mesma impressão digital
- [ ] Descrições oficiais das 120 habilidades, com nível de Bloom revisado
- [ ] Simulado somativo cronometrado por área
- [ ] Revisão espaçada das questões erradas
- [ ] Proxy opcional para o tutor em turmas

## Créditos e licença

Arquitetura inspirada no [pianoKT](https://github.com/chilltse/pianokt). Código sob GPL-3.0-or-later.

**Dados**
- Microdados do Enem, INEP (dados abertos).
- Alinhamento das respostas certificado contra o gabarito impresso: pipeline `enem_kt_confounds` v9.2, DOI [10.5281/zenodo.22166455](https://doi.org/10.5281/zenodo.22166455).
- Enunciados de 2022 a 2024: [maritaca-ai/enem](https://huggingface.co/datasets/maritaca-ai/enem) (Apache-2.0; Pires et al., 2023, arXiv:2311.14169).
- Enunciados de 2009 a 2017: ENEM Challenge (Silveira & Mauá, BRACIS 2017), via [eduagarcia/enem_challenge](https://huggingface.co/datasets/eduagarcia/enem_challenge).

As questões do Enem são documentos públicos do INEP, mas os textos de apoio citam obras de terceiros.
