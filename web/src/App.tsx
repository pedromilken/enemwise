import { useEffect, useMemo, useState } from 'react'
import { loadBundle } from './data'
import { makeBank, newStudent } from './kt/engine'
import { setD } from './kt/irt'
import type { StudentState } from './kt/types'
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

  useEffect(() => { loadBundle().then((b) => { setD(b.meta.D); setBundle(b) }).catch((e) => setErro(String(e.message ?? e))) }, [])
  useEffect(() => { const f = () => setTab(fromHash()); addEventListener('hashchange', f); return () => removeEventListener('hashchange', f) }, [])
  const bank = useMemo(() => (bundle ? makeBank(bundle.items, bundle.priors, bundle.meta.bandas) : null), [bundle])

  const update = (s: StudentState | null) => { setStudent(s); saveStudent(s) }

  return (
    <div className="app">
      <header className="topo">
        <a className="marca" href="#treinar">ENEM<span>Wise</span></a>
        <nav aria-label="Seções">
          {TABS.map(([t, label]) => (
            <a key={t} href={`#${t}`} aria-current={tab === t ? 'page' : undefined}>{label}</a>
          ))}
        </nav>
      </header>
      {bundle?.meta.sintetico && (
        <p className="aviso">Demonstração com questões sintéticas. Gere o banco real rodando o pipeline sobre os microdados do INEP.</p>
      )}
      <main>
        {erro && <section className="folha"><h2>O banco de questões não carregou.</h2><p>{erro}</p></section>}
        {!erro && (!bundle || !bank) && <p className="carregando">Carregando banco de questões…</p>}
        {bundle && bank && tab === 'professor' && <Professor bank={bank} meta={bundle.meta} descricoes={bundle.descricoes} bloom={bundle.bloom} />}
        {bundle && bank && tab !== 'professor' && !student && (
          <Inicio bandas={bundle.meta.bandas} onStart={(nome, banda) => update(newStudent(bank, nome, banda))} />
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
