# Endereço do site

Hoje o app está em `https://pedromilken.github.io/enemwise/`, endereço que o GitHub Pages impõe: usuário mais nome do repositório. Para ficar só **enemwise**, há três caminhos.

| Caminho | Endereço | Custo | Trabalho |
|---|---|---|---|
| **Vercel** (o mesmo do Piano KT) | `https://enemwise.vercel.app` | grátis | ligar o repositório, 5 minutos |
| **Domínio próprio** | `https://enemwise.com.br` | anuidade do registro.br | comprar o domínio e apontar o DNS |
| Continuar no Pages | `https://pedromilken.github.io/enemwise/` | grátis | nada |

Os três podem conviver: o Pages continua publicando a cada push, e a Vercel publica em paralelo.

---

## Vercel

1. Entre em **vercel.com** com a conta do GitHub.
2. **Add New → Project**, escolha o repositório `enemwise` e **Import**.
3. O `vercel.json` na raiz já define o build (`cd web && npm ci && npm run build`) e a pasta de saída (`web/dist`). Não é preciso ajustar nada.
4. Em **Environment Variables**, crie as mesmas três do GitHub, para Production e Preview:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
   - `VITE_LOGIN_GOOGLE` com valor `1`, quando o Google estiver ligado
5. **Deploy.** Em **Settings → Domains**, confirme que o domínio é `enemwise.vercel.app`; se estiver ocupado, escolha outro nome ali mesmo.

**Importante:** na Vercel o site fica na raiz (`/`), e não em `/enemwise/`. O build já cuida disso sozinho, porque o caminho base só é aplicado no workflow do GitHub Pages.

### Ajustar o login para o endereço novo

No Supabase, em **Authentication → URL Configuration**:
- **Site URL:** `https://enemwise.vercel.app`
- **Redirect URLs:** acrescente `https://enemwise.vercel.app` e mantenha `https://pedromilken.github.io/enemwise/`

**No Google Cloud não muda nada:** o redirecionamento aponta para o callback do Supabase, não para o site.

---

## Domínio próprio

1. Registre o domínio (por exemplo, `enemwise.com.br` no registro.br).
2. **Na Vercel:** Settings → Domains → adicione o domínio e siga as instruções de DNS.
   **No GitHub Pages:** Settings → Pages → Custom domain, e crie um arquivo `CNAME` na raiz do site com o domínio.
3. Atualize o Site URL e as Redirect URLs no Supabase.

---

## Celular

O app já funciona em qualquer navegador de celular: layout responsivo, teste feito em tela de 390 px respondendo questões e entrando na conta. O `manifest.webmanifest` permite ainda **adicionar à tela inicial**, abrindo o app em tela cheia, sem barra do navegador.
