import { useState } from 'react'
import type { Usuario } from '../nuvem'

export type StatusSync = 'local' | 'sincronizando' | 'sincronizado' | 'offline'

const ROTULO: Record<StatusSync, string> = {
  local: 'Salvo neste aparelho', sincronizando: 'Salvando…', sincronizado: 'Salvo na sua conta', offline: 'Sem conexão: salvo neste aparelho',
}

export function Conta({ usuario, status, onEntrar, onSair, onApagarNuvem }: {
  usuario: Usuario | null
  status: StatusSync
  onEntrar: (email: string) => Promise<void>
  onSair: (apagarLocal: boolean) => void
  onApagarNuvem: () => void
}) {
  const [aberto, setAberto] = useState(false)
  const [email, setEmail] = useState('')
  const [enviado, setEnviado] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  return (
    <div className="conta">
      <button className="chip" aria-expanded={aberto} onClick={() => setAberto(!aberto)}>
        {usuario ? <span className={`ponto ${status}`} aria-hidden="true" /> : null}
        {usuario ? usuario.email.split('@')[0] : 'Entrar'}
      </button>
      {aberto && (
        <div className="conta-painel" role="dialog" aria-label="Conta">
          {!usuario ? (
            enviado ? (
              <p>Enviamos um link para <strong>{email}</strong>. Abra o e-mail neste aparelho e clique no link para entrar.</p>
            ) : (
              <form className="stack" onSubmit={async (e) => {
                e.preventDefault(); setErro(null)
                try { await onEntrar(email.trim()); setEnviado(true) } catch (x) { setErro(x instanceof Error ? x.message : 'Não foi possível enviar o link.') }
              }}>
                <label className="field"><span>Seu e-mail</span>
                  <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
                </label>
                <button className="btn primary" type="submit">Receber link de acesso</button>
                {erro && <p role="alert" className="erro">{erro}</p>}
                <small>
                  Sem senha: você entra pelo link enviado ao e-mail. Guardamos só o e-mail e o seu progresso de treino, para você
                  continuar em qualquer aparelho. Nada é compartilhado, e você pode apagar tudo quando quiser.
                  Menores de 18 anos devem usar com autorização de um responsável.
                </small>
              </form>
            )
          ) : (
            <div className="stack">
              <p><strong>{usuario.email}</strong><br /><small>{ROTULO[status]}</small></p>
              <button className="btn" onClick={() => { onSair(false); setAberto(false) }}>Sair</button>
              <button className="btn" onClick={() => { onSair(true); setAberto(false) }}>Sair e apagar deste aparelho</button>
              <small>Use a segunda opção em computadores compartilhados, como os da escola.</small>
              <button className="link" onClick={() => { if (confirm('Apagar seu progresso da nuvem? O que está neste aparelho continua.')) onApagarNuvem() }}>
                Apagar meus dados da nuvem
              </button>
            </div>
          )}
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
