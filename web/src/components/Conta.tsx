import { useState } from 'react'
import { definirSenha, mensagemErro } from '../nuvem'
import type { Usuario } from '../nuvem'

export type StatusSync = 'local' | 'sincronizando' | 'sincronizado' | 'offline'

const ROTULO: Record<StatusSync, string> = {
  local: 'Salvo neste aparelho', sincronizando: 'Salvando…', sincronizado: 'Salvo na sua conta', offline: 'Sem conexão: salvo neste aparelho',
}

export function Conta({ usuario, status, onSair, onApagarNuvem }: {
  usuario: Usuario | null
  status: StatusSync
  onSair: (apagarLocal: boolean) => void
  onApagarNuvem: () => void
}) {
  const [aberto, setAberto] = useState(false)
  const [trocando, setTrocando] = useState(false)
  const [senha, setSenha] = useState('')
  const [msg, setMsg] = useState<string | null>(null)

  if (!usuario) return <a className="chip" href="#entrar">Entrar</a>

  return (
    <div className="conta">
      <button className="chip" aria-expanded={aberto} onClick={() => setAberto(!aberto)}>
        <span className={`ponto ${status}`} aria-hidden="true" />
        {usuario.email.split('@')[0]}
      </button>
      {aberto && (
        <div className="conta-painel" role="dialog" aria-label="Conta">
          <div className="stack">
            <p><strong>{usuario.email}</strong><br /><small>{ROTULO[status]}</small></p>
            {trocando ? (
              <form className="stack" onSubmit={async (e) => {
                e.preventDefault(); setMsg(null)
                try { await definirSenha(senha); setMsg('Senha atualizada.'); setTrocando(false); setSenha('') }
                catch (x) { setMsg(mensagemErro(x)) }
              }}>
                <label className="field"><span>Nova senha</span>
                  <input type="password" required minLength={6} autoComplete="new-password" value={senha} onChange={(e) => setSenha(e.target.value)} />
                </label>
                <button className="btn" type="submit">Salvar senha</button>
              </form>
            ) : (
              <button className="btn" onClick={() => setTrocando(true)}>Trocar senha</button>
            )}
            {msg && <p role="status"><small>{msg}</small></p>}
            <button className="btn" onClick={() => { onSair(false); setAberto(false) }}>Sair</button>
            <button className="btn" onClick={() => { onSair(true); setAberto(false) }}>Sair e apagar deste aparelho</button>
            <small>Use a segunda opção em computadores compartilhados, como os da escola.</small>
            <button className="link" onClick={() => { if (confirm('Apagar seu progresso da nuvem? O que está neste aparelho continua.')) onApagarNuvem() }}>
              Apagar meus dados da nuvem
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export function ConfirmarVinculo({ nome, n, onJuntar, onDescartar }: { nome: string; n: number; onJuntar: () => void; onDescartar: () => void }) {
  return (
    <div className="aviso vinculo" role="alertdialog" aria-label="Progresso neste aparelho">
      <p>Este aparelho tem um progresso sem conta, de <strong>{nome}</strong>, com {n} questões. Ele é seu?</p>
      <div className="acoes">
        <button className="btn primary" onClick={onJuntar}>Sim, juntar à minha conta</button>
        <button className="btn" onClick={onDescartar}>Não, usar só o da minha conta</button>
      </div>
    </div>
  )
}
