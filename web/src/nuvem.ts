/**
 * Login opcional e cópia do progresso na nuvem (Supabase).
 *
 * Sem VITE_SUPABASE_URL e VITE_SUPABASE_ANON_KEY no build, o app segue 100% local e o
 * botão de entrar não aparece. A chave "anon" é pública por desenho: quem protege os
 * dados é a política RLS da tabela (cada usuário só lê e grava a própria linha).
 */
import type { SupabaseClient } from '@supabase/supabase-js'
import type { StudentState } from './kt/types'

const URL = import.meta.env.VITE_SUPABASE_URL as string | undefined
const KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined
export const nuvemDisponivel = Boolean(URL && KEY)
/** Só mostra o botão do Google se o provedor estiver mesmo ligado no Supabase (VITE_LOGIN_GOOGLE=1). */
export const googleDisponivel = nuvemDisponivel && import.meta.env.VITE_LOGIN_GOOGLE === '1'

let clienteP: Promise<SupabaseClient> | null = null
function cliente(): Promise<SupabaseClient> {
  if (!nuvemDisponivel) return Promise.reject(new Error('Login não configurado neste site.'))
  clienteP ??= import('@supabase/supabase-js').then(({ createClient }) =>
    createClient(URL!, KEY!, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'pkce' } }))
  return clienteP
}

export interface Usuario { id: string; email: string }

export async function usuarioAtual(): Promise<Usuario | null> {
  const { data } = await (await cliente()).auth.getSession()
  const u = data.session?.user
  return u ? { id: u.id, email: u.email ?? '' } : null
}

export async function aoMudarSessao(cb: (u: Usuario | null) => void): Promise<() => void> {
  const { data } = (await cliente()).auth.onAuthStateChange((_evento, sessao) => {
    const u = sessao?.user
    cb(u ? { id: u.id, email: u.email ?? '' } : null)
  })
  return () => data.subscription.unsubscribe()
}

export async function entrarComEmail(email: string) {
  const { error } = await (await cliente()).auth.signInWithOtp({
    email, options: { emailRedirectTo: `${location.origin}${import.meta.env.BASE_URL}` },
  })
  if (error) throw new Error(error.message)
}

/** Mensagens do Supabase vêm em inglês; as mais comuns viram texto claro em português. */
export function mensagemErro(e: unknown): string {
  const m = e instanceof Error ? e.message : String(e)
  if (/Invalid login credentials/i.test(m)) return 'E-mail ou senha incorretos.'
  if (/User already registered|already been registered/i.test(m)) return 'Já existe uma conta com esse e-mail. Entre com a sua senha.'
  if (/Password should be at least (\d+)/i.test(m)) return `A senha precisa ter pelo menos ${m.match(/at least (\d+)/i)![1]} caracteres.`
  if (/Email not confirmed/i.test(m)) return 'Confirme o e-mail pelo link que enviamos e tente de novo.'
  if (/Unable to validate email address|invalid format/i.test(m)) return 'E-mail em formato inválido.'
  if (/rate limit|too many requests/i.test(m)) return 'Muitas tentativas seguidas. Espere alguns minutos.'
  if (/Unsupported provider|provider is not enabled/i.test(m)) return 'Entrada pelo Google ainda não está ligada neste site.'
  if (/fetch|network/i.test(m)) return 'Sem conexão com o servidor.'
  return m
}

export async function entrarComSenha(email: string, senha: string) {
  const { error } = await (await cliente()).auth.signInWithPassword({ email, password: senha })
  if (error) throw new Error(error.message)
}

/** Retorna true quando o Supabase exige confirmação por e-mail antes da primeira entrada. */
export async function criarConta(email: string, senha: string): Promise<boolean> {
  const { data, error } = await (await cliente()).auth.signUp({
    email, password: senha, options: { emailRedirectTo: `${location.origin}${import.meta.env.BASE_URL}` },
  })
  if (error) throw new Error(error.message)
  return !data.session
}

export async function definirSenha(nova: string) {
  const { error } = await (await cliente()).auth.updateUser({ password: nova })
  if (error) throw new Error(error.message)
}

export async function entrarComGoogle() {
  const { error } = await (await cliente()).auth.signInWithOAuth({
    provider: 'google', options: { redirectTo: `${location.origin}${import.meta.env.BASE_URL}` },
  })
  if (error) throw new Error(error.message)
}

export async function sair() {
  await (await cliente()).auth.signOut()
}

export async function baixarProgresso(userId: string): Promise<StudentState | null> {
  const { data, error } = await (await cliente()).from('progresso').select('estado').eq('user_id', userId).maybeSingle()
  if (error) throw new Error(error.message)
  return (data?.estado as StudentState | undefined) ?? null
}

export async function enviarProgresso(userId: string, estado: StudentState) {
  const { error } = await (await cliente()).from('progresso')
    .upsert({ user_id: userId, estado, atualizado_em: new Date().toISOString() })
  if (error) throw new Error(error.message)
}

export async function apagarProgressoNuvem(userId: string) {
  const { error } = await (await cliente()).from('progresso').delete().eq('user_id', userId)
  if (error) throw new Error(error.message)
}
