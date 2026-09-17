# Conteúdos programáticos

A Matriz de Referência diz **que competência** a questão cobra. Ela não diz **sobre o que** a questão é:
"H8, resolver situação-problema de espaço e forma" cobre tanto área de triângulo quanto volume de cilindro.
Quem estuda precisa do conteúdo; quem ensina, dos dois.

O ENEMWise classifica cada questão com texto em um ou dois conteúdos, usados no filtro do treino, na devolutiva do
estudante e na visão do professor.

---

## Taxonomia

**46 conteúdos**, organizados por área e disciplina, em `pipeline/enemwise_pipeline/conteudos.py`:

| Área | Conteúdos |
|---|---|
| Matemática | números, porcentagem e financeira, razão e proporção, sequências, funções, equações e sistemas, geometria plana, geometria espacial, geometria analítica, trigonometria, estatística, probabilidade, análise combinatória |
| Linguagens | interpretação de texto, gêneros e mídias, variação linguística, gramática em uso, figuras e funções da linguagem, literatura, língua estrangeira, arte, práticas corporais |
| Ciências da Natureza | mecânica, calor e termodinâmica, ondas e óptica, eletricidade, estrutura da matéria, reações e estequiometria, soluções e ácido-base, termoquímica e eletroquímica, orgânica, célula, genética, evolução, ecologia, saúde |
| Ciências Humanas | Brasil colônia e império, Brasil república, história geral, cidadania e direitos, cultura e patrimônio, geografia física, população e cidades, economia e produção, cartografia, filosofia e sociologia |

**Fontes:** o anexo "Objetos de conhecimento associados às Matrizes de Referência" (INEP) e o programa do vestibular
da Fuvest, que detalha os mesmos objetos em itens finos, como a geometria analítica dentro da geometria.

## Como a classificação funciona

Cada conteúdo tem termos característicos e uma lista de habilidades típicas. O texto da questão, com as alternativas,
é comparado com esses termos; termos fortes valem o dobro e a habilidade da Matriz entra como reforço, nunca como
regra isolada. Acima de um limiar, a questão recebe até dois conteúdos.

**O que isso não é:** um classificador treinado. É uma heurística transparente, que qualquer pessoa pode auditar e
corrigir editando a lista de termos. Questões sem termo característico ficam **sem conteúdo**, de propósito, em vez de
receber um palpite.

**Cobertura medida nas 1.547 questões com texto:** 80% em Linguagens, Ciências da Natureza e Ciências Humanas, 69% em
Matemática, onde os enunciados são mais curtos e menos verbais. As demais aparecem no treino normalmente; só não entram
no filtro por conteúdo nem na tabela da devolutiva.

## Auditar e corrigir

```powershell
enemwise conteudos --entrada out
enemwise conteudos --entrada out --topico geometria-analitica --amostra 8
```

O primeiro mostra a cobertura por área e quantas questões caíram em cada conteúdo. O segundo lista exemplos, que é como
se descobre um termo mal escolhido.

**Para ajustar:** edite `TAXONOMIA` em `pipeline/enemwise_pipeline/conteudos.py`, acrescentando termos ao tópico, e rode
de novo `enemwise batch` e `enemwise merge`. Tópicos que costumam gerar falso positivo podem entrar em
`EXIGE_TERMO_FORTE`, como já acontece com geometria analítica.

## No app

- **Treinar:** um seletor de conteúdo ao lado do de edição, com a contagem de questões. Escolhido um conteúdo, o
  cabeçalho mostra de que área ele vem, e o domínio continua sendo medido por habilidade da Matriz.
- **Meu retorno:** tabela "Por conteúdo" com acertos, esperado, situação e as habilidades tocadas, da pior para a melhor.
  A partir de 4 questões o conteúdo recebe rótulo.
- **Professor:** os conteúdos em que a turma mais rende abaixo do esperado, ao lado da tabela por competência.
