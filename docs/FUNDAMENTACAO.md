# Fundamentação pedagógica e estatística

Como cada referência vira uma decisão concreta no ENEMWise, e o que a leitura crítica do
SPPA mudou no desenho da avaliação.

---

## 1. Das referências às funcionalidades

| Referência | Princípio usado | Onde está no ENEMWise |
|---|---|---|
| Cornell CTI, *Measuring student learning* | Avaliar responde a duas perguntas: como sei que a aprendizagem ocorreu e o que mudar no ensino | Retorno do estudante e painel do professor |
| Cornell CTI | Combinar medidas **diretas** e **indiretas** | Direta: acerto por habilidade. Indireta: autoavaliação de confiança após cada resposta |
| Cornell CTI | Combinar avaliação **formativa** e **somativa** | Formativa: treino com dica e retorno imediato. Somativa: simulado cronometrado (roadmap) |
| Cornell CTI | Cada avaliação alinhada a um resultado de aprendizagem | Cada questão já vem ligada a uma habilidade da Matriz de Referência (`CO_HABILIDADE`) |
| Cornell CTI | Medição sustentável em tempo e recursos | Correção automática; nada para o professor corrigir |
| Bloom et al. (1956) | Seis níveis cognitivos: Conhecimento, Compreensão, Aplicação, Análise, Síntese, Avaliação | `enemwise bloom` sugere o nível pelo verbo do descritor; painel mostra domínio por nível |
| Walvoord (2010) | Avaliação em três passos: metas, evidências, ação ("fechar o ciclo") | Painel do professor organizado como meta da turma, evidências e ações |
| Davis (2009) | Prática frequente de baixo risco com retorno rápido | Treino sem nota, retorno a cada questão |
| Alalawi et al. (2025), SPPA | Intervenção conduzida pelo docente, sem infraestrutura institucional | App estático no GitHub Pages; dados ficam no navegador |
| SPPA | Risco binário e faixa limítrofe após cada avaliação | Três faixas por área: meta provável, limítrofe, abaixo da meta provável |
| SPPA | Planilha para contato personalizado (mala direta) | "Baixar planilha para contato" |
| SPPA | Alinhamento construtivo para achar lacunas | Habilidade → questões → prioridades de estudo |
| SPPA | Fase de avaliação do curso: tarefas com desempenho ruim | "Questões para revisar": acerto da turma bem abaixo do previsto pela TRI |
| Hattie & Timperley (2007), via SPPA | Retorno em três perguntas | "Meu retorno": aonde quero chegar, como estou indo, qual o próximo passo |

Duas notas de cautela:

- **Bloom sugerido não é Bloom validado.** A heurística olha só o verbo inicial. Toda sugestão sai marcada para revisão humana, como no SPPA, onde o mapeamento é feito pelos docentes. A Matriz do ENEM já tem cinco eixos cognitivos próprios; Bloom complementa, não substitui.
- **Davis (2009) e Walvoord (2010) estão citados pelo princípio geral.** Confira as páginas no seu exemplar antes de citar no artigo.

---

## 2. Onde o ENEMWise difere do SPPA, e por quê

**Risco com incerteza, não só rótulo.** O SPPA treina cinco classificadores com notas de turmas anteriores. O ENEMWise usa a posterior do θ na TRI: P(nota < meta) = Φ((θ_meta − θ̂) / sd). Três consequências:

- a faixa vem com probabilidade e margem de erro;
- não precisa de histórico da turma, porque a calibração vem dos microdados do ENEM;
- com menos de 5 questões na área, **não há rótulo**. Sem esse piso, seria só o prior falando.

**Previsão registrada antes da resposta.** Cada tentativa guarda `pPrevisto`, `pLAntes` e `thetaAntes`. É como lacrar o palpite num envelope antes do jogo: dá para avaliar o modelo sem vazamento.

---

## 3. Leitura crítica do SPPA

Reproduzi as estatísticas publicadas. Os testes estão em `pipeline/tests/test_pedagogico.py` e rodam no CI.

