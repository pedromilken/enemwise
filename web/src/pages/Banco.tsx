import { useMemo, useState } from 'react'
import type { Bank } from '../kt/engine'
import { type Area, AREAS, type Meta, nomeHabilidade, type StudentState } from '../kt/types'

const POR_PAGINA = 60

/** Banco de questões: tudo o que tem texto, para testar qualquer uma diretamente. */
export function Banco({ bank, meta, student }: { bank: Bank; meta: Meta; student: StudentState | null }) {
  const [area, setArea] = useState<Area | 'todas'>('todas')
  const [ano, setAno] = useState<number | null>(null)
  const [topico, setTopico] = useState<string | null>(null)
  const [busca, setBusca] = useState('')
  const [limite, setLimite] = useState(POR_PAGINA)
  const catalogo = meta.conteudos ?? []
  const nome = (id: string) => catalogo.find((c) => c.id === id)?.nome ?? id
  const feitas = useMemo(() => {
    const m = new Map<string, boolean>()
    for (const t of student?.tentativas ?? []) m.set(t.itemId, t.correta)
    return m
  }, [student])

  const lista = useMemo(() => {
    const q = busca.trim().toLowerCase()
    return bank.items
      .filter((i) => i.enunciado && (area === 'todas' || i.area === area) && (ano === null || i.ano === ano)
        && (topico === null || (i.topicos ?? []).includes(topico))
        && (!q || (i.enunciado ?? '').toLowerCase().includes(q) || (i.alternativas ?? []).some((a) => a.toLowerCase().includes(q))))
      .sort((a, b) => b.ano - a.ano || a.area.localeCompare(b.area) || (a.numero ?? 0) - (b.numero ?? 0))
  }, [bank, area, ano, topico, busca])

  const anos = [...new Set(bank.items.map((i) => i.ano))].sort((a, b) => b - a)
  const topicos = catalogo.filter((c) => area === 'todas' || c.area === area)

  return (
    <div className="banco">
      <div className="chips" role="group" aria-label="Filtros">
        <button className={area === 'todas' ? 'chip on' : 'chip'} onClick={() => { setArea('todas'); setTopico(null); setLimite(POR_PAGINA) }}>Todas as áreas</button>
        {AREAS.map((a) => (
          <button key={a} className={area === a ? 'chip on' : 'chip'} onClick={() => { setArea(a); setTopico(null); setLimite(POR_PAGINA) }}>{meta.areas[a]}</button>
        ))}
        <label className="edicao"><span className="sr-only">Edição</span>
          <select value={ano ?? ''} onChange={(e) => { setAno(e.target.value ? Number(e.target.value) : null); setLimite(POR_PAGINA) }}>
            <option value="">Todas as edições</option>
            {anos.map((a) => <option key={a} value={a}>ENEM {a}</option>)}
          </select>
        </label>
        {topicos.length > 0 && (
          <label className="edicao"><span className="sr-only">Conteúdo</span>
            <select value={topico ?? ''} onChange={(e) => { setTopico(e.target.value || null); setLimite(POR_PAGINA) }}>
              <option value="">Todos os conteúdos</option>
              {topicos.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          </label>
        )}
        <label className="edicao busca"><span className="sr-only">Buscar no enunciado</span>
          <input type="search" placeholder="Buscar no enunciado…" value={busca} onChange={(e) => { setBusca(e.target.value); setLimite(POR_PAGINA) }} />
        </label>
      </div>

      <p className="fineprint">{lista.length} de {bank.items.filter((i) => i.enunciado).length} questões com texto. Abrir uma questão aqui conta no seu treino como qualquer outra.</p>

      <div className="tabela-rolagem">
        <table className="tabela-risco banco-tabela">
          <thead><tr><th>Edição</th><th>Questão</th><th>Área e habilidade</th><th>Conteúdo</th><th>Início do enunciado</th><th></th></tr></thead>
          <tbody>{lista.slice(0, limite).map((i) => (
            <tr key={i.id} className={feitas.has(i.id) ? (feitas.get(i.id) ? 'feita ok' : 'feita erro') : ''}>
              <td>ENEM {i.ano}</td>
              <td>{i.numero ?? '—'}</td>
              <td>{meta.areas[i.area]}, {nomeHabilidade(i.habilidade)}</td>
              <td>{(i.topicos ?? []).map(nome).join(' · ') || <span className="dev-num">sem conteúdo</span>}</td>
              <td className="banco-trecho">{(i.enunciado ?? '').slice(0, 110)}…</td>
              <td><a className="chip" href={`#treinar?q=${i.id}`}>{feitas.has(i.id) ? 'Refazer' : 'Abrir'}</a></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {lista.length > limite && <button className="btn" onClick={() => setLimite(limite + POR_PAGINA)}>Mostrar mais {Math.min(POR_PAGINA, lista.length - limite)}</button>}
    </div>
  )
}
