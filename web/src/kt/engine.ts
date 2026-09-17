import { DEFAULT_LEARN, MASTERY, type BktParams, pCorrect, update } from './bkt'
import { eap, info3pl, p3pl, thetaFromScore } from './irt'
import { type Area, type Attempt, type Confianca, type Item, type SkillKey, type SkillPrior, type StudentState, skillKey } from './types'

export interface Bank {
  items: Item[]
  byId: Map<string, Item>
  bySkill: Map<SkillKey, Item[]>
  priors: Map<string, SkillPrior> // `${skill}|${banda}`
  bandas: string[]
}

export function makeBank(items: Item[], priors: SkillPrior[], bandas: string[]): Bank {
  const practicable = items.filter((i) => i.enunciado && i.alternativas?.length === 5)
  const bySkill = new Map<SkillKey, Item[]>()
  for (const it of practicable) {
    const k = skillKey(it.area, it.habilidade)
    bySkill.set(k, [...(bySkill.get(k) ?? []), it])
  }
  return {
    items: practicable,
    byId: new Map(practicable.map((i) => [i.id, i])),
    bySkill,
    priors: new Map(priors.map((p) => [`${skillKey(p.area, p.habilidade)}|${p.banda}`, p])),
    bandas,
  }
}

const bandCenter = (label: string) => {
  const [lo, hi] = label.split('-').map(Number)
  return (lo === 0 ? 400 : lo + (Math.min(hi, 1000) - lo) / 2)
}

/** Nenhuma habilidade começa consolidada sem evidência do próprio estudante. */
export const MAX_PRIOR = 0.85

/** P(L0): prior empírico da banda; sem microdados (ex.: LC), cai para a TRI no centro da banda. */
export function initialMastery(bank: Bank, key: SkillKey, banda: number): number {
  const pr = bank.priors.get(`${key}|${banda}`)
  if (pr) return Math.min(MAX_PRIOR, pr.p_l0)
  const theta = thetaFromScore(bandCenter(bank.bandas[banda] ?? '450-550'))
  const its = bank.bySkill.get(key) ?? []
  if (!its.length) return 0.3
  const m = its.reduce((s, i) => s + (p3pl(theta, i.a, i.b, i.c) - i.c) / (1 - i.c), 0) / its.length
  return Math.min(MAX_PRIOR, Math.max(0.01, m))
}

export function paramsFor(bank: Bank, item: Item, banda: number): BktParams {
  const pr = bank.priors.get(`${skillKey(item.area, item.habilidade)}|${banda}`)
  return { guess: Math.min(0.35, item.c), slip: pr?.slip ?? 0.1, learn: DEFAULT_LEARN }
}

export function newStudent(bank: Bank, nome: string, banda: number): StudentState {
  const mastery = {} as Record<SkillKey, number>
  for (const k of bank.bySkill.keys()) mastery[k] = initialMastery(bank, k, banda)
  return { versao: 1, nome, banda, mastery, tentativas: [] }
}

export function mastery(s: StudentState, bank: Bank, k: SkillKey) {
  return s.mastery[k] ?? initialMastery(bank, k, s.banda)
}

/** Dica usada conta como erro para o rastreamento (convenção do ASSISTments). */
export function record(s: StudentState, bank: Bank, item: Item, resposta: string, usouDica: boolean): StudentState {
  const correta = resposta === item.gabarito
  const k = skillKey(item.area, item.habilidade)
  const params = paramsFor(bank, item, s.banda)
  const pLAntes = mastery(s, bank, k)
  const next = update(pLAntes, correta && !usouDica, params)
  const t: Attempt = {
    itemId: item.id, resposta, correta, usouDica, ts: Date.now(),
    pPrevisto: round4(pCorrect(pLAntes, params)), pLAntes: round4(pLAntes),
    thetaAntes: round4(theta(s, bank, item.area).mean), pBanda: item.p_banda?.[s.banda] ?? undefined,
  }
  return { ...s, mastery: { ...s.mastery, [k]: next }, tentativas: [...s.tentativas, t] }
}

/** Aplica uma tentativa já registrada (de outro aparelho, por exemplo) sem alterar o registro. */
export function aplicarTentativa(s: StudentState, bank: Bank, t: Attempt): StudentState {
  const item = bank.byId.get(t.itemId)
  if (!item) return { ...s, tentativas: [...s.tentativas, t] } // questão fora do banco atual: guarda, não rastreia
  const k = skillKey(item.area, item.habilidade)
  const next = update(mastery(s, bank, k), t.correta && !t.usouDica, paramsFor(bank, item, s.banda))
  return { ...s, mastery: { ...s.mastery, [k]: next }, tentativas: [...s.tentativas, t] }
}

const round4 = (x: number) => Math.round(x * 1e4) / 1e4

export function setConfianca(s: StudentState, itemId: string, c: Confianca): StudentState {
  const idx = s.tentativas.map((t) => t.itemId).lastIndexOf(itemId)
  if (idx < 0) return s
  const tentativas = s.tentativas.slice()
  tentativas[idx] = { ...tentativas[idx], confianca: c }
  return { ...s, tentativas }
}

export function theta(s: StudentState, bank: Bank, area: Area) {
  const obs = s.tentativas
    .map((t) => ({ t, it: bank.byId.get(t.itemId) }))
    .filter((x) => x.it?.area === area)
    .map(({ t, it }) => ({ a: it!.a, b: it!.b, c: it!.c, correct: t.correta }))
  return eap(obs, thetaFromScore(bandCenter(bank.bandas[s.banda] ?? '450-550')), 1)
}

/**
 * Política de seleção.
 * 1) Escolhe a habilidade mais frágil ainda não consolidada (com 20% de exploração
 *    para intercalar habilidades, o que ajuda a retenção).
 * 2) Dentro dela, a questão inédita mais informativa para o theta atual.
 */
export type Filtro = (it: Item) => boolean

export function nextItem(s: StudentState, bank: Bank, filtro: Filtro = () => true, rng = Math.random): Item | null {
  const seen = new Set(s.tentativas.map((t) => t.itemId))
  const skills = [...bank.bySkill.entries()]
    .map(([k, its]) => ({ k, its: its.filter((i) => filtro(i) && !seen.has(i.id)), pL: mastery(s, bank, k) }))
    .filter((x) => x.its.length > 0)
  if (!skills.length) return null
  const open = skills.filter((x) => x.pL < MASTERY)
  const pool = open.length ? open : skills
  // habilidade 0 (não informada pelo INEP) junta muitos itens e ficaria sempre "mais frágil": só entra na exploração
  const comMatriz = pool.filter((x) => !x.k.endsWith('-H0'))
  const alvo = comMatriz.length ? comMatriz : pool
  const pick = rng() < 0.2 ? pool[Math.floor(rng() * pool.length)] : alvo.reduce((a, b) => (b.pL < a.pL ? b : a))
  const th = theta(s, bank, pick.k.slice(0, 2) as Area).mean
  return pick.its.reduce((a, b) => (info3pl(th, b.a, b.b, b.c) > info3pl(th, a.a, a.b, a.c) ? b : a))
}
