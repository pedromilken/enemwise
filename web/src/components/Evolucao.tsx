import { useState } from 'react'
import type { Bank } from '../kt/engine'
import { evolucao, novoResultado } from '../kt/evolucao'
import { META_PADRAO } from '../kt/feedback'
import { type Area, AREAS, type Meta, type StudentState } from '../kt/types'

const fmtData = (d: string) => { const [a, m, dia] = d.split('-'); return `${dia}/${m}/${a}` }

/** Gráfico pequeno: resultados anteriores (pontos), estimativa atual (losango) e meta (linha tracejada). */
function Sparkline({ pontos, estimativa, meta }: { pontos: { nota: number }[]; estimativa: number | null; meta: number }) {
  const valores = [...pontos.map((p) => p.nota), ...(estimativa !== null ? [estimativa] : []), meta]
  if (valores.length < 2) return null
  const lo = Math.min(...valores) - 30, hi = Math.max(...valores) + 30
  const W = 220, H = 56, n = pontos.length + (estimativa !== null ? 1 : 0)
  const x = (i: number) => 12 + (n > 1 ? (i * (W - 24)) / (n - 1) : (W - 24) / 2)
  const y = (v: number) => H - 8 - ((v - lo) / (hi - lo)) * (H - 16)
  const serie = pontos.map((p, i) => [x(i), y(p.nota)] as const)
  const est = estimativa !== null ? ([x(n - 1), y(estimativa)] as const) : null
  const linha = [...serie, ...(est ? [est] : [])].map(([px, py]) => `${px},${py}`).join(' ')
  return (
    <svg className="evolucao-svg" viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label="Evolução da nota">
      <line x1={4} x2={W - 4} y1={y(meta)} y2={y(meta)} stroke="currentColor" strokeDasharray="3 3" opacity=".45" />
      {linha.includes(' ') && <polyline points={linha} fill="none" stroke="var(--azul)" strokeWidth="2" opacity=".7" />}
      {serie.map(([px, py], i) => <circle key={i} cx={px} cy={py} r="3.5" fill="var(--azul)" />)}
      {est && <path d={`M${est[0]},${est[1] - 5} l5,5 l-5,5 l-5,-5 z`} fill="var(--tinta)" />}
    </svg>
  )
}

export function Evolucao({ bank, meta, student, onChange }: { bank: Bank; meta: Meta; student: StudentState; onChange: (s: StudentState) => void }) {
  const [aberto, setAberto] = useState(false)
  const [data, setData] = useState(new Date().toISOString().slice(0, 10))
  const [origem, setOrigem] = useState('')
  const [notas, setNotas] = useState<Partial<Record<Area, string>>>({})
  const alvo = student.meta ?? META_PADRAO
  const ev = evolucao(student, bank)
  const historico = [...(student.historico ?? [])].sort((a, b) => b.data.localeCompare(a.data))

  function salvar(e: React.FormEvent) {
    e.preventDefault()
    const n: Partial<Record<Area, number>> = {}
    for (const a of AREAS) if (notas[a]) n[a] = Number(notas[a])
    if (!Object.keys(n).length) return
    onChange({ ...student, historico: [...(student.historico ?? []), novoResultado(data, origem, n)], atualizadoEm: Date.now() })
    setNotas({}); setOrigem(''); setAberto(false)
  }

  return (
    <div className="evolucao">
      <p className="fineprint">Registre notas do Enem ou de simulados para comparar com a estimativa da plataforma. O losango é a estimativa atual da plataforma; a linha tracejada, a sua meta de {alvo}.</p>
      {historico.length > 0 && (
        <table className="tabela-risco">
          <thead><tr><th>Área</th><th>Registrado</th><th>Estimativa atual</th><th>Variação</th><th></th></tr></thead>
          <tbody>{ev.filter((a) => a.pontos.length).map((a) => (
            <tr key={a.area}>
              <td>{meta.areas[a.area]}</td>
              <td>{a.ultimo ? `${a.ultimo.nota} (${a.ultimo.origem}, ${fmtData(a.ultimo.data)})` : '—'}</td>
              <td>{a.estimativa ?? <small>responda mais questões</small>}</td>
              <td>{a.variacao === null ? '—' : <span className={a.variacao >= 0 ? 'faixa ok' : 'faixa risco'}>{a.variacao > 0 ? '+' : ''}{a.variacao}</span>}</td>
              <td><Sparkline pontos={a.pontos} estimativa={a.estimativa} meta={alvo} /></td>
            </tr>
          ))}</tbody>
        </table>
      )}
      {!aberto ? (
        <button className="btn" onClick={() => setAberto(true)}>Registrar resultado</button>
      ) : (
        <form className="stack evolucao-form" onSubmit={salvar}>
          <div className="linha-campos">
            <label className="field"><span>Data</span><input type="date" required value={data} onChange={(e) => setData(e.target.value)} /></label>
            <label className="field"><span>Prova</span><input type="text" placeholder="ENEM 2025, simulado da escola…" value={origem} onChange={(e) => setOrigem(e.target.value)} list="origens" /></label>
            <datalist id="origens">{['ENEM 2025', 'ENEM 2024', 'Simulado da escola', 'Simulado do cursinho'].map((o) => <option key={o} value={o} />)}</datalist>
          </div>
          <div className="linha-campos">
            {AREAS.map((a) => (
              <label key={a} className="field"><span>{meta.areas[a]}</span>
                <input type="number" min={0} max={1000} step={1} placeholder="nota" value={notas[a] ?? ''} onChange={(e) => setNotas({ ...notas, [a]: e.target.value })} />
              </label>
            ))}
          </div>
          <small>Preencha só as áreas que tiver. Deixe em branco o que não fez.</small>
          <div className="acoes">
            <button className="btn primary" type="submit">Salvar</button>
            <button className="btn" type="button" onClick={() => setAberto(false)}>Cancelar</button>
          </div>
        </form>
      )}
      {historico.length > 0 && (
        <details className="evolucao-lista">
          <summary>Todos os registros ({historico.length})</summary>
          <ul>{historico.map((h) => (
            <li key={h.id}>{fmtData(h.data)}, {h.origem}: {AREAS.filter((a) => h.notas[a] !== undefined).map((a) => `${a} ${h.notas[a]}`).join(', ')}
              <button className="link" onClick={() => onChange({ ...student, historico: (student.historico ?? []).filter((x) => x.id !== h.id), atualizadoEm: Date.now() })}>remover</button>
            </li>
          ))}</ul>
        </details>
      )}
    </div>
  )
}
