/**
 * Devolutiva pela Matriz de Referência: pontos fortes e a desenvolver por habilidade,
 * agregados por competência.
 *
 * Duas evidências, lado a lado:
 * - domínio estimado pelo BKT (P(L)), que acumula todas as tentativas da habilidade;
 * - acerto observado contra o ESPERADO para aquelas questões (soma das previsões
 *   registradas antes de cada resposta). Isso desconta a dificuldade: acertar 2 de 4
 *   questões muito difíceis é diferente de acertar 2 de 4 fáceis.
 *
 * Com menos de 3 tentativas na habilidade, não há rótulo: seria opinião, não evidência.
 */
import { pCorrect } from './bkt'
import { type Bank, mastery, paramsFor } from './engine'
import { type Area, AREAS, skillKey, type SkillKey, type StudentState } from './types'
import { competenciaDe, MATRIZ } from '../matriz'

export const MIN_TENTATIVAS = 3

export type Rotulo = 'ponto forte' | 'a desenvolver' | 'em desenvolvimento' | 'poucas tentativas'

export interface EvidenciaHabilidade {
  key: SkillKey
  area: Area
  habilidade: number
  competencia: number | null
  n: number
  acertos: number
  esperado: number
  z: number | null
  pL: number
  rotulo: Rotulo
  variancia: number
  errosComCerteza: number
  acertosNoChute: number
}

export function classificar(n: number, acertos: number, pL: number, z: number | null): Rotulo {
  if (n < MIN_TENTATIVAS) return 'poucas tentativas'
  if (pL <= 0.4) return 'a desenvolver'
  if (pL >= 0.8 || (acertos / n >= 0.75 && (z ?? 0) >= 1)) return 'ponto forte'
  if (z !== null && z <= -1.5) return 'a desenvolver'
  return 'em desenvolvimento'
}

export function evidencias(s: StudentState, bank: Bank): EvidenciaHabilidade[] {
  const acc = new Map<SkillKey, { area: Area; h: number; n: number; k: number; e: number; v: number; certeza: number; chute: number }>()
  for (const t of s.tentativas) {
    const it = bank.byId.get(t.itemId)
    if (!it || it.habilidade === 0) continue // sem habilidade informada pelo INEP: fora da devolutiva pela Matriz
    const key = skillKey(it.area, it.habilidade)
    const p = t.pPrevisto ?? pCorrect(mastery(s, bank, key), paramsFor(bank, it, s.banda))
    const cur = acc.get(key) ?? { area: it.area, h: it.habilidade, n: 0, k: 0, e: 0, v: 0, certeza: 0, chute: 0 }
    cur.n += 1
    cur.k += t.correta ? 1 : 0
    cur.e += p
    cur.v += p * (1 - p)
    if (!t.correta && t.confianca === 'certeza') cur.certeza += 1
    if (t.correta && t.confianca === 'chute') cur.chute += 1
    acc.set(key, cur)
  }
  return [...acc.entries()].map(([key, a]) => {
    const z = a.v > 0 ? (a.k - a.e) / Math.sqrt(a.v) : null
    const pL = mastery(s, bank, key)
    return {
      key, area: a.area, habilidade: a.h, competencia: competenciaDe(a.area, a.h)?.numero ?? null,
      n: a.n, acertos: a.k, esperado: a.e, variancia: a.v, z, pL, rotulo: classificar(a.n, a.k, pL, z),
      errosComCerteza: a.certeza, acertosNoChute: a.chute,
    }
  })
}

export interface ResumoCompetencia {
  area: Area
  numero: number
  descricao: string
  habilidades: EvidenciaHabilidade[]
  n: number
  acertos: number
  esperado: number
  fortes: number
  aDesenvolver: number
  z: number | null
  desempenho: 'acima do esperado' | 'abaixo do esperado' | 'dentro do esperado' | 'poucas tentativas'
}

export const MIN_TENTATIVAS_COMPETENCIA = 5

function desempenhoCompetencia(n: number, z: number | null): ResumoCompetencia['desempenho'] {
  if (n < MIN_TENTATIVAS_COMPETENCIA || z === null) return 'poucas tentativas'
  return z >= 1.5 ? 'acima do esperado' : z <= -1.5 ? 'abaixo do esperado' : 'dentro do esperado'
}

export function porCompetencia(ev: EvidenciaHabilidade[]): ResumoCompetencia[] {
  const out: ResumoCompetencia[] = []
  for (const area of AREAS) {
    for (const c of MATRIZ.areas[area].competencias) {
      const hs = ev.filter((e) => e.area === area && e.competencia === c.numero).sort((a, b) => a.habilidade - b.habilidade)
      if (!hs.length) continue
      const n = hs.reduce((s, e) => s + e.n, 0)
      const acertos = hs.reduce((s, e) => s + e.acertos, 0)
      const esperado = hs.reduce((s, e) => s + e.esperado, 0)
      const v = hs.reduce((s, e) => s + e.variancia, 0)
      const z = v > 0 ? (acertos - esperado) / Math.sqrt(v) : null
      out.push({
        z, desempenho: desempenhoCompetencia(n, z),
        area, numero: c.numero, descricao: c.descricao, habilidades: hs,
        n: hs.reduce((s, e) => s + e.n, 0), acertos: hs.reduce((s, e) => s + e.acertos, 0),
        esperado: hs.reduce((s, e) => s + e.esperado, 0),
        fortes: hs.filter((e) => e.rotulo === 'ponto forte').length,
        aDesenvolver: hs.filter((e) => e.rotulo === 'a desenvolver').length,
      })
    }
  }
  return out
}

export const semHabilidadeInformada = (s: StudentState, bank: Bank) =>
  s.tentativas.filter((t) => bank.byId.get(t.itemId)?.habilidade === 0).length

export function destaques(ev: EvidenciaHabilidade[], k = 5) {
  const fortes = ev.filter((e) => e.rotulo === 'ponto forte').sort((a, b) => b.pL - a.pL || (b.z ?? 0) - (a.z ?? 0)).slice(0, k)
  const fracos = ev.filter((e) => e.rotulo === 'a desenvolver').sort((a, b) => a.pL - b.pL || (a.z ?? 0) - (b.z ?? 0)).slice(0, k)
  const concepcoes = ev.filter((e) => e.errosComCerteza >= 2).sort((a, b) => b.errosComCerteza - a.errosComCerteza).slice(0, k)
  const chutes = ev.filter((e) => e.acertosNoChute >= 2).sort((a, b) => b.acertosNoChute - a.acertosNoChute).slice(0, k)
  return { fortes, fracos, concepcoes, chutes }
}
