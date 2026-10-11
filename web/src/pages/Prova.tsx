import { useEffect, useMemo, useRef, useState } from 'react'
import { type Bank, record } from '../kt/engine'
import { type Area, AREAS, type Item, type StudentState } from '../kt/types'
import {
  carregarEdicao, carregarIndice, type DiaProva, type EdicaoProva, fmtTempo, gravarSessoes, type IndiceProva, type ItemCaderno,
  itensDoCaderno, lerSessoes, notaEAP, type Sessao,
} from '../prova'
import { downloadTexto } from '../store'

const NOME_AREA: Record<Area, string> = { LC: 'Linguagens', CH: 'Ciências Humanas', CN: 'Ciências da Natureza', MT: 'Matemática' }
const corLimpa = (c: string) => c.replace(/^CADERNO\s*/i, '').toLowerCase().replace(/^./, (x) => x.toUpperCase())

/** Texto da questão: o do banco (com as figuras) quando existe; senão o do caderno, com a descrição das figuras no lugar delas. */
function Questao({ item, texto, banco }: { item: ItemCaderno; texto?: { enunciado: string; alternativas: string[]; descricao: string[] }; banco?: Item }) {
  const enun = banco?.enunciado ?? texto?.enunciado ?? ''
  const figs = banco?.figuras ?? []
  const desc = banco?.descricao ?? texto?.descricao ?? []
  const partes = enun.split('[[placeholder]]')
  return (
    <div className="enunciado">
      {partes.map((p, i) => (
        <div key={i}>
          {p.split(/\n|(?=##)/).filter(Boolean).map((l, j) =>
            l.startsWith('#') ? <p key={j} className="enun-titulo">{l.replace(/^#+\s*/, '')}</p> : <p key={j}>{l}</p>)}
          {i < partes.length - 1 && (figs[i]
            ? <figure><img src={figs[i]} alt={desc[i] ?? 'Figura da questão'} loading="lazy" /></figure>
            : desc[i] ? <figure className="fig-descrita"><figcaption>Figura: {desc[i]}</figcaption></figure> : null)}
        </div>
      ))}
      {partes.length === 1 && desc.length > 0 && !figs.length && (
        <figure className="fig-descrita"><figcaption>{desc.map((d, i) => <span key={i}>Figura: {d} </span>)}</figcaption></figure>
      )}
      {item.anulado && <p className="aviso">Questão anulada pelo INEP: não conta na nota.</p>}
    </div>
  )
}

export function Prova({ bank, student, onChange }: { bank: Bank; student: StudentState | null; onChange: (s: StudentState) => void }) {
  const [indice, setIndice] = useState<IndiceProva | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [sessoes, setSessoes] = useState<Sessao[]>(lerSessoes)
  const [abertaId, setAbertaId] = useState<string | null>(() => lerSessoes().find((s) => s.entregue === null)?.id ?? null)
  useEffect(() => { carregarIndice().then(setIndice).catch((e) => setErro(String(e.message ?? e))) }, [])

  const salvar = (f: (xs: Sessao[]) => Sessao[]) => setSessoes((xs) => { const n = f(xs); gravarSessoes(n); return n })
  const aberta = sessoes.find((s) => s.id === abertaId) ?? null

  if (erro) return <section className="folha"><h2>Simulado indisponível</h2><p>{erro}</p></section>
  if (!indice) return <p className="carregando">Carregando provas…</p>
  if (aberta) return <EmProva key={aberta.id} sessao={aberta} bank={bank} student={student} onChange={onChange}
    atualizar={(s) => salvar((xs) => xs.map((x) => (x.id === s.id ? s : x)))}
    fechar={() => setAbertaId(null)}
    descartar={() => { salvar((xs) => xs.filter((x) => x.id !== aberta.id)); setAbertaId(null) }} />
  return <Escolher indice={indice} sessoes={sessoes} abrir={setAbertaId}
    iniciar={(s) => { salvar((xs) => [...xs, s]); setAbertaId(s.id) }}
    descartar={(id) => salvar((xs) => xs.filter((x) => x.id !== id))} />
}

function Escolher({ indice, sessoes, iniciar, abrir, descartar }: {
  indice: IndiceProva; sessoes: Sessao[]; iniciar: (s: Sessao) => void; abrir: (id: string) => void; descartar: (id: string) => void
}) {
  const anos = indice.anos.map((a) => a.ano).sort((a, b) => b - a)
  const [ano, setAno] = useState(anos[0])
  const dias = indice.anos.find((a) => a.ano === ano)?.dias ?? []
  const [diaN, setDiaN] = useState(1)
  const dia: DiaProva | undefined = dias.find((d) => d.dia === diaN) ?? dias[0]
  const [cor, setCor] = useState('sortear')
  const [lingua, setLingua] = useState<'ingles' | 'espanhol'>('ingles')
  const [redacao, setRedacao] = useState(true)
  const reserva = dia?.redacao && redacao ? 60 : 0

  function comecar() {
    if (!dia) return
    const cores = dia.cores ?? []
    const c = cor === 'sortear' || !cores.includes(cor) ? cores[Math.floor(Math.random() * cores.length)] : cor
    const agora = Date.now()
    iniciar({
      id: `${ano}-${dia.dia}-${agora}`, ano, dia: dia.dia, cor: c, lingua, reservaRedacao: reserva, inicio: agora,
      limite: agora + (dia.duracao_min - reserva) * 60000, atual: 0, respostas: {}, revisar: [], tempoMs: {}, visitas: { 0: 1 }, entregue: null,
    })
  }

  return (
    <section className="folha prova-escolha">
      <h1 className="display small">Simulado do ENEM</h1>
      <p className="lede">
        A 1ª etapa como foi aplicada: o caderno de uma cor, na ordem impressa, com a duração oficial do dia.
        O gabarito só aparece quando você entrega ou o tempo acaba. As mesmas provas são feitas pelos agentes do ENEMWise.
      </p>
      <div className="prova-campos">
        <label>Edição
          <select value={ano} onChange={(e) => { setAno(Number(e.target.value)); setDiaN(1); setCor('sortear') }}>
            {anos.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
        <label>Dia
          <select value={dia?.dia ?? 1} onChange={(e) => { setDiaN(Number(e.target.value)); setCor('sortear') }}>
            {dias.map((d) => <option key={d.dia} value={d.dia}>{d.dia}º dia: {d.areas.join(' + ')}{d.redacao ? ' + redação' : ''}</option>)}
          </select>
        </label>
        <label>Caderno
          <select value={cor} onChange={(e) => setCor(e.target.value)}>
            <option value="sortear">Sortear (como na sala)</option>
            {(dia?.cores ?? []).map((c) => <option key={c} value={c}>{corLimpa(c)}</option>)}
          </select>
        </label>
        {dia?.areas.includes('LC') && (
          <label>Língua estrangeira
            <select value={lingua} onChange={(e) => setLingua(e.target.value as 'ingles' | 'espanhol')}>
              <option value="ingles">Inglês</option><option value="espanhol">Espanhol</option>
            </select>
          </label>
        )}
      </div>
      {dia?.redacao && (
        <label className="prova-check">
          <input type="checkbox" checked={redacao} onChange={(e) => setRedacao(e.target.checked)} />
          Reservar 60 min para a redação (o tempo das questões fica {fmtTempo((dia.duracao_min - 60) * 60000)})
        </label>
      )}
      {dia && <p>Tempo de prova: <strong>{fmtTempo((dia.duracao_min - reserva) * 60000)}</strong> (oficial: {fmtTempo(dia.duracao_min * 60000)}{dia.redacao ? ', com a redação' : ''}).</p>}
      <button className="btn primary" onClick={comecar} disabled={!dia}>Começar a prova</button>
      <p className="fineprint">O relógio corre mesmo com a aba fechada, como na sala. Questão sem marcação conta como em branco.</p>

      {sessoes.length > 0 && (
        <>
          <h2>Suas provas</h2>
          <table className="tabela-risco">
            <thead><tr><th>Edição</th><th>Dia</th><th>Caderno</th><th>Situação</th><th /></tr></thead>
            <tbody>
              {[...sessoes].reverse().map((s) => (
                <tr key={s.id}>
                  <td>{s.ano}</td><td>{s.dia}º</td><td>{corLimpa(s.cor)}</td>
                  <td>{s.entregue === null ? 'em andamento' : `entregue em ${new Date(s.entregue).toLocaleDateString('pt-BR')}`}</td>
                  <td>
                    <button className="btn" onClick={() => abrir(s.id)}>{s.entregue === null ? 'Continuar' : 'Ver resultado'}</button>{' '}
                    <button className="btn" onClick={() => { if (confirm('Apagar esta prova?')) descartar(s.id) }}>Apagar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}

function EmProva({ sessao: s, bank, student, onChange, atualizar, fechar, descartar }: {
  sessao: Sessao; bank: Bank; student: StudentState | null; onChange: (s: StudentState) => void
  atualizar: (s: Sessao) => void; fechar: () => void; descartar: () => void
}) {
  const [ed, setEd] = useState<EdicaoProva | null>(null)
  const [agora, setAgora] = useState(Date.now())
  const abertoDesde = useRef(Date.now())
  useEffect(() => { carregarEdicao(s.ano).then(setEd) }, [s.ano])
  useEffect(() => { if (s.entregue !== null) return; const t = setInterval(() => setAgora(Date.now()), 1000); return () => clearInterval(t) }, [s.entregue])
  const itens = useMemo(() => (ed ? itensDoCaderno(ed, s) : []), [ed, s.dia, s.cor, s.lingua]) // eslint-disable-line react-hooks/exhaustive-deps

  // tempo com a questão aberta, somado ao trocar de questão ou entregar
  const comTempo = (x: Sessao): Sessao => {
    const dt = Math.max(0, Math.min(Date.now(), x.limite) - abertoDesde.current)
    abertoDesde.current = Date.now()
    return { ...x, tempoMs: { ...x.tempoMs, [x.atual]: (x.tempoMs[x.atual] ?? 0) + dt } }
  }
  const ir = (i: number) => {
    if (i < 0 || i >= itens.length || i === s.atual) return
    const x = comTempo(s)
    atualizar({ ...x, atual: i, visitas: { ...x.visitas, [i]: (x.visitas[i] ?? 0) + 1 } })
    scrollTo({ top: 0 })
  }
  const entregar = (motivo: 'entregou' | 'tempo') => {
    const x = s.entregue === null ? comTempo(s) : s
    atualizar({ ...x, entregue: motivo === 'tempo' ? x.limite : Date.now(), motivo })
  }
  useEffect(() => { if (s.entregue === null && agora >= s.limite) entregar('tempo') }) // eslint-disable-line react-hooks/exhaustive-deps

  if (!ed) return <p className="carregando">Carregando o caderno…</p>
  if (!itens.length) return <section className="folha"><p>Caderno não encontrado nesta edição.</p><button className="btn" onClick={descartar}>Voltar</button></section>
  if (s.entregue !== null) return <Resultado s={s} itens={itens} bank={bank} student={student} onChange={onChange} atualizar={atualizar} fechar={fechar} />

  const it = itens[s.atual]
  const texto = ed.itens[String(it.co_item)]
  const banco = bank.byId.get(`${s.ano}-${it.co_item}`)
  const alts = banco?.alternativas ?? texto?.alternativas ?? []
  const resta = s.limite - agora
  const feitas = Object.keys(s.respostas).length
  const decorrido = agora - s.inicio
  const total = s.limite - s.inicio
  const ritmo = feitas ? decorrido / feitas : 0
  const marcarRevisar = () => atualizar({ ...s, revisar: s.revisar.includes(s.atual) ? s.revisar.filter((k) => k !== s.atual) : [...s.revisar, s.atual] })

  return (
    <section className="prova">
      <div className={`prova-relogio ${resta < 15 * 60000 ? 'urgente' : ''}`} role="timer" aria-live="off">
        <strong>{fmtTempo(resta)}</strong>
        <span>{feitas}/{itens.length} marcadas</span>
        <span>{ritmo ? `${fmtTempo(ritmo)} por questão (ideal ${fmtTempo(total / itens.length)})` : ''}</span>
        <button className="btn" onClick={fechar}>Pausar a tela</button>
        <button className="btn primary" onClick={() => { if (confirm(`Entregar a prova? ${itens.length - feitas} questões em branco.`)) entregar('entregou') }}>Entregar</button>
      </div>
      <div className="prova-grid">
        <div className="folha">
          <div className="questao-head">
            <span className="chip">Questão {it.pos}</span>
            <span className="chip">{NOME_AREA[it.area]}</span>
            {it.lingua && <span className="chip">{it.lingua === 'ingles' ? 'Inglês' : 'Espanhol'}</span>}
          </div>
          {texto || banco ? <Questao item={it} texto={texto} banco={banco} /> : <p className="aviso">Texto desta questão indisponível.</p>}
          <ol className="alternativas">
            {alts.map((alt, i) => {
              const l = 'ABCDE'[i]
              const marcada = s.respostas[s.atual] === l
              return (
                <li key={l}>
                  <button className={`alt ${marcada ? 'marcada' : ''}`} aria-pressed={marcada}
                    onClick={() => {
                      const r = { ...s.respostas }
                      if (marcada) delete r[s.atual]; else r[s.atual] = l
                      atualizar({ ...s, respostas: r })
                    }}>
                    <span className="alt-letra">{l}</span><span>{alt}</span>
                  </button>
                </li>
              )
            })}
          </ol>
          <div className="acoes">
            <button className="btn" onClick={() => ir(s.atual - 1)} disabled={s.atual === 0}>Anterior</button>
            <button className="btn" onClick={marcarRevisar}>{s.revisar.includes(s.atual) ? 'Desmarcar revisão' : 'Marcar para revisar'}</button>
            <button className="btn primary" onClick={() => ir(s.atual + 1)} disabled={s.atual === itens.length - 1}>Próxima</button>
          </div>
          <p className="fineprint">Clique de novo na alternativa marcada para apagá-la.</p>
        </div>
        <aside className="folha cartao-resposta" aria-label="Cartão-resposta">
          <h3>Cartão-resposta</h3>
          <div className="cartao-grade">
            {itens.map((x, i) => (
              <button key={i} onClick={() => ir(i)} aria-current={i === s.atual ? 'true' : undefined}
                className={`${s.respostas[i] ? 'feita' : ''} ${s.revisar.includes(i) ? 'revisar' : ''}`}
                title={`${x.pos} (${x.area})${s.respostas[i] ? `: ${s.respostas[i]}` : ''}`}>
                {x.pos}<small>{s.respostas[i] ?? ''}</small>
              </button>
            ))}
          </div>
          <p className="fineprint">Azul: marcada. Amarelo: para revisar.</p>
        </aside>
      </div>
    </section>
  )
}

function Resultado({ s, itens, bank, student, onChange, atualizar, fechar }: {
  s: Sessao; itens: ItemCaderno[]; bank: Bank; student: StudentState | null
  onChange: (s: StudentState) => void; atualizar: (s: Sessao) => void; fechar: () => void
}) {
  const linhas = itens.map((it, i) => {
    const r = s.respostas[i] ?? ''
    return { i, it, r, correta: it.anulado || it.gab === 'X' ? null : r ? r === it.gab : false }
  })
  const areas = AREAS.filter((a) => itens.some((x) => x.area === a))
  const porArea = areas.map((a) => {
    const L = linhas.filter((l) => l.it.area === a)
    const val = L.filter((l) => l.correta !== null)
    return { a, n: val.length, acertos: val.filter((l) => l.correta).length, branco: L.filter((l) => !l.r).length,
      nota: notaEAP(val.map((l) => ({ a: l.it.a, b: l.it.b, c: l.it.c, correta: l.correta }))) }
  })
  const noBanco = linhas.filter((l) => l.r && bank.byId.has(`${s.ano}-${l.it.co_item}`))

  function exportar() {
    const cab = 'uid,ano,dia,cor,co_prova,posicao,co_item,area,habilidade,resposta,gabarito,correct,tempo_s,visitas'
    const uid = s.id
    const corpo = linhas.map((l) => [uid, s.ano, s.dia, corLimpa(s.cor), l.it.co_prova, l.it.pos, l.it.co_item, l.it.area, l.it.hab ?? '',
      l.r, l.it.gab, l.correta === null ? '' : Number(l.correta), ((s.tempoMs[l.i] ?? 0) / 1000).toFixed(1), (s.visitas[l.i] ?? 0)].join(','))
    downloadTexto(`simulado-${s.ano}-dia${s.dia}.csv`, [cab, ...corpo].join('\n'), 'text/csv')
  }
  function contar() {
    if (!student) return
    let st = student
    for (const l of noBanco) st = record(st, bank, bank.byId.get(`${s.ano}-${l.it.co_item}`)!, l.r, false)
    onChange(st)
    atualizar({ ...s, contouNoTreino: true })
  }

  return (
    <section className="folha prova-resultado">
      <h1 className="display small">ENEM {s.ano}, {s.dia}º dia ({corLimpa(s.cor)})</h1>
      <p className="lede">{s.motivo === 'tempo' ? 'O tempo acabou; o que ficou sem marcação contou como em branco.' : 'Prova entregue.'}{' '}
        Duração: {fmtTempo((s.entregue ?? s.limite) - s.inicio)} de {fmtTempo(s.limite - s.inicio)}.</p>
      <table className="tabela-risco">
        <thead><tr><th>Área</th><th>Acertos</th><th>Em branco</th><th>Nota estimada</th></tr></thead>
        <tbody>{porArea.map((p) => (
          <tr key={p.a}><td>{NOME_AREA[p.a]}</td><td>{p.acertos}/{p.n}</td><td>{p.branco}</td><td>{p.nota ?? '—'}</td></tr>
        ))}</tbody>
      </table>
      <p className="fineprint">Nota estimada pela TRI com os parâmetros do INEP (EAP, 500 + 100θ). Aproxima a nota oficial, que usa outra escala por edição; anuladas ficam de fora.</p>
      <div className="acoes">
        <button className="btn" onClick={exportar}>Exportar respostas (CSV)</button>
        {student && !s.contouNoTreino && noBanco.length > 0 && (
          <button className="btn primary" onClick={contar}>Contar {noBanco.length} respostas no meu treino</button>
        )}
        {s.contouNoTreino && <span className="chip">Contou no treino</span>}
        <button className="btn" onClick={fechar}>Voltar</button>
      </div>
      <h2>Gabarito</h2>
      <table className="tabela-risco prova-gabarito">
        <thead><tr><th>Questão</th><th>Área</th><th>Sua</th><th>Gabarito</th><th>Tempo</th><th /></tr></thead>
        <tbody>{linhas.map((l) => (
          <tr key={l.i} className={l.correta === null ? '' : l.correta ? 'certa' : 'errada'}>
            <td>{l.it.pos}</td><td>{l.it.area}</td><td>{l.r || '—'}</td><td>{l.it.anulado ? 'anulada' : l.it.gab}</td>
            <td>{fmtTempo(s.tempoMs[l.i] ?? 0)}</td>
            <td>{bank.byId.has(`${s.ano}-${l.it.co_item}`) && <a href={`#treinar?q=${s.ano}-${l.it.co_item}`}>rever</a>}</td>
          </tr>
        ))}</tbody>
      </table>
    </section>
  )
}
