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

## Duas formas de entrar

| | Entrar com o Google | Link no e-mail |
|---|---|---|
| Para o estudante | um toque, sem sair do site | precisa abrir o e-mail e voltar |
| Fila de turma | sem limite de envio | o envio padrão do Supabase é limitado por hora |
| Para você configurar | Google Cloud, cerca de 10 minutos | nada além do básico |
| Quem fica de fora | quem não tem conta Google | ninguém |

As duas convivem: com o Google ligado, o painel mostra o botão dele em cima e o campo de e-mail logo abaixo.

---

## Configuração básica (obrigatória)

1. Crie um projeto gratuito em **supabase.com**.
2. Em **SQL Editor**, rode o arquivo [`supabase/progresso.sql`](../supabase/progresso.sql). Confira depois:
   ```sql
   select tablename, rowsecurity from pg_tables where tablename = 'progresso';
   select policyname, cmd from pg_policies where tablename = 'progresso';
   ```
   O primeiro precisa dar `true`; o segundo, 4 políticas.
3. Em **Authentication → URL Configuration**:
   - **Site URL:** `https://pedromilken.github.io/enemwise/`
   - **Redirect URLs:** a mesma e, para testar local, `http://localhost:5173/`
4. Em **Project Settings → API keys**, copie a chave **anon** (ou **publishable**). Nunca a `service_role`.
5. No GitHub, em **Settings → Secrets and variables → Actions → Variables**, crie `SUPABASE_URL` e `SUPABASE_ANON_KEY`.
   Precisa ser em **Variables**, não em Secrets: o build injeta esses valores no site, e Secrets viriam vazios. A chave anon é pública por desenho; quem protege os dados são as políticas do passo 2.

## Entrar com o Google (recomendado para estudantes)

6. No **Google Cloud Console**, crie um projeto.
7. Configure a tela de consentimento (**Google Auth Platform**): tipo **External**, nome do app, e-mails de contato. Os escopos usados são só `email`, `profile` e `openid`, que não são sensíveis e não exigem revisão do Google.
8. **Publique o app.** Em modo de teste, só entram usuários cadastrados na lista de teste, no máximo 100.
9. Em **Credentials → Create credentials → OAuth client ID → Web application**, no campo **Authorized redirect URIs** cole exatamente o endereço que o Supabase mostra na tela do provedor Google:
   `https://SEU-PROJETO.supabase.co/auth/v1/callback`
10. Copie **Client ID** e **Client secret**.
11. No Supabase, em **Authentication → Sign In / Providers → Google**: ative, cole as duas credenciais e salve.
12. No GitHub, crie a variável `LOGIN_GOOGLE` com o valor `1`.
13. Em **Actions**, rode **"Publicar no GitHub Pages"**.

**Escolas com Google Workspace:** contas institucionais de estudante podem bloquear aplicativos de terceiros até o administrador liberar. Contas pessoais do Gmail entram normalmente, e o link por e-mail continua disponível para quem precisar.

---

## Antes de usar com turmas

- **E-mail.** O envio padrão do Supabase tem limite baixo de mensagens por hora e serve para testes. Para uma turma entrando ao mesmo tempo, configure um SMTP próprio em **Authentication → SMTP**.
- **Plano gratuito.** Projetos sem uso por um período podem ser pausados. Reative pelo painel.
- **LGPD e menores de idade.** O app guarda só e-mail e progresso de treino e oferece "apagar meus dados da nuvem". Para estudantes menores de 18 anos, obtenha a autorização dos responsáveis (por exemplo, pela escola). Apagar a conta de autenticação em si é feito pelo administrador no painel do Supabase.