| # | O que o artigo reporta | O que a reprodução mostra | Decisão no ENEMWise |
|---|---|---|---|
| 1 | RQ2: t(80,247) = 2,225, p = 0,029 | Só reproduz com **42 vs 46**, ou seja, **excluindo os desistentes** (15 e 9). Com 57 vs 55, o gl seria ~108 | Relatar sempre os dois recortes: intenção de tratar e concluintes |
| 2 | Média do controle: 32,64 (DP 16,21) no texto | A Tabela 5 traz **35,61 (DP 19,99)**. Com os valores da tabela: t(85,7) = 1,32, **p = 0,19**, g = 0,28 [−0,14; 0,70] | Uma única fonte para os descritivos, gerada pelo código |
| 3 | Desistência 26,5% vs 16,4%, não significativa | Desistir mais no grupo tratado tira possíveis reprovações do cálculo das médias entre concluintes | Desistência entra como desfecho, não como exclusão |
| 4 | RQ3: 248 controles pareados | A coorte de 2019 tinha **236** alunos. Houve pareamento com reposição, e o qui-quadrado tratou 496 observações como independentes | Pareamento sem reposição, caliper de 0,2 DP do logit (Austin, 2011), balanço por SMD < 0,1 |
| 5 | RQ1 binário: recall 0,986, precisão 0,877, acurácia 0,869 | Se "reprovado" (25%) fosse a classe positiva, esses recall e precisão implicariam acurácia ≈ 0,96. Com "aprovado" positivo, ≈ 0,89. Os números são compatíveis com **"aprovado" como positivo** | Métricas da classe de interesse (erro/risco), F1 macro, AUC, calibração |
| 6 | RQ1 multiclasse | Em 11 de 15 células, acurácia = recall, assinatura de média ponderada. Nas 4 restantes (KNN e uma de DT) os valores divergem, o que é internamente inconsistente, pois recall ponderado é sempre igual à acurácia | Idem; publicar a matriz de confusão |
| 7 | Acurácia 0,869 após a 1ª avaliação | A classe majoritária sozinha dá 0,746 | Toda métrica ao lado de linhas de base |
| 8 | Controle histórico (2019), com troca de docente | Os próprios autores reconhecem a troca; o efeito da intervenção se confunde com o do docente | Preferir controle concorrente: sorteio por turma ou entrada escalonada |
| 9 | Discussão: "34,6% maior aprovação" | É diferença em **pontos percentuais** (45,5 − 10,9) | Reportar p.p. e razão de chances |

Nada disso invalida a ideia do SPPA, que é boa e inspirou o painel. Mas o efeito publicado na RQ2 é **frágil**: depende de qual média de controle está certa e de excluir os desistentes.

---

## 4. Protocolo de avaliação proposto

| Questão | Pergunta | Dados | Análise | Ferramenta |
|---|---|---|---|---|
| **QA1** | O modelo prevê bem o próximo acerto e acha quem vai errar? | Exportações com `pPrevisto` | AUC, Brier, ECE, precisão/recall/F1 da classe "erro", contra prevalência e acerto da faixa | `enemwise avaliar` |
| **QA2** | A intervenção melhora quem estava em risco? | Simulado somativo antes/depois, desistência | Qui-quadrado + post hoc Bonferroni; Welch + g de Hedges nos dois recortes | `estatistica.qui_quadrado`, `comparar_medias` |
| **QA3** | Há efeito na turma inteira? | Idem, turma completa | Idem; propensão sem reposição se não houver sorteio | `estatistica.pareamento_propensao` |
| **QA4** | Como professores e estudantes percebem a ferramenta? | Entrevistas semiestruturadas | Análise temática (Braun & Clarke, 2006) | fora do app |

