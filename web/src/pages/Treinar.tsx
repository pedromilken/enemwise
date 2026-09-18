import { useMemo, useState } from 'react'
import { Bubble } from '../components/Bubble'
import { level, pCorrect } from '../kt/bkt'
import { type Bank, type Filtro, mastery, nextItem, paramsFor, record, setConfianca, theta } from '../kt/engine'
import { scoreFromTheta } from '../kt/irt'
import { disponiveis } from '../kt/conteudo'
import { revisoesVencidas, setDificuldade } from '../kt/engine'
import { type Area, AREAS, type Confianca, type Dificuldade, type Item, type Meta, nomeHabilidade, skillKey, type StudentState } from '../kt/types'
import { ask, dicaLocal, linkRelato, NIVEIS_DICA, type NivelDica, DEFAULT_MODEL, getConfig, prompt, setConfig } from '../tutor'

function Enunciado({ item }: { item: Item }) {
  const partes = (item.enunciado ?? '').split('[[placeholder]]')
  return (
    <div className="enunciado">
      {partes.map((p, i) => (
        <div key={i}>
          {p.split(/\n|(?=##)/).filter(Boolean).map((l, j) =>
            l.startsWith('#') ? <p key={j} className="enun-titulo">{l.replace(/^#+\s*/, '')}</p> : <p key={j}>{l}</p>)}
          {i < partes.length - 1 && item.figuras?.[i] && (
            <figure>
              <img src={item.figuras[i]} alt={item.descricao?.[i] ?? 'Figura da questão'} loading="lazy" />
            </figure>
          )}
        </div>
      ))}
    </div>
  )
}

/** Resolução comentada: vem do pipeline quando existe; senão, orienta pelo gabarito e pela habilidade. */
function Resolucao({ item }: { item: Item }) {
  if (!item.resolucao) {
    return (
      <details className="resolucao" open>
        <summary>Resolução</summary>
        <p><small>Esta questão ainda não tem resolução comentada. Use o tutor com IA para uma explicação, ou reveja a habilidade cobrada: {nomeHabilidade(item.habilidade)}.</small></p>
      </details>
    )
  }
  return (
    <details className="resolucao" open>
      <summary>Resolução</summary>
      {item.resolucao.split(/\n{2,}/).map((p, i) => <p key={i}>{p}</p>)}
    </details>
  )
}

function Tutor({ item, respondida, resposta }: { item: Item; respondida: boolean; resposta: string | null }) {
  const [cfg, setCfg] = useState(getConfig())
  const [texto, setTexto] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function explicar() {
    if (!cfg) return
    setBusy(true); setErro(null)
    try { setTexto(await ask(cfg, prompt('explicacao', item, resposta ?? '?'))) }
    catch (e) { setErro(e instanceof Error ? e.message : 'Falha ao consultar o tutor.') }
    finally { setBusy(false) }
  }
  return (
    <details className="tutor">
      <summary>Tutor com IA</summary>
      {!cfg ? (
        <form className="stack" onSubmit={(e) => {
          e.preventDefault()
          const f = new FormData(e.currentTarget)
          const c = { apiKey: String(f.get('k')), model: String(f.get('m')) || DEFAULT_MODEL }
          setConfig(c); setCfg(c)
        }}>
          <label className="field"><span>Chave da API da Anthropic</span><input name="k" type="password" required autoComplete="off" /></label>
          <label className="field"><span>Modelo</span><input name="m" defaultValue={DEFAULT_MODEL} /></label>
          <button className="btn" type="submit">Ativar tutor</button>
          <small>A chave fica só nesta aba do navegador e é apagada ao fechá-la.</small>
        </form>
      ) : (
        <div className="stack">
          {respondida && <button className="btn" disabled={busy} onClick={explicar}>{busy ? 'Pensando…' : 'Explicar a resolução'}</button>}
          {!respondida && <small>Responda para liberar a explicação. Antes disso, use "Pedir dica".</small>}
          {erro && <p role="alert" className="erro">{erro}</p>}
          {texto && <p className="tutor-texto">{texto}</p>}
          <button className="link" onClick={() => { setConfig(null); setCfg(null) }}>Desativar tutor</button>
        </div>
      )}
    </details>
  )
}

export function Treinar({ bank, meta, student, onChange, descricoes = {}, itemInicial }: {
  bank: Bank; meta: Meta; student: StudentState; onChange: (s: StudentState) => void
  descricoes?: Record<string, string>; itemInicial?: string | null
}) {
  const [areas, setAreas] = useState<Area[]>(AREAS)
  const [edicao, setEdicao] = useState<number | null>(null)
  const [topico, setTopico] = useState<string | null>(null)
  const filtro = (as: Area[], ed: number | null, tp: string | null): Filtro => (i) =>
    as.includes(i.area) && (ed === null || i.ano === ed) && (tp === null || (i.topicos ?? []).includes(tp))
  const [item, setItem] = useState<Item | null>(() => (itemInicial && bank.byId.get(itemInicial)) || nextItem(student, bank, filtro(AREAS, null, null)))
  const catalogo = meta.conteudos ?? []
  const conteudos = useMemo(() => disponiveis(bank, catalogo, areas), [bank, catalogo, areas])
  const conteudoAtual = catalogo.find((c) => c.id === topico) ?? null
  const [escolha, setEscolha] = useState<string | null>(null)
  const [respondida, setRespondida] = useState(false)
  const [dicas, setDicas] = useState<string[]>([])   // uma por nível já usado
  const [dicaBusy, setDicaBusy] = useState(false)
  const nivel = dicas.length as 0 | 1 | 2 | 3

  const anterior = useMemo(() => (item ? [...student.tentativas].reverse().find((t) => t.itemId === item.id && !respondida) ?? null : null), [item?.id]) // eslint-disable-line react-hooks/exhaustive-deps
  const vencidas = useMemo(() => revisoesVencidas(student, bank).filter((r) => filtro(areas, edicao, topico)(r.item)), [student, bank, areas, edicao, topico]) // eslint-disable-line react-hooks/exhaustive-deps
  const k = item ? skillKey(item.area, item.habilidade) : null
  const pL = item && k ? mastery(student, bank, k) : 0
  // Previsão congelada no momento em que a questão aparece: é a aposta do modelo, não um recálculo pós-resposta.
  const previsto = useMemo(() => (item ? pCorrect(pL, paramsFor(bank, item, student.banda)) : 0), [item?.id]) // eslint-disable-line react-hooks/exhaustive-deps
  const th = useMemo(() => (item ? theta(student, bank, item.area) : null), [student, bank, item])
  const banda = item?.p_banda?.[student.banda]

  function recomecar(as: Area[], ed: number | null, tp: string | null) {
    setAreas(as); setEdicao(ed); setTopico(tp); setEscolha(null); setRespondida(false); setDicas([])
    setItem(nextItem(student, bank, filtro(as, ed, tp)))
  }
  // trocar de área derruba o conteúdo escolhido quando ele não pertence à nova seleção
  const trocarArea = (a: Area | 'todas') => {
    const as = a === 'todas' ? AREAS : [a]
    const tp = topico && catalogo.some((c) => c.id === topico && as.includes(c.area)) ? topico : null
    recomecar(as, edicao, tp)
  }
  function confirmar() {
    if (!item || !escolha) return
    onChange(record(student, bank, item, escolha, nivel))
    setRespondida(true)
  }
  function proxima() {
    setEscolha(null); setRespondida(false); setDicas([])
    setItem(nextItem(student, bank, filtro(areas, edicao, topico)))
  }
  async function pedirDica() {
    if (!item || nivel >= 3) return
    const prox = (nivel + 1) as NivelDica
    const local = dicaLocal(item, prox, descricoes[skillKey(item.area, item.habilidade)],
      (item.topicos ?? []).map((t) => catalogo.find((c) => c.id === t)?.nome).filter(Boolean).join(', ') || undefined)
    const cfg = getConfig()
    if (!cfg) { setDicas((d) => [...d, local]); return }
    setDicaBusy(true)
    try { const txt = await ask(cfg, prompt('dica', item, undefined, prox)); setDicas((d) => [...d, txt]) }
    catch { setDicas((d) => [...d, local]) }
    finally { setDicaBusy(false) }
  }

  return (
    <div className="treinar">
      <div className="chips" role="group" aria-label="Área">
        <button className={areas.length === 4 ? 'chip on' : 'chip'} onClick={() => trocarArea('todas')}>Todas as áreas</button>
        {AREAS.map((a) => (
          <button key={a} className={areas.length === 1 && areas[0] === a ? 'chip on' : 'chip'} onClick={() => trocarArea(a)}>{meta.areas[a]}</button>
        ))}
        <label className="edicao">
          <span className="sr-only">Edição</span>
          <select value={edicao ?? ''} onChange={(e) => recomecar(areas, e.target.value ? Number(e.target.value) : null, topico)}>
            <option value="">Todas as edições</option>
            {[...meta.edicoes_com_texto].reverse().map((ano) => <option key={ano} value={ano}>ENEM {ano}</option>)}
          </select>
        </label>
        {conteudos.length > 0 && (
          <label className="edicao">
            <span className="sr-only">Conteúdo</span>
            <select value={topico ?? ''} onChange={(e) => recomecar(areas, edicao, e.target.value || null)}>
              <option value="">Todos os conteúdos</option>
              {AREAS.filter((a) => conteudos.some((c) => c.area === a)).map((a) => (
                <optgroup key={a} label={meta.areas[a]}>
                  {conteudos.filter((c) => c.area === a).map((c) => (
                    <option key={c.id} value={c.id}>{c.nome} ({c.itens})</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
        )}
      </div>
      {vencidas.length > 0 && !respondida && (
        <p className="conteudo-nota">
          <strong>{vencidas.length} {vencidas.length === 1 ? 'questão vence' : 'questões vencem'} para revisão</strong> (erros e as que você achou difíceis voltam antes).
          {' '}<button className="link" onClick={() => { setEscolha(null); setDicas([]); setItem(vencidas[0].item) }}>Revisar agora</button>
        </p>
      )}
      {conteudoAtual && (
        <p className="conteudo-nota">
          Treinando <strong>{conteudoAtual.nome}</strong> ({conteudoAtual.disciplina}). As questões vêm de {meta.areas[conteudoAtual.area]};
          o domínio continua sendo medido por habilidade da Matriz.
        </p>
      )}

      {!item ? (
        <section className="folha vazio">
          <h2>Você respondeu todas as questões desta seleção.</h2>
          <p>{topico ? 'Escolha outro conteúdo ou volte para todos.' : 'Escolha outra área ou veja no mapa quais habilidades ainda estão abertas.'}</p>
          {topico && <button className="btn" onClick={() => recomecar(areas, edicao, null)}>Ver todos os conteúdos</button>}
        </section>
      ) : (
        <div className="treinar-grid">
          <article className="folha questao" aria-live="polite">
            <header className="questao-head">
              <span>Questão {item.numero ?? ''}</span>
              <span>ENEM {item.ano}</span>
              <span>{meta.areas[item.area]}, {item.habilidade === 0 ? 'habilidade não informada' : `habilidade ${item.habilidade}`}</span>
              {(item.topicos ?? []).length > 0 && (
                <span className="questao-topico">{(item.topicos ?? []).map((t) => catalogo.find((c) => c.id === t)?.nome).filter(Boolean).join(' · ')}</span>
              )}
            </header>
            {anterior && (
              <p className="revisao-aviso">
                Revisão: você respondeu esta questão em {new Date(anterior.ts).toLocaleDateString('pt-BR')} e {anterior.correta ? 'acertou' : 'errou'}
                {anterior.dificuldade ? `, achando ${anterior.dificuldade === 'facil' ? 'fácil' : anterior.dificuldade === 'medio' ? 'média' : 'difícil'}` : ''}.
              </p>
            )}
            <Enunciado item={item} />
            <ol className="alternativas">
              {(item.alternativas ?? []).map((alt, i) => {
                const l = 'ABCDE'[i]
                const estado = respondida ? (l === item.gabarito ? 'certa' : l === escolha ? 'errada' : '') : l === escolha ? 'marcada' : ''
                return (
                  <li key={l}>
                    <button className={`alt ${estado}`} disabled={respondida} aria-pressed={l === escolha} onClick={() => setEscolha(l)}>
                      <span className="alt-letra">{l}</span>
                      <span>{alt}</span>
                    </button>
                  </li>
                )
              })}
            </ol>
            {dicas.map((d, i) => (
              <p key={i} className="dica"><strong>{NIVEIS_DICA[(i + 1) as NivelDica].rotulo}.</strong> {d}</p>
            ))}
            <div className="acoes">
              {!respondida ? (
                <>
                  <button className="btn" onClick={pedirDica} disabled={nivel >= 3 || dicaBusy}>
                    {dicaBusy ? 'Buscando dica…' : nivel === 0 ? 'Pedir dica' : nivel < 3 ? `Dica ${nivel + 1} de 3` : 'Sem mais dicas'}
                  </button>
                  {nivel > 0 && <small className="credito">Acerto agora vale {NIVEIS_DICA[nivel as NivelDica].credito} para o domínio</small>}
                  <button className="btn primary" onClick={confirmar} disabled={!escolha}>Confirmar resposta</button>
                </>
              ) : (
                <>
                  <p className={escolha === item.gabarito ? 'veredito ok' : 'veredito'}>
                    {escolha === item.gabarito ? 'Resposta correta.' : `Gabarito: ${item.gabarito}.`}
                  </p>
                  <Resolucao item={item} />
                  <button className="btn primary" onClick={proxima}>Próxima questão</button>
                  <div className="confianca" role="group" aria-label="Como você sentiu esta questão?">
                    <span>Como você sentiu esta questão?</span>
                    {([['facil', 'Fácil'], ['medio', 'Média'], ['dificil', 'Difícil']] as [Dificuldade, string][]).map(([d, label]) => {
                      const atual = [...student.tentativas].reverse().find((t) => t.itemId === item.id)?.dificuldade
                      return <button key={d} className={atual === d ? 'chip on' : 'chip'} aria-pressed={atual === d}
                        onClick={() => onChange(setDificuldade(student, item.id, d))}>{label}</button>
                    })}
                  </div>
                  <div className="confianca" role="group" aria-label="Quão seguro você estava?">
                    <span>Quão seguro você estava?</span>
                    {([['chute', 'Chutei'], ['duvida', 'Tive dúvida'], ['certeza', 'Tinha certeza']] as [Confianca, string][]).map(([c, label]) => {
                      const atual = [...student.tentativas].reverse().find((t) => t.itemId === item.id)?.confianca
                      return <button key={c} className={atual === c ? 'chip on' : 'chip'} aria-pressed={atual === c}
                        onClick={() => onChange(setConfianca(student, item.id, c))}>{label}</button>
                    })}
                  </div>
                </>
              )}
            </div>
            <p className="relato"><a href={linkRelato(item)} target="_blank" rel="noopener noreferrer">Reportar problema nesta questão</a></p>
          </article>

          <aside className="painel">
            <div className="painel-bloco">
              <Bubble value={mastery(student, bank, k!)} size={56} label="Domínio da habilidade" />
              <div>
                <p className="painel-num">{Math.round(mastery(student, bank, k!) * 100)}%</p>
                <p className="painel-label">domínio de {nomeHabilidade(item.habilidade)}, {level(mastery(student, bank, k!))}</p>
              </div>
            </div>
            <dl className="painel-dl">
              <div><dt>Chance prevista de acerto</dt><dd>{Math.round(previsto * 100)}%</dd></div>
              {banda != null && <div><dt>Acerto na sua faixa ({meta.bandas[student.banda].replace('-', ' a ')})</dt><dd>{Math.round(banda * 100)}%</dd></div>}
              {th && <div><dt>Nota estimada em {item.area}</dt><dd>{Math.round(scoreFromTheta(th.mean))} ± {Math.round(100 * th.sd)}</dd></div>}
              <div><dt>Acerto casual da questão (TRI)</dt><dd>{Math.round(item.c * 100)}%</dd></div>
            </dl>
            <Tutor key={item.id} item={item} respondida={respondida} resposta={escolha} />
          </aside>
        </div>
      )}
    </div>
  )
}
