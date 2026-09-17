# Do pianoKT ao ENEMWise

O que foi mantido, o que mudou e por quê.

| pianoKT | ENEMWise | Motivo |
|---|---|---|
| React Router 7 em modo SPA + Vite | React + Vite, navegação por hash | Pages não reescreve rotas; hash evita 404 ao recarregar |
| Supabase (auth, estado online) | `localStorage` + exportação JSON | Pages é estático; sem conta, sem dado pessoal em servidor |
| GCS + worker Python + Spark/Delta (bronze/silver/gold) | pipeline Python offline gerando JSON | o "lakehouse" vira um passo de build; volume por usuário é pequeno |
| Recomendação "demo black box" | BKT + TRI 3PL implementados e testados | o KT deixa de ser placeholder |
| Alinhamento de MIDI (desempenho × partitura) | alinhamento de cadernos (resposta × gabarito por posição) | mesmo problema estrutural: casar sequência observada com referência |
| Leaderboard de desafios | visão da turma por habilidade | foco pedagógico no professor, não em ranking |

## Unidade de conhecimento

- pianoKT: trecho musical / técnica
- ENEMWise: habilidade da Matriz de Referência (H1–H30 por área), já anotada pelo INEP em cada item (`CO_HABILIDADE`)

Essa anotação oficial é a grande vantagem do ENEM para KT: o mapa item → habilidade (a "matriz Q") vem pronto, sem rotulagem manual.
