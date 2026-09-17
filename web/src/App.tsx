import { useEffect, useMemo, useRef, useState } from 'react'
import { Conta, ConfirmarVinculo, type StatusSync } from './components/Conta'
import { loadBundle } from './data'
import { makeBank, newStudent } from './kt/engine'
import { setD } from './kt/irt'
import { mesclar, precisaConfirmarVinculo } from './kt/sincronia'
import type { StudentState } from './kt/types'
import {
  aoMudarSessao, apagarProgressoNuvem, baixarProgresso, entrarComEmail, entrarComGoogle, enviarProgresso, nuvemDisponivel, sair,
  type Usuario,
} from './nuvem'
import { Inicio } from './pages/Inicio'
import { Mapa } from './pages/Mapa'
import { Professor } from './pages/Professor'
import { Treinar } from './pages/Treinar'
import { loadStudent, saveStudent } from './store'

type Tab = 'treinar' | 'mapa' | 'professor'
const TABS: [Tab, string][] = [['treinar', 'Treinar'], ['mapa', 'Meu retorno'], ['professor', 'Professor']]
const fromHash = (): Tab => (TABS.find(([t]) => `#${t}` === location.hash)?.[0] ?? 'treinar')

export default function App() {
  const [bundle, setBundle] = useState<Awaited<ReturnType<typeof loadBundle>> | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>(fromHash)
  const [student, setStudent] = useState<StudentState | null>(loadStudent)
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [status, setStatus] = useState<StatusSync>('local')
  const [pendente, setPendente] = useState<{ usuario: Usuario; remoto: StudentState | null } | null>(null)
  const envio = useRef<number | undefined>(undefined)
  const ultimoUsuario = useRef<string | null>(null)

  useEffect(() => { loadBundle().then((b) => { setD(b.meta.D); setBundle(b) }).catch((e) => setErro(String(e.message ?? e))) }, [])
  useEffect(() => { const f = () => setTab(fromHash()); addEventListener('hashchange', f); return () => removeEventListener('hashchange', f) }, [])
  const bank = useMemo(() => (bundle ? makeBank(bundle.items, bundle.priors, bundle.meta.bandas) : null), [bundle])

  const salvarLocal = (s: StudentState | null) => { setStudent(s); saveStudent(s) }

  async function enviarMesclado(u: Usuario, estado: StudentState) {
    if (!bank) return
    setStatus('sincronizando')
    try {
      const remoto = await baixarProgresso(u.id)                 // outro aparelho pode ter treinado nesse meio tempo
      const m = { ...mesclar(bank, estado, remoto)!, dono: u.id }
      await enviarProgresso(u.id, m)
      setStudent((atual) => { const x = atual ? { ...mesclar(bank, atual, m)!, dono: u.id } : m; saveStudent(x); return x })
      setStatus('sincronizado')
    } catch {
      setStatus('offline')
    }
  }

  // Sessão: ao entrar, junta o progresso da nuvem com o deste aparelho
  useEffect(() => {
    if (!nuvemDisponivel || !bank) return
    let cancelar = () => {}
    let ativo = true
    const aoEntrar = async (u: Usuario | null) => {
      if (!ativo) return
      setUsuario(u)
      if (!u) { ultimoUsuario.current = null; setStatus('local'); return }
      if (ultimoUsuario.current === u.id) return                   // renovação de token: nada a fazer
      ultimoUsuario.current = u.id
      setStatus('sincronizando')
      try {
        const remoto = await baixarProgresso(u.id)
        const local = loadStudent()
        if (precisaConfirmarVinculo(local, u.id)) { setPendente({ usuario: u, remoto }); setStatus('sincronizado'); return }
        const m = mesclar(bank, local?.dono === u.id ? local : null, remoto)
        const final = m ? { ...m, dono: u.id } : null
        salvarLocal(final)
        if (final) await enviarProgresso(u.id, final)
        setStatus('sincronizado')
      } catch {
        setStatus('offline')
      }
    }
    // o Supabase recomenda não chamar o cliente dentro do callback: adia para fora dele
    aoMudarSessao((u) => { setTimeout(() => aoEntrar(u), 0) }).then((f) => { cancelar = f })
    return () => { ativo = false; cancelar() }
  }, [bank]) // eslint-disable-line react-hooks/exhaustive-deps

  const update = (s: StudentState | null) => {
    const comDono = s && usuario ? { ...s, dono: usuario.id } : s
    salvarLocal(comDono)
    if (usuario && comDono) {
      window.clearTimeout(envio.current)
      setStatus('sincronizando')
      envio.current = window.setTimeout(() => enviarMesclado(usuario, comDono), 1500)
    }
  }

  return (
    <div className="app">
      <header className="topo">
        <a className="marca" href="#treinar">ENEM<span>Wise</span></a>
        <nav aria-label="Seções">
          {TABS.map(([t, label]) => (
            <a key={t} href={`#${t}`} aria-current={tab === t ? 'page' : undefined}>{label}</a>
          ))}
          {nuvemDisponivel && (
            <Conta usuario={usuario} status={status} onEntrar={entrarComEmail} onEntrarGoogle={entrarComGoogle}
              onSair={async (apagarLocal) => {
                await sair()
                if (apagarLocal) salvarLocal(null)
              }}
              onApagarNuvem={async () => { if (usuario) { await apagarProgressoNuvem(usuario.id); setStatus('local') } }} />
          )}
        </nav>
      </header>
      {pendente && student && bank && (
        <ConfirmarVinculo nome={student.nome} n={student.tentativas.length}
          onJuntar={() => {
            const m = { ...mesclar(bank, student, pendente.remoto)!, dono: pendente.usuario.id }
            salvarLocal(m); setPendente(null); enviarMesclado(pendente.usuario, m)
          }}
          onDescartar={() => {
            salvarLocal(pendente.remoto ? { ...pendente.remoto, dono: pendente.usuario.id } : null); setPendente(null)
          }} />
      )}
      {bundle?.meta.sintetico && (
        <p className="aviso">Demonstração com questões sintéticas. Gere o banco real rodando o pipeline sobre os microdados do INEP.</p>
      )}
      <main>
        {erro && <section className="folha"><h2>O banco de questões não carregou.</h2><p>{erro}</p></section>}
        {!erro && (!bundle || !bank) && <p className="carregando">Carregando banco de questões…</p>}
        {bundle && bank && tab === 'professor' && <Professor bank={bank} meta={bundle.meta} descricoes={bundle.descricoes} bloom={bundle.bloom} />}
        {bundle && bank && tab !== 'professor' && !student && !pendente && (
          <Inicio bandas={bundle.meta.bandas} onStart={(nome, banda) => update({ ...newStudent(bank, nome, banda), atualizadoEm: Date.now() })} />
        )}
        {bundle && bank && student && tab === 'treinar' && <Treinar bank={bank} meta={bundle.meta} student={student} onChange={update} />}
        {bundle && bank && student && tab === 'mapa' && (
          <Mapa bank={bank} meta={bundle.meta} student={student} descricoes={bundle.descricoes} bloom={bundle.bloom} onChange={update} onReset={() => update(null)} />
        )}
      </main>
      <footer className="rodape">
        <p>{bundle?.meta.fonte}{bundle ? `, edições ${bundle.meta.edicoes[0]} a ${bundle.meta.edicoes.at(-1)}` : ''}. Software livre sob GPL-3.0.</p>
      </footer>
    </div>
  )
}
