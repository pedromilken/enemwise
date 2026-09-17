import { useMemo, useState } from 'react'
import { MasteryGrid } from '../components/MasteryGrid'
import { MASTERY } from '../kt/bkt'
import { type Bank, mastery } from '../kt/engine'
import { porConteudo } from '../kt/conteudo'
import { evidencias, porCompetencia } from '../kt/devolutiva'
import { csvIntervencao, itensParaRevisar, META_PADRAO, risco } from '../kt/feedback'
import { AREAS, type Meta, nomeHabilidade, type SkillKey, type StudentState } from '../kt/types'
import { isStudentState, loadTurma, saveTurma } from '../store'

const FAIXA_CLASSE: Record<string, string> = {
  'meta provável': 'faixa ok', 'limítrofe': 'faixa limite', 'abaixo da meta provável': 'faixa risco', 'evidência insuficiente': 'faixa neutra',
}

function baixarCsv(nome: string, texto: string) {
  const blob = new Blob(['\ufeff' + texto], { type: 'text/csv;charset=utf-8' })
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: nome })
  a.click(); URL.revokeObjectURL(a.href)
}

export function Professor({ bank, meta, descricoes, bloom }: {
  bank: Bank; meta: Meta; descricoes: Record<string, string>; bloom: Record<string, string>
}) {
  const [turma, setTurma] = useState<StudentState[]>(loadTurma)
  const [aviso, setAviso] = useState<string | null>(null)
  const [metaTurma, setMetaTurma] = useState(META_PADRAO)

  async function importar(files: FileList | null) {
    if (!files) return
    const novos: StudentState[] = []
    let invalidos = 0
    for (const f of Array.from(files)) {
      try {
        const s = JSON.parse(await f.text())
        isStudentState(s) ? novos.push(s) : invalidos++
      } catch { invalidos++ }
    }
    const next = [...turma.filter((t) => !novos.some((n) => n.nome === t.nome)), ...novos]
    setTurma(next); saveTurma(next)
    setAviso(invalidos ? `${invalidos} arquivo(s) ignorado(s): não são exportações do ENEMWise.` : null)
  }

  const resumo = useMemo(() => [...bank.bySkill.keys()].map((k) => {
    const vals = turma.map((s) => mastery(s, bank, k))
    const media = vals.reduce((a, b) => a + b, 0) / Math.max(1, vals.length)
    return { k, media, abaixo: vals.filter((v) => v < 0.5).length, dominam: vals.filter((v) => v >= MASTERY).length }
  }).sort((a, b) => a.media - b.media), [turma, bank])
  const porK = new Map(resumo.map((r) => [r.k, r]))
  const revisar = useMemo(() => itensParaRevisar(turma, bank), [turma, bank])
  const conteudosTurma = useMemo(() => {
    const g = new Map<string, { nome: string; disciplina: string; area: string; n: number; acertos: number; esperado: number; alunos: number }>()
    for (const s of turma) {
      for (const c of porConteudo(s, bank, meta.conteudos ?? [])) {
        const cur = g.get(c.id) ?? { nome: c.nome, disciplina: c.disciplina, area: c.area, n: 0, acertos: 0, esperado: 0, alunos: 0 }
        cur.n += c.n; cur.acertos += c.acertos; cur.esperado += c.esperado; cur.alunos += 1
        g.set(c.id, cur)
      }
    }
    return [...g.entries()].filter(([, c]) => c.n >= 10)
      .sort(([, a], [, b]) => (a.acertos - a.esperado) / a.n - (b.acertos - b.esperado) / b.n)
  }, [turma, bank, meta.conteudos])
  const competencias = useMemo(() => {
    const g = new Map<string, { area: string; numero: number; descricao: string; n: number; acertos: number; esperado: number; alunosFracos: number; alunos: number }>()
    for (const s of turma) {
      for (const c of porCompetencia(evidencias(s, bank))) {
        const k = `${c.area}-${c.numero}`
        const cur = g.get(k) ?? { area: c.area, numero: c.numero, descricao: c.descricao, n: 0, acertos: 0, esperado: 0, alunosFracos: 0, alunos: 0 }
        cur.n += c.n; cur.acertos += c.acertos; cur.esperado += c.esperado; cur.alunos += 1
        if (c.aDesenvolver > 0) cur.alunosFracos += 1
        g.set(k, cur)
      }
    }
    return [...g.values()].sort((a, b) => (a.acertos - a.esperado) / Math.max(a.n, 1) - (b.acertos - b.esperado) / Math.max(b.n, 1))
  }, [turma, bank])
  const porBloom = useMemo(() => {
    const g = new Map<string, number[]>()
    for (const r of resumo) {
      const nivel = bloom[r.k]?.replace(' (sugerido)', '')
      if (nivel) g.set(nivel, [...(g.get(nivel) ?? []), r.media])
    }
    return [...g.entries()].map(([nivel, v]) => ({ nivel, n: v.length, media: v.reduce((a, b) => a + b, 0) / v.length }))
  }, [resumo, bloom])
  const confianca = useMemo(() => {
    const ts = turma.flatMap((s) => s.tentativas).filter((t) => t.confianca)
    return (['chute', 'duvida', 'certeza'] as const).map((c) => {
      const g = ts.filter((t) => t.confianca === c)
      return { c, n: g.length, acerto: g.length ? g.filter((t) => t.correta).length / g.length : null }
    })
  }, [turma])

  return (
    <section className="folha">
      <h1 className="display small">Visão da turma</h1>
      <p className="lede">
        O ciclo tem três passos: definir a meta, olhar as evidências e decidir a ação. Carregue os arquivos exportados pelos estudantes. Eles são lidos só neste navegador.
      </p>
      <div className="acoes">
        <label className="btn upload">
          Carregar arquivos dos estudantes
          <input type="file" accept="application/json" multiple onChange={(e) => importar(e.target.files)} />
        </label>
        <label className="field inline">
          <span>Meta da turma</span>
          <input type="number" min={300} max={900} step={10} value={metaTurma} onChange={(e) => setMetaTurma(Number(e.target.value))} />
        </label>
      </div>
      {aviso && <p role="status" className="erro">{aviso}</p>}

      {turma.length === 0 ? (
        <p className="vazio-texto">Nenhum estudante carregado ainda.</p>
      ) : (
        <>
          <h2 className="secao">Quem precisa de apoio agora</h2>
          <div className="tabela-rolagem">
            <table className="prioridades">
              <thead><tr><th>Estudante</th>{AREAS.map((a) => <th key={a}>{meta.areas[a]}</th>)}<th></th></tr></thead>
              <tbody>
                {turma.map((s) => (
                  <tr key={s.nome}>
                    <th scope="row">{s.nome}<small>{s.tentativas.length} questões, meta {s.meta ?? metaTurma}</small></th>
                    {AREAS.map((a) => {
                      const r = risco(s, bank, a, s.meta ?? metaTurma)
                      return <td key={a}><span className={FAIXA_CLASSE[r.faixa]}>{r.faixa}</span>{r.n > 0 && <small>{r.nota} ± {r.notaSd}</small>}</td>
                    })}
                    <td><button className="link" onClick={() => { const t = turma.filter((x) => x !== s); setTurma(t); saveTurma(t) }}>remover</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button className="btn" onClick={() => baixarCsv('enemwise-intervencao.csv', csvIntervencao(turma, bank, metaTurma))}>Baixar planilha para contato</button>
          <p className="fineprint">A planilha traz faixa de risco e habilidades prioritárias por estudante, pronta para mala direta.</p>

          {conteudosTurma.length > 0 && (
            <>
              <h2 className="secao">Conteúdos que mais pedem aula</h2>
              <div className="tabela-rolagem">
                <table className="prioridades">
                  <thead><tr><th>Conteúdo</th><th>Acertos</th><th>Esperado</th><th>Estudantes</th></tr></thead>
                  <tbody>{conteudosTurma.slice(0, 10).map(([id, c]) => (
                    <tr key={id}>
                      <td>{c.nome}<small>{c.disciplina === meta.areas[c.area as keyof Meta['areas']] ? c.disciplina : `${c.disciplina}, ${meta.areas[c.area as keyof Meta['areas']]}`}</small></td>
                      <td>{c.acertos} de {c.n}</td><td>{c.esperado.toFixed(1)}</td><td>{c.alunos}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </>
          )}

          <h2 className="secao">Competências da Matriz: onde a turma rende abaixo do esperado</h2>
          <div className="tabela-rolagem">
            <table className="prioridades">
              <thead><tr><th>Competência</th><th>Acertos</th><th>Esperado</th><th>Estudantes com habilidade a desenvolver</th></tr></thead>
              <tbody>{competencias.slice(0, 10).map((c) => (
                <tr key={`${c.area}-${c.numero}`}>
                  <td>{meta.areas[c.area as keyof Meta['areas']]}, competência {c.numero}<small>{c.descricao}</small></td>
                  <td>{c.acertos} de {c.n}</td><td>{c.esperado.toFixed(1)}</td><td>{c.alunosFracos} de {c.alunos}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>

          <h2 className="secao">Habilidades que mais pedem aula</h2>
          <table className="prioridades">
            <thead><tr><th>Habilidade</th><th>Domínio médio</th><th>Abaixo de 50%</th><th>Consolidaram</th></tr></thead>
            <tbody>
              {resumo.slice(0, 8).map((r) => (
                <tr key={r.k}>
                  <td>{meta.areas[r.k.slice(0, 2) as keyof Meta['areas']]}, {nomeHabilidade(r.k.split('H')[1])}
                    {descricoes[r.k] && <small>{descricoes[r.k]}</small>}{bloom[r.k] && <small>Bloom: {bloom[r.k]}</small>}</td>
                  <td>{Math.round(r.media * 100)}%</td><td>{r.abaixo} de {turma.length}</td><td>{r.dominam}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {porBloom.length > 0 && (
            <>
              <h2 className="secao">Domínio por nível cognitivo</h2>
              <table className="prioridades">
                <thead><tr><th>Nível (Bloom, 1956)</th><th>Habilidades</th><th>Domínio médio</th></tr></thead>
                <tbody>{porBloom.map((b) => <tr key={b.nivel}><td>{b.nivel}</td><td>{b.n}</td><td>{Math.round(b.media * 100)}%</td></tr>)}</tbody>
              </table>
            </>
          )}

          <h2 className="secao">Questões para revisar</h2>
          {revisar.length === 0 ? <p className="vazio-texto">Nenhuma questão com acerto muito abaixo do esperado (mínimo de 3 respostas).</p> : (
            <table className="prioridades">
              <thead><tr><th>Questão</th><th>Respostas</th><th>Acerto da turma</th><th>Esperado pela TRI</th></tr></thead>
              <tbody>{revisar.slice(0, 10).map((r) => (
                <tr key={r.item.id}><td>ENEM {r.item.ano}, questão {r.item.numero}, {r.item.area} {nomeHabilidade(r.item.habilidade)}</td>
                  <td>{r.n}</td><td>{Math.round(r.observado * 100)}%</td><td>{Math.round(r.esperado * 100)}%</td></tr>
              ))}</tbody>
            </table>
          )}
          <p className="fineprint">Diferença grande sugere lacuna de ensino no tema, não só questão difícil: a dificuldade já está descontada.</p>

          <h2 className="secao">Autoavaliação dos estudantes</h2>
          <table className="prioridades">
            <thead><tr><th>Declararam</th><th>Respostas</th><th>Acerto</th></tr></thead>
            <tbody>{confianca.map((c) => (
              <tr key={c.c}><td>{{ chute: 'Chutei', duvida: 'Tive dúvida', certeza: 'Tinha certeza' }[c.c]}</td><td>{c.n}</td>
                <td>{c.acerto == null ? '' : `${Math.round(c.acerto * 100)}%`}</td></tr>
            ))}</tbody>
          </table>
          <p className="fineprint">Medida indireta. Acerto alto entre quem "chutou" indica conhecimento que o estudante não reconhece; acerto baixo com "certeza" indica concepção equivocada.</p>

          <h2 className="secao">Mapa da turma</h2>
          <MasteryGrid areas={meta.areas} descricoes={descricoes}
            value={(k: SkillKey) => porK.get(k)?.media ?? null}
            note={(k) => { const r = porK.get(k); return r ? `${r.abaixo}/${turma.length}` : undefined }} />
        </>
      )}
    </section>
  )
}
