/**
 * Desempenho por conteúdo programático.
 *
 * A Matriz diz qual competência a questão cobra; o conteúdo diz sobre o que ela é.
 * Quem estuda precisa dos dois: "H8, espaço e forma" não indica se o problema era
 * área de triângulo ou volume de cilindro.
 */
import { pCorrect } from './bkt'
import { type Bank, mastery, paramsFor } from './engine'
import { skillKey, type Area, type Conteudo, type StudentState } from './types'

export const MIN_TENTATIVAS_CONTEUDO = 4

export interface EvidenciaConteudo {
  id: string
  nome: string
  area: Area
  disciplina: string
  n: number
  acertos: number
  esperado: number
  z: number | null
  desempenho: 'acima do esperado' | 'abaixo do esperado' | 'dentro do esperado' | 'poucas tentativas'
  habilidades: number[]
}

export function porConteudo(s: StudentState, bank: Bank, catalogo: Conteudo[]): EvidenciaConteudo[] {
  const byId = new Map(catalogo.map((c) => [c.id, c]))
  const acc = new Map<string, { n: number; k: number; e: number; v: number; habs: Set<number> }>()
  for (const t of s.tentativas) {
    const it = bank.byId.get(t.itemId)
    if (!it?.topicos?.length) continue
    const p = t.pPrevisto ?? pCorrect(mastery(s, bank, skillKey(it.area, it.habilidade)), paramsFor(bank, it, s.banda))
    for (const tid of it.topicos) {
      if (!byId.has(tid)) continue
      const cur = acc.get(tid) ?? { n: 0, k: 0, e: 0, v: 0, habs: new Set<number>() }
      cur.n += 1
      cur.k += t.correta ? 1 : 0
      cur.e += p
      cur.v += p * (1 - p)
      if (it.habilidade) cur.habs.add(it.habilidade)
      acc.set(tid, cur)
    }
  }
  return [...acc.entries()].map(([id, a]) => {
    const c = byId.get(id)!
    const z = a.v > 0 ? (a.k - a.e) / Math.sqrt(a.v) : null
    const desempenho: EvidenciaConteudo['desempenho'] =
      a.n < MIN_TENTATIVAS_CONTEUDO || z === null ? 'poucas tentativas'
        : z >= 1.5 ? 'acima do esperado' : z <= -1.5 ? 'abaixo do esperado' : 'dentro do esperado'
    return { id, nome: c.nome, area: c.area, disciplina: c.disciplina, n: a.n, acertos: a.k, esperado: a.e, z,
             desempenho, habilidades: [...a.habs].sort((x, y) => x - y) }
  }).sort((x, y) => (x.acertos - x.esperado) / x.n - (y.acertos - y.esperado) / y.n)
}

/** Conteúdos com questões disponíveis no banco, para o filtro do treino. */
export function disponiveis(bank: Bank, catalogo: Conteudo[], areas: Area[]): (Conteudo & { itens: number })[] {
  const cont = new Map<string, number>()
  for (const it of bank.items) {
    if (!areas.includes(it.area)) continue
    for (const t of it.topicos ?? []) cont.set(t, (cont.get(t) ?? 0) + 1)
  }
  return catalogo
    .filter((c) => cont.has(c.id) && areas.includes(c.area))
    .map((c) => ({ ...c, itens: cont.get(c.id)! }))
    .sort((a, b) => a.area.localeCompare(b.area) || a.nome.localeCompare(b.nome))
}
