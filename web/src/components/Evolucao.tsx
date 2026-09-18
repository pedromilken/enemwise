import { useState } from 'react'
import type { Bank } from '../kt/engine'
import { evolucao, novoResultado, trajetoria } from '../kt/evolucao'
import { META_PADRAO } from '../kt/feedback'
import { type Area, AREAS, type Meta, type StudentState } from '../kt/types'

const fmtData = (d: string) => { const [a, m, dia] = d.split('-'); return `${dia}/${m}/${a}` }

/**
 * Gráfico no tempo: linha cinza = estimativa da plataforma dia a dia; pontos azuis = resultados
 * registrados; losango = estimativa de agora; tracejado = meta.
 */
function Sparkline({ pontos, traj, estimativa, meta }: {
  pontos: { data: string; nota: number }[]; traj: { data: string; nota: number }[]; estimativa: number | null; meta: number
}) {
  const todos = [...pontos, ...traj]
  if (!todos.length) return null
  const dias = (d: string) => Date.parse(d) / 86_400_000
  const d0 = Math.min(...todos.map((p) => dias(p.data))), d1 = Math.max(...todos.map((p) => dias(p.data)), dias(new Date().toISOString().slice(0, 10)))
  const valores = [...todos.map((p) => p.nota), ...(estimativa !== null ? [estimativa] : []), meta]
  const lo = Math.min(...valores) - 30, hi = Math.max(...valores) + 30
  const W = 260, H = 60
  const x = (d: string) => 10 + (d1 > d0 ? ((dias(d) - d0) / (d1 - d0)) * (W - 20) : (W - 20) / 2)
  const y = (v: number) => H - 8 - ((v - lo) / (hi - lo)) * (H - 16)
  const hoje = new Date().toISOString().slice(0, 10)
  return (
    <svg className="evolucao-svg" viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label="Evolução da nota no tempo">
      <line x1={4} x2={W - 4} y1={y(meta)} y2={y(meta)} stroke="currentColor" strokeDasharray="3 3" opacity=".45" />
      {traj.length > 1 && <polyline points={traj.map((p) => `${x(p.data)},${y(p.nota)}`).join(' ')} fill="none" stroke="currentColor" strokeWidth="1.5" opacity=".5" />}
      {pontos.map((p, i) => <circle key={i} cx={x(p.data)} cy={y(p.nota)} r="3.5" fill="var(--azul)" />)}
      {estimativa !== null && <path d={`M${x(hoje)},${y(estimativa) - 5} l5,5 l-5,5 l-5,-5 z`} fill="var(--tinta)" />}
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
      <p className="fineprint">A linha cinza é a estimativa da plataforma ao longo dos dias de treino; os pontos azuis, notas do Enem ou de simulados que você registrar; o losango, a estimativa de hoje; o tracejado, a sua meta de {alvo}.</p>
      {ev.some((a) => a.pontos.length || a.estimativa !== null) && (
        <table className="tabela-risco">
          <thead><tr><th>Área</th><th>Registrado</th><th>Estimativa atual</th><th>Variação</th><th>No tempo</th></tr></thead>
          <tbody>{ev.filter((a) => a.pontos.length || a.estimativa !== null).map((a) => (
            <tr key={a.area}>
              <td>{meta.areas[a.area]}</td>
              <td>{a.ultimo ? `${a.ultimo.nota} (${a.ultimo.origem}, ${fmtData(a.ultimo.data)})` : <small>nenhum ainda</small>}</td>
              <td>{a.estimativa ?? <small>responda mais questões</small>}</td>
              <td>{a.variacao === null ? '—' : <span className={a.variacao >= 0 ? 'faixa ok' : 'faixa risco'}>{a.variacao > 0 ? '+' : ''}{a.variacao}</span>}</td>
              <td><Sparkline pontos={a.pontos} traj={trajetoria(student, bank, a.area)} estimativa={a.estimativa} meta={alvo} /></td>
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
