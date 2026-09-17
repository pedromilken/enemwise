import { useEffect, useMemo, useState } from 'react'
import type { Bank } from '../kt/engine'
import { destaques, type EvidenciaHabilidade, evidencias, MIN_TENTATIVAS, MIN_TENTATIVAS_COMPETENCIA, porCompetencia, type ResumoCompetencia, type Rotulo, semHabilidadeInformada } from '../kt/devolutiva'
import { type Area, AREAS, type Meta, type StudentState } from '../kt/types'
import { MATRIZ } from '../matriz'

const CLASSE_COMP: Record<ResumoCompetencia['desempenho'], string> = {
  'acima do esperado': 'faixa ok', 'abaixo do esperado': 'faixa risco', 'dentro do esperado': 'faixa neutra', 'poucas tentativas': 'faixa neutra',
}

const CLASSE: Record<Rotulo, string> = {
  'ponto forte': 'faixa ok', 'a desenvolver': 'faixa risco', 'em desenvolvimento': 'faixa limite', 'poucas tentativas': 'faixa neutra',
}

function Habilidade({ e, descricoes }: { e: EvidenciaHabilidade; descricoes: Record<string, string> }) {
  return (
    <li className="dev-hab">
      <div className="dev-hab-topo">
        <strong>H{e.habilidade}</strong>
        <span className={CLASSE[e.rotulo]}>{e.rotulo}</span>
        <span className="dev-num">acertou {e.acertos} de {e.n}{e.n >= MIN_TENTATIVAS ? `, esperado ${e.esperado.toFixed(1)}` : ''}</span>
      </div>
      <p>{descricoes[e.key]}</p>
      {e.errosComCerteza >= 2 && <small className="dev-alerta">Errou {e.errosComCerteza} vezes tendo certeza: vale rever o conceito, não só praticar.</small>}
      {e.acertosNoChute >= 2 && <small className="dev-alerta">Acertou {e.acertosNoChute} vezes no chute: confirme o domínio com mais questões.</small>}
    </li>
  )
}

export function Devolutiva({ bank, meta, student, descricoes }: {
  bank: Bank; meta: Meta; student: StudentState; descricoes: Record<string, string>
}) {
  const ev = useMemo(() => evidencias(student, bank), [student, bank])
  const d = useMemo(() => destaques(ev), [ev])
  const comps = useMemo(() => porCompetencia(ev), [ev])
  const semH = semHabilidadeInformada(student, bank)
  const [area, setArea] = useState<Area | null>(null)
  const [imprimindo, setImprimindo] = useState(false)
  useEffect(() => {
    if (!imprimindo) return
    const fim = () => setImprimindo(false)
    addEventListener('afterprint', fim)
    const t = setTimeout(() => window.print(), 50)
    return () => { clearTimeout(t); removeEventListener('afterprint', fim) }
  }, [imprimindo])
  const areasComDados = AREAS.filter((a) => comps.some((c) => c.area === a))
  const atual = area ?? areasComDados[0] ?? null

  if (!ev.length) return <p className="vazio-texto">Responda algumas questões para receber a devolutiva pela Matriz de Referência.</p>

  const linha = (e: EvidenciaHabilidade) => (
    <li key={e.key}>
      <strong>{meta.areas[e.area]}, H{e.habilidade}</strong>
      <small>{descricoes[e.key]}</small>
    </li>
  )

  return (
    <section className="devolutiva" aria-labelledby="dev-titulo">
      <div className="mapa-head">
        <h2 id="dev-titulo" className="secao">Devolutiva pela Matriz de Referência</h2>
        <button className="btn no-print" onClick={() => setImprimindo(true)}>Imprimir ou salvar em PDF</button>
      </div>

      <div className="dev-destaques">
        <div className="retorno-bloco">
          <h3>Pontos fortes</h3>
          {d.fortes.length ? <ul className="dev-lista">{d.fortes.map(linha)}</ul> : <p className="vazio-texto">Ainda sem evidência suficiente.</p>}
        </div>
        <div className="retorno-bloco">
          <h3>Pontos a desenvolver</h3>
          {d.fracos.length ? <ul className="dev-lista">{d.fracos.map(linha)}</ul> : <p className="vazio-texto">Nenhum com evidência suficiente.</p>}
        </div>
      </div>

      {d.concepcoes.length > 0 && (
        <p className="aviso">Possíveis concepções equivocadas em {d.concepcoes.map((e) => `${e.area} H${e.habilidade}`).join(', ')}: erros repetidos com certeza costumam indicar uma ideia errada, e não falta de prática.</p>
      )}

      <div className="chips no-print" role="tablist" aria-label="Área">
        {areasComDados.map((a) => (
          <button key={a} role="tab" aria-selected={a === atual} className={a === atual ? 'chip on' : 'chip'} onClick={() => setArea(a)}>{meta.areas[a]}</button>
        ))}
      </div>

      {comps.filter((c) => imprimindo || c.area === atual).map((c) => (
        <details key={`${c.area}-${c.numero}`} className="dev-comp" open={imprimindo || c.aDesenvolver > 0 || c.desempenho === 'abaixo do esperado'}>
          <summary>
            <span className="dev-comp-titulo">{imprimindo ? `${meta.areas[c.area]}, competência ${c.numero}` : `Competência ${c.numero}`}</span>
            <span className="dev-num">{c.acertos} de {c.n} acertos, esperado {c.esperado.toFixed(1)}</span>
            {c.desempenho !== 'poucas tentativas' && <span className={CLASSE_COMP[c.desempenho]}>{c.desempenho}</span>}
            {c.fortes > 0 && <span className="faixa ok">{c.fortes} forte{c.fortes > 1 ? 's' : ''}</span>}
            {c.aDesenvolver > 0 && <span className="faixa risco">{c.aDesenvolver} a desenvolver</span>}
          </summary>
          <p className="dev-comp-desc">{c.descricao}</p>
          <ul className="dev-habs">{c.habilidades.map((e) => <Habilidade key={e.key} e={e} descricoes={descricoes} />)}</ul>
        </details>
      ))}

      {semH > 0 && <p className="fineprint">{semH} questões sem habilidade informada pelo INEP ficam fora desta devolutiva, mas contam no seu treino.</p>}
      <p className="fineprint">
        Rótulos só a partir de {MIN_TENTATIVAS} questões por habilidade e {MIN_TENTATIVAS_COMPETENCIA} por competência. "Esperado" soma a chance de acerto prevista antes de cada
        resposta, já considerando a dificuldade de cada questão. Fonte das descrições: {MATRIZ.fonte}.
      </p>
    </section>
  )
}
