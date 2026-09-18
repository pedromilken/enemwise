/**
 * Relatório legível do estudante: HTML autônomo (abre em qualquer navegador, imprime em PDF)
 * e CSV das respostas. O JSON continua existindo como cópia técnica para o professor importar.
 */
import { porConteudo } from './kt/conteudo'
import { destaques, evidencias, porCompetencia } from './kt/devolutiva'
import type { Bank } from './kt/engine'
import { nivelDe } from './kt/engine'
import { META_PADRAO, risco } from './kt/feedback'
import { evolucao } from './kt/evolucao'
import { AREAS, type Meta, type StudentState } from './kt/types'

const esc = (s: unknown) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!))
const CONF: Record<string, string> = { chute: 'chutei', duvida: 'tive dúvida', certeza: 'tinha certeza' }

export function relatorioHtml(s: StudentState, bank: Bank, meta: Meta, descricoes: Record<string, string>): string {
  const ev = evidencias(s, bank)
  const d = destaques(ev)
  const comps = porCompetencia(ev)
  const conts = porConteudo(s, bank, meta.conteudos ?? [])
  const alvo = s.meta ?? META_PADRAO
  const riscos = AREAS.map((a) => risco(s, bank, a))
  const nome = (id: string) => (meta.conteudos ?? []).find((c) => c.id === id)?.nome ?? id
  const lista = (xs: typeof d.fortes) => xs.length
    ? `<ul>${xs.map((e) => `<li><strong>${esc(meta.areas[e.area])}, H${e.habilidade}</strong><br><small>${esc(descricoes[e.key] ?? '')}</small></li>`).join('')}</ul>`
    : '<p class="muted">Ainda sem evidência suficiente.</p>'
  const acertos = s.tentativas.filter((t) => t.correta).length

  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Relatório ENEMWise de ${esc(s.nome)}</title>
<style>
body{font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif;color:#1B2140;max-width:60rem;margin:2rem auto;padding:0 1rem}
h1{font-size:1.7rem;margin:0 0 .25rem}h2{font-size:1.15rem;margin:1.75rem 0 .5rem;border-bottom:1px solid #d8dcd5;padding-bottom:.25rem}
h3{font-size:1rem;margin:1rem 0 .35rem}.muted{color:#5b6070}small{color:#5b6070}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:.35rem .5rem;border-bottom:1px solid #e6e9e3;vertical-align:top}th{font-weight:600}
.tag{display:inline-block;padding:.05rem .5rem;border-radius:1rem;font-size:.8rem;border:1px solid}
.ok{color:#1f7a3e;border-color:#1f7a3e}.risco{color:#b02a4b;border-color:#b02a4b}.neutro{color:#5b6070;border-color:#5b6070}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}@media(max-width:700px){.grid{grid-template-columns:1fr}}
@media print{body{margin:0}h2{break-after:avoid}tr{break-inside:avoid}}
</style></head><body>
<h1>Relatório de treino de ${esc(s.nome)}</h1>
<p class="muted">ENEMWise, gerado em ${new Date().toLocaleString('pt-BR')}. ${s.tentativas.length} questões respondidas, ${acertos} acertos. Meta: ${alvo} pontos.</p>

<h2>Onde você está em relação à meta</h2>
<table><tr><th>Área</th><th>Questões</th><th>Nota estimada</th><th>Situação</th></tr>
${riscos.map((r) => `<tr><td>${esc(meta.areas[r.area])}</td><td>${r.n}</td><td>${r.n ? `${r.nota} ± ${r.notaSd}` : '—'}</td><td><span class="tag ${r.faixa === 'meta provável' ? 'ok' : r.faixa === 'abaixo da meta provável' ? 'risco' : 'neutro'}">${esc(r.faixa)}</span></td></tr>`).join('')}
</table>

${(s.historico ?? []).length ? `<h2>Evolução em relação a resultados anteriores</h2>
<table><tr><th>Área</th><th>Último resultado registrado</th><th>Estimativa atual</th><th>Variação</th></tr>
${evolucao(s, bank).filter((a) => a.pontos.length).map((a) => `<tr><td>${esc(meta.areas[a.area])}</td><td>${a.ultimo ? `${a.ultimo.nota} <small>(${esc(a.ultimo.origem)}, ${a.ultimo.data.split('-').reverse().join('/')})</small>` : '—'}</td><td>${a.estimativa ?? '<small>poucas questões</small>'}</td><td>${a.variacao === null ? '—' : `<span class="tag ${a.variacao >= 0 ? 'ok' : 'risco'}">${a.variacao > 0 ? '+' : ''}${a.variacao}</span>`}</td></tr>`).join('')}
</table>
<p class="muted"><small>Registros: ${(s.historico ?? []).map((h) => `${h.data.split('-').reverse().join('/')} ${esc(h.origem)} (${AREAS.filter((x) => h.notas[x] !== undefined).map((x) => `${x} ${h.notas[x]}`).join(', ')})`).join('; ')}.</small></p>` : ''}

<h2>Devolutiva pela Matriz de Referência</h2>
<div class="grid"><div><h3>Pontos fortes</h3>${lista(d.fortes)}</div><div><h3>Pontos a desenvolver</h3>${lista(d.fracos)}</div></div>
${d.concepcoes.length ? `<p><strong>Atenção:</strong> erros repetidos com certeza em ${d.concepcoes.map((e) => `${e.area} H${e.habilidade}`).join(', ')}. Costumam indicar uma ideia errada, e não falta de prática: vale rever o conceito.</p>` : ''}

${AREAS.filter((a) => comps.some((c) => c.area === a)).map((a) => `<h3>${esc(meta.areas[a])}</h3>
<table><tr><th>Competência</th><th>Acertos</th><th>Esperado</th><th>Situação</th></tr>
${comps.filter((c) => c.area === a).map((c) => `<tr><td><strong>${c.numero}</strong> <small>${esc(c.descricao)}</small></td><td>${c.acertos} de ${c.n}</td><td>${c.esperado.toFixed(1)}</td><td>${c.desempenho === 'poucas tentativas' ? '<small>poucas questões</small>' : `<span class="tag ${c.desempenho === 'acima do esperado' ? 'ok' : c.desempenho === 'abaixo do esperado' ? 'risco' : 'neutro'}">${c.desempenho}</span>`}</td></tr>`).join('')}
</table>`).join('')}

${conts.length ? `<h2>Por conteúdo</h2>
<table><tr><th>Conteúdo</th><th>Acertos</th><th>Esperado</th><th>Situação</th><th>Habilidades</th></tr>
${conts.map((c) => `<tr><td>${esc(c.nome)} <small>${esc(c.disciplina)}</small></td><td>${c.acertos} de ${c.n}</td><td>${c.esperado.toFixed(1)}</td><td>${c.desempenho === 'poucas tentativas' ? '<small>poucas questões</small>' : `<span class="tag ${c.desempenho === 'acima do esperado' ? 'ok' : c.desempenho === 'abaixo do esperado' ? 'risco' : 'neutro'}">${c.desempenho}</span>`}</td><td>${c.habilidades.map((h) => `H${h}`).join(', ')}</td></tr>`).join('')}
</table>` : ''}

<h2>Questões respondidas</h2>
<table><tr><th>Quando</th><th>Questão</th><th>Área e habilidade</th><th>Conteúdo</th><th>Resposta</th><th>Dica</th><th>Confiança</th></tr>
${[...s.tentativas].reverse().map((t) => { const it = bank.byId.get(t.itemId); return `<tr><td>${new Date(t.ts).toLocaleDateString('pt-BR')}</td><td>${it ? `ENEM ${it.ano}, nº ${it.numero ?? '?'}` : esc(t.itemId)}</td><td>${it ? `${esc(meta.areas[it.area])}, H${it.habilidade}` : ''}</td><td>${it ? (it.topicos ?? []).map(nome).map(esc).join(' · ') : ''}</td><td>${t.correta ? `<span class="tag ok">acertou (${esc(t.resposta)})</span>` : `<span class="tag risco">errou: ${esc(t.resposta)}, gabarito ${esc(it?.gabarito ?? '')}</span>`}</td><td>${nivelDe(t) ? `nível ${nivelDe(t)}` : '—'}</td><td>${CONF[t.confianca ?? ''] ?? '—'}</td></tr>` }).join('')}
</table>
<p class="muted"><small>"Esperado" soma a chance de acerto prevista antes de cada resposta, considerando a dificuldade de cada questão. Rótulos só a partir de 3 questões por habilidade, 5 por competência e 4 por conteúdo. Fonte das descrições: ${esc(meta.fonte)} e Matriz de Referência do Enem (INEP).</small></p>
</body></html>`
}

export function respostasCsv(s: StudentState, bank: Bank, meta: Meta): string {
  const nome = (id: string) => (meta.conteudos ?? []).find((c) => c.id === id)?.nome ?? id
  const q = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const linhas = [['data', 'edicao', 'questao', 'area', 'habilidade', 'conteudos', 'resposta', 'gabarito', 'correta', 'nivel_dica', 'confianca', 'p_previsto'].join(';')]
  for (const t of s.tentativas) {
    const it = bank.byId.get(t.itemId)
    linhas.push([new Date(t.ts).toISOString(), it?.ano, it?.numero, it ? meta.areas[it.area] : '', it?.habilidade,
      (it?.topicos ?? []).map(nome).join(' | '), t.resposta, it?.gabarito, t.correta ? 1 : 0, nivelDe(t), t.confianca ?? '', t.pPrevisto ?? ''].map(q).join(';'))
  }
  return '\ufeff' + linhas.join('\r\n')  // BOM para o Excel abrir com acentos certos
}