**QA1 não envolve intervenção** e pode rodar com logs pseudonimizados. **QA2 a QA4 envolvem pessoas**, muitas vezes menores de idade: exigem aprovação em CEP pela Plataforma Brasil, TCLE dos responsáveis e TALE dos estudantes. Pela LGPD, as exportações usam só o apelido escolhido e ficam no navegador até o próprio estudante enviar.

**Pré-registro recomendado** antes de coletar: hipóteses, desfecho primário, tratamento da desistência e correção para múltiplas comparações. É o que teria evitado as ambiguidades 1 a 3.

---

## Referências

- Alalawi, K., Athauda, R., Chiong, R., & Renner, I. (2025). Evaluating the student performance prediction and action framework through a learning analytics intervention study. *Education and Information Technologies, 30*, 2887–2916. https://doi.org/10.1007/s10639-024-12923-5
- Austin, P. C. (2011). An introduction to propensity score methods for reducing the effects of confounding in observational studies. *Multivariate Behavioral Research, 46*(3), 399–424.
- Bloom, B. S., Engelhart, M. D., Furst, E. J., Hill, W. H., & Krathwohl, D. R. (Eds.). (1956). *Taxonomy of educational objectives: The classification of educational goals*. Longmans, Green and Co.
- Braun, V., & Clarke, V. (2006). Using thematic analysis in psychology. *Qualitative Research in Psychology, 3*(2), 77–101.
- Center for Teaching Innovation, Cornell University. *Measuring student learning*. https://teaching.cornell.edu/teaching-resources/assessment-evaluation/measuring-student-learning
- Davis, B. G. (2009). *Tools for teaching* (2nd ed.). Jossey-Bass.
- Garcia-Perez, M. A., & Nunez-Anton, V. (2003). Cellwise residual analysis in two-way contingency tables. *Educational and Psychological Measurement, 63*(5), 825–839.
- Hattie, J., & Timperley, H. (2007). The power of feedback. *Review of Educational Research, 77*(1), 81–112.
- Walvoord, B. E. (2010). *Assessment clear and simple: A practical guide for institutions, departments, and general education* (2nd ed.). Jossey-Bass.


## Dicas em níveis e crédito parcial

Três níveis, do mais leve ao quase-resposta: o que a questão pede (conceito e conteúdo), o caminho (primeiro passo, ou uma alternativa eliminada), e a resolução quase completa (ou três alternativas eliminadas). Cada nível reduz o crédito do acerto para o BKT: 100%, 75%, 50% e 0%.

A atualização com crédito parcial é a mistura dos dois posteriores, "acertou" e "errou", pesada pelo crédito. É a forma mais simples de registrar "provavelmente sabia, mas não sozinho", sem inventar um parâmetro novo. Nível 3 vale como erro: quando a dica entrega quase tudo, o acerto não informa sobre o domínio. O nível fica gravado na tentativa (`nivelDica`), então os relatórios e o dataset de uso conseguem separar acertos plenos de acertos assistidos.


## Revisão espaçada por dificuldade percebida

Depois de responder, o estudante marca a questão como fácil, média ou difícil. Esse julgamento define quando ela volta: erro em 1 dia, difícil em 3, média em 7, fácil em 21; sem julgamento, 10. A política de seleção reserva cerca de um terço das escolhas para revisões vencidas, priorizando erros, depois difíceis, depois as mais atrasadas. Uma questão fácil quase não se repete porque já há domínio; a difícil volta cedo porque é onde a memória mais decai.

O julgamento de dificuldade também é uma medida de metacognição: cruzado com o acerto e com a chance prevista pela TRI, separa "difícil e errou" (lacuna real) de "difícil e acertou" (esforço produtivo) e de "fácil e errou" (desatenção ou concepção equivocada).

## Trajetória no tempo

Cada tentativa guarda o θ estimado antes da resposta. A trajetória diária da nota estimada sai desse registro sem recálculo, e é comparada aos resultados externos que o estudante registra (Enem anterior, simulados). A comparação vale como tendência: a estimativa mede domínio nas questões do app com dificuldade descontada; a nota real inclui tempo, cansaço e a prova inteira.
