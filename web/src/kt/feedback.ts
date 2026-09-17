/**
 * Camada pedagógica.
 *
 * - Risco por área (inspirado no SPPA): em vez de um classificador treinado em notas
 *   passadas, usa a posterior do theta na TRI. Dá uma probabilidade, não só um rótulo.
 * - Retorno em três perguntas (Hattie & Timperley, 2007): aonde quero chegar,
 *   como estou indo, qual o próximo passo.
 * - Revisão de questões (fase de avaliação do curso no SPPA; "fechar o ciclo" em
 *   Walvoord, 2010): itens em que a turma erra muito mais do que a TRI esperava.
 */
import { MASTERY } from './bkt'
import { type Bank, mastery, theta } from './engine'
import { p3pl, scoreFromTheta, thetaFromScore } from './irt'
import { type Area, AREAS, type Item, type SkillKey, type StudentState } from './types'

export const MIN_EVIDENCIA = 5 // abaixo disso, não rotulamos risco: seria só o prior falando
export const META_PADRAO = 600

export type Faixa = 'meta provável' | 'limítrofe' | 'abaixo da meta provável' | 'evidência insuficiente'

// Φ(x) por aproximação de Abramowitz-Stegun 7.1.26 (erro < 1,5e-7)
export function phi(x: number): number {
  const t = 1 / (1 + 0.3275911 * Math.abs(x) / Math.SQRT2)
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t *
    Math.exp(-(x * x) / 2)
  return x >= 0 ? (1 + y) / 2 : (1 - y) / 2
}

export interface RiscoArea {
  area: Area
  n: number
  nota: number
  notaSd: number
  pAbaixo: number | null
  faixa: Faixa
}

export function risco(s: StudentState, bank: Bank, area: Area, meta = s.meta ?? META_PADRAO): RiscoArea {
  const n = s.tentativas.filter((t) => bank.byId.get(t.itemId)?.area === area).length
  const th = theta(s, bank, area)
  const base = { area, n, nota: Math.round(scoreFromTheta(th.mean)), notaSd: Math.round(100 * th.sd) }
  if (n < MIN_EVIDENCIA) return { ...base, pAbaixo: null, faixa: 'evidência insuficiente' }
  const pAbaixo = phi((thetaFromScore(meta) - th.mean) / Math.max(th.sd, 1e-6))
  const faixa: Faixa = pAbaixo >= 0.7 ? 'abaixo da meta provável' : pAbaixo > 0.3 ? 'limítrofe' : 'meta provável'
  return { ...base, pAbaixo, faixa }
}

export function prioridades(s: StudentState, bank: Bank, k = 3): { key: SkillKey; pL: number; restantes: number }[] {
  const seen = new Set(s.tentativas.map((t) => t.itemId))
  return [...bank.bySkill.entries()]
    .map(([key, its]) => ({ key, pL: mastery(s, bank, key), restantes: its.filter((i) => !seen.has(i.id)).length }))
    .filter((x) => x.pL < MASTERY && x.restantes > 0)
    .sort((a, b) => a.pL - b.pL)
    .slice(0, k)
}

export function retorno(s: StudentState, bank: Bank) {
  return {
    aondeQueroChegar: s.meta ?? META_PADRAO,
    comoEstouIndo: AREAS.map((a) => risco(s, bank, a)),
    proximoPasso: prioridades(s, bank),
  }
}

export interface ItemRevisao { item: Item; n: number; observado: number; esperado: number }

/** Itens em que a turma acerta bem menos que o previsto pela TRI no theta de cada estudante. */
export function itensParaRevisar(turma: StudentState[], bank: Bank, minN = 3, limiar = -0.25): ItemRevisao[] {
  const acc = new Map<string, { n: number; obs: number; esp: number }>()
  for (const s of turma) {
    for (const t of s.tentativas) {
      const it = bank.byId.get(t.itemId)
      if (!it) continue
      const th = t.thetaAntes ?? theta(s, bank, it.area).mean
      const cur = acc.get(it.id) ?? { n: 0, obs: 0, esp: 0 }
      cur.n += 1; cur.obs += t.correta ? 1 : 0; cur.esp += p3pl(th, it.a, it.b, it.c)
      acc.set(it.id, cur)
    }
  }
  return [...acc.entries()]
    .filter(([, v]) => v.n >= minN)
    .map(([id, v]) => ({ item: bank.byId.get(id)!, n: v.n, observado: v.obs / v.n, esperado: v.esp / v.n }))
    .filter((r) => r.observado - r.esperado <= limiar)
    .sort((a, b) => (a.observado - a.esperado) - (b.observado - b.esperado))
}

export function csvIntervencao(turma: StudentState[], bank: Bank, meta: number): string {
  const head = ['estudante', 'area', 'questoes', 'nota_estimada', 'incerteza', 'p_abaixo_da_meta', 'faixa', 'prioridades']
  const esc = (v: unknown) => `"${String(v).replace(/"/g, '""')}"`
  const rows = turma.flatMap((s) => AREAS.map((a) => {
    const r = risco(s, bank, a, s.meta ?? meta)
    const pri = prioridades(s, bank).filter((p) => p.key.startsWith(a)).map((p) => p.key).join(' ')
    return [s.nome, a, r.n, r.nota, r.notaSd, r.pAbaixo == null ? '' : r.pAbaixo.toFixed(2), r.faixa, pri].map(esc).join(',')
  }))
  return [head.join(','), ...rows].join('\n')
}
