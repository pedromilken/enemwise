import { Devolutiva } from '../components/Devolutiva'
import { Evolucao } from '../components/Evolucao'
import { MasteryGrid } from '../components/MasteryGrid'
import { type Bank, mastery } from '../kt/engine'
import { META_PADRAO, retorno } from '../kt/feedback'
import { type Meta, nomeHabilidade, type StudentState } from '../kt/types'
import { relatorioHtml, respostasCsv } from '../relatorio'
import { download, downloadTexto } from '../store'

const FAIXA_CLASSE: Record<string, string> = {
  'meta provável': 'faixa ok', 'limítrofe': 'faixa limite', 'abaixo da meta provável': 'faixa risco', 'evidência insuficiente': 'faixa neutra',
}

export function Mapa({ bank, meta, student, descricoes, bloom, onChange, onReset }: {
  bank: Bank; meta: Meta; student: StudentState; descricoes: Record<string, string>; bloom: Record<string, string>
  onChange: (s: StudentState) => void; onReset: () => void
}) {
  const feitas = student.tentativas.length
  const acertos = student.tentativas.filter((t) => t.correta).length
  const r = retorno(student, bank)
  const slug = student.nome.toLowerCase().replace(/\s+/g, '-') || 'estudante'
  return (
    <section className="folha">
      <div className="mapa-head">
        <div>
          <h1 className="display small">Seu retorno</h1>
          <p className="lede">{feitas} questões respondidas, {acertos} acertos.</p>
        </div>
        <div className="mapa-acoes">
          <button className="btn primary" onClick={() => downloadTexto(`relatorio-${slug}.html`, relatorioHtml(student, bank, meta, descricoes), 'text/html;charset=utf-8')}>Baixar relatório</button>
          <button className="btn" onClick={() => downloadTexto(`respostas-${slug}.csv`, respostasCsv(student, bank, meta), 'text/csv;charset=utf-8')}>Respostas em CSV</button>
          <button className="btn" onClick={() => download(`enemwise-${slug}.json`, student)}>Cópia para o professor (JSON)</button>
          <button className="link" onClick={() => { if (confirm('Apagar todo o progresso deste navegador?')) onReset() }}>Recomeçar do zero</button>
        </div>
      </div>

      <div className="retorno">
        <div className="retorno-bloco">
          <h2>Aonde quero chegar</h2>
          <label className="field">
            <span>Nota-alvo em cada área</span>
            <input type="number" min={300} max={900} step={10} value={student.meta ?? META_PADRAO}
              onChange={(e) => onChange({ ...student, meta: Number(e.target.value), atualizadoEm: Date.now() })} />
          </label>
          <small>Use a nota de corte do curso que você quer. Ela muda o cálculo de risco abaixo.</small>
        </div>
        <div className="retorno-bloco">
          <h2>Como estou indo</h2>
          <table className="tabela-risco">
            <tbody>
              {r.comoEstouIndo.map((a) => (
                <tr key={a.area}>
                  <th scope="row">{meta.areas[a.area]}</th>
                  <td className="nota">{a.n ? `${a.nota} ± ${a.notaSd}` : 'sem respostas'}</td>
                  <td><span className={FAIXA_CLASSE[a.faixa]}>{a.faixa}{a.pAbaixo != null ? ` (${Math.round(a.pAbaixo * 100)}%)` : ''}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          <small>A porcentagem é a chance estimada de ficar abaixo da nota-alvo. Com menos de 5 questões na área, não há rótulo.</small>
        </div>
        <div className="retorno-bloco">
          <h2>Qual o próximo passo</h2>
          {r.proximoPasso.length === 0 ? <p>Nenhuma habilidade aberta com questões disponíveis.</p> : (
            <ol className="passos">
              {r.proximoPasso.map((p) => (
                <li key={p.key}>
                  <strong>{meta.areas[p.key.slice(0, 2) as keyof Meta['areas']]}, {nomeHabilidade(p.key.split('H')[1])}</strong>
                  <span> domínio {Math.round(p.pL * 100)}%, {p.restantes} {p.restantes === 1 ? 'questão disponível' : 'questões disponíveis'}</span>
                  {descricoes[p.key] && <small>{descricoes[p.key]}</small>}
                  {bloom[p.key] && <small>Nível cognitivo: {bloom[p.key]}</small>}
                </li>
              ))}
            </ol>
          )}
          <a className="btn primary" href="#treinar">Treinar agora</a>
        </div>
      </div>

      <section className="evolucao-secao" aria-labelledby="ev-titulo">
        <h2 id="ev-titulo" className="secao">Evolução</h2>
        <Evolucao bank={bank} meta={meta} student={student} onChange={onChange} />
      </section>

      <Devolutiva bank={bank} meta={meta} student={student} descricoes={descricoes} />

      <h2 className="secao">Cartão de habilidades</h2>
      <MasteryGrid areas={meta.areas} descricoes={descricoes}
        value={(k) => (bank.bySkill.has(k) ? mastery(student, bank, k) : null)} />
    </section>
  )
}
