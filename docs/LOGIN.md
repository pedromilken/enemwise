# Login e progresso na nuvem

O login é **opcional**. Sem configurar nada, o ENEMWise funciona como antes: o progresso fica no navegador.
Com o login ligado, o estudante entra por um link enviado ao e-mail (sem senha) e continua o treino em qualquer aparelho.

---

## Como funciona

- **Supabase** cuida da autenticação e guarda uma linha por usuário na tabela `progresso`.
- **O site continua estático** no GitHub Pages. A chave pública do Supabase vai no build; quem protege os dados é a política RLS, que só deixa cada pessoa ler e gravar a própria linha.
- **Nada se perde entre aparelhos.** As tentativas são somadas, nunca sobrescritas, e o domínio é recalculado repassando todas em ordem.
- **Computador compartilhado.** Se o aparelho tiver progresso de outra pessoa, o app pergunta antes de juntar. "Sair e apagar deste aparelho" limpa o navegador.

---

## Configurar (uma vez)

1. Crie um projeto gratuito em **supabase.com**.
2. Em **SQL Editor**, rode o arquivo [`supabase/progresso.sql`](../supabase/progresso.sql).
3. Em **Authentication → URL Configuration**:
   - **Site URL:** `https://pedromilken.github.io/enemwise/`
   - **Redirect URLs:** adicione `https://pedromilken.github.io/enemwise/` e, para testar localmente, `http://localhost:5173/`
4. Em **Project Settings → API**, copie a **Project URL** e a chave **anon / publishable**. Nunca use a `service_role`.
5. No GitHub, em **Settings → Secrets and variables → Actions → Variables**, crie:
   - `SUPABASE_URL` com a Project URL
   - `SUPABASE_ANON_KEY` com a chave anon / publishable
6. Em **Actions**, rode de novo **"Publicar no GitHub Pages"**. O botão **Entrar** aparece no topo.

Para testar localmente, crie `web/.env.local` com `VITE_SUPABASE_URL=...` e `VITE_SUPABASE_ANON_KEY=...`.

---

## Antes de usar com turmas

- **E-mail.** O envio padrão do Supabase tem limite baixo de mensagens por hora e serve para testes. Para uma turma entrando ao mesmo tempo, configure um SMTP próprio em **Authentication → SMTP**.
- **Plano gratuito.** Projetos sem uso por um período podem ser pausados. Reative pelo painel.
- **LGPD e menores de idade.** O app guarda só e-mail e progresso de treino e oferece "apagar meus dados da nuvem". Para estudantes menores de 18 anos, obtenha a autorização dos responsáveis (por exemplo, pela escola). Apagar a conta de autenticação em si é feito pelo administrador no painel do Supabase.
