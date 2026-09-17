import { useState } from 'react'
import { criarConta, entrarComEmail, entrarComGoogle, entrarComSenha, googleDisponivel, mensagemErro } from '../nuvem'

type Modo = 'entrar' | 'criar'

export function Entrar({ onPronto }: { onPronto: () => void }) {
  const [modo, setModo] = useState<Modo>('entrar')
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)

  async function enviar(e: React.FormEvent) {
    e.preventDefault()
    setErro(null); setAviso(null); setOcupado(true)
    try {
      if (modo === 'entrar') {
        await entrarComSenha(email.trim(), senha)
        onPronto()
      } else {
        const precisaConfirmar = await criarConta(email.trim(), senha)
        if (precisaConfirmar) setAviso(`Conta criada. Confirme pelo link enviado para ${email.trim()} e volte aqui para entrar.`)
        else onPronto()
      }
    } catch (x) {
      setErro(mensagemErro(x))
    } finally {
      setOcupado(false)
    }
  }

  async function porLink() {
    setErro(null); setAviso(null)
    if (!email.trim()) { setErro('Escreva o seu e-mail acima primeiro.'); return }
    try {
      await entrarComEmail(email.trim())
      setAviso(`Enviamos um link para ${email.trim()}. Abra o e-mail neste aparelho para entrar sem senha.`)
    } catch (x) { setErro(mensagemErro(x)) }
  }

  return (
    <section className="folha entrar">
      <h1 className="display small">{modo === 'entrar' ? 'Entrar' : 'Criar conta'}</h1>
      <p className="lede">
        Entrar guarda o seu treino na conta, para continuar no celular ou em outro computador.
        Sem conta, o progresso fica só neste navegador.
      </p>

      {googleDisponivel && (
        <>
          <button className="btn primary largo" disabled={ocupado} onClick={async () => {
            setErro(null)
            try { await entrarComGoogle() } catch (x) { setErro(mensagemErro(x)) }
          }}>Continuar com o Google</button>
          <p className="ou">ou use e-mail e senha</p>
        </>
      )}

      <form className="stack" onSubmit={enviar}>
        <label className="field"><span>E-mail</span>
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field"><span>Senha</span>
          <input type="password" required minLength={6} autoComplete={modo === 'entrar' ? 'current-password' : 'new-password'}
            value={senha} onChange={(e) => setSenha(e.target.value)} />
          <small>Pelo menos 6 caracteres.</small>
        </label>
        <button className={googleDisponivel ? 'btn largo' : 'btn primary largo'} type="submit" disabled={ocupado}>
          {ocupado ? 'Aguarde…' : modo === 'entrar' ? 'Entrar' : 'Criar conta'}
        </button>
        {erro && <p role="alert" className="erro">{erro}</p>}
        {aviso && <p role="status">{aviso}</p>}
      </form>

      <p className="entrar-links">
        {modo === 'entrar' ? (
          <>
            <button className="link" onClick={() => { setModo('criar'); setErro(null); setAviso(null) }}>Criar uma conta</button>
            <button className="link" onClick={porLink}>Esqueci a senha: entrar por link no e-mail</button>
          </>
        ) : (
          <button className="link" onClick={() => { setModo('entrar'); setErro(null); setAviso(null) }}>Já tenho conta</button>
        )}
        <a className="link" href="#treinar">Voltar ao treino</a>
      </p>

      <p className="fineprint">
        Guardamos só o e-mail e o seu progresso de treino. Nada é compartilhado, e você pode apagar tudo pelo menu da conta.
        Menores de 18 anos devem usar com autorização de um responsável.
      </p>
    </section>
  )
}
