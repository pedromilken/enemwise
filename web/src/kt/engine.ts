import { CREDITO_DICA, DEFAULT_LEARN, MASTERY, type BktParams, pCorrect, updateParcial } from './bkt'
import { eap, info3pl, p3pl, thetaFromScore } from './irt'
import { type Area, type Attempt, type Confianca, type Dificuldade, type Item, type SkillKey, type SkillPrior, type StudentState, skillKey } from './types'

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
export const nivelDe = (t: Pick<Attempt, 'usouDica' | 'nivelDica'>): 0 | 1 | 2 | 3 => t.nivelDica ?? (t.usouDica ? 3 : 0)

export function record(s: StudentState, bank: Bank, item: Item, resposta: string, dica: boolean | 0 | 1 | 2 | 3): StudentState {
  const nivel: 0 | 1 | 2 | 3 = typeof dica === 'boolean' ? (dica ? 3 : 0) : dica
  const correta = resposta === item.gabarito
  const k = skillKey(item.area, item.habilidade)
  const params = paramsFor(bank, item, s.banda)
  const pLAntes = mastery(s, bank, k)
  const next = updateParcial(pLAntes, correta, CREDITO_DICA[nivel], params)
  const t: Attempt = {
    itemId: item.id, resposta, correta, usouDica: nivel > 0, nivelDica: nivel, ts: Date.now(),
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
  const next = updateParcial(mastery(s, bank, k), t.correta, CREDITO_DICA[nivelDe(t)], paramsFor(bank, item, s.banda))
  return { ...s, mastery: { ...s.mastery, [k]: next }, tentativas: [...s.tentativas, t] }
}

const round4 = (x: number) => Math.round(x * 1e4) / 1e4

export function setDificuldade(s: StudentState, itemId: string, d: Dificuldade): StudentState {
  const idx = s.tentativas.map((t) => t.itemId).lastIndexOf(itemId)
  if (idx < 0) return s
  const tentativas = s.tentativas.slice()
  tentativas[idx] = { ...tentativas[idx], dificuldade: d }
  return { ...s, tentativas }
}

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

/**
 * Revisão espaçada por dificuldade percebida.
 * Intervalos, em dias, até a questão voltar: quem errou revê logo; quem acertou e achou
 * difícil revê cedo; quem acertou e achou fácil quase não revê, porque já domina.
 */
export const INTERVALO_REVISAO_DIAS: Record<'erro' | Dificuldade | 'sem', number> = { erro: 1, dificil: 3, medio: 7, facil: 21, sem: 10 }
export const FRACAO_REVISAO = 0.35
const DIA = 86_400_000

export interface Revisao { item: Item; venceEm: number; atrasoDias: number; motivo: 'erro' | Dificuldade | 'sem' }

export function proximaRevisao(t: Attempt): { venceEm: number; motivo: Revisao['motivo'] } {
  const motivo: Revisao['motivo'] = !t.correta ? 'erro' : t.dificuldade ?? 'sem'
  return { venceEm: t.ts + INTERVALO_REVISAO_DIAS[motivo] * DIA, motivo }
}

/** Questões cuja revisão venceu, da mais urgente para a menos (erro antes de difícil, e mais atrasada antes). */
export function revisoesVencidas(s: StudentState, bank: Bank, agora = Date.now()): Revisao[] {
  const ultima = new Map<string, Attempt>()
  for (const t of s.tentativas) ultima.set(t.itemId, t)   // fica a última tentativa de cada questão
  const ordem: Record<Revisao['motivo'], number> = { erro: 0, dificil: 1, medio: 2, sem: 3, facil: 4 }
  return [...ultima.values()]
    .map((t) => ({ t, item: bank.byId.get(t.itemId), ...proximaRevisao(t) }))
    .filter((x): x is typeof x & { item: Item } => !!x.item && x.venceEm <= agora)
    .map(({ item, venceEm, motivo }) => ({ item, venceEm, motivo, atrasoDias: Math.floor((agora - venceEm) / DIA) }))
    .sort((a, b) => ordem[a.motivo] - ordem[b.motivo] || b.atrasoDias - a.atrasoDias)
}

export function nextItem(s: StudentState, bank: Bank, filtro: Filtro = () => true, rng = Math.random, agora = Date.now()): Item | null {
  // revisão espaçada: questões vencidas voltam com prioridade proporcional à dificuldade sentida
  const vencidas = revisoesVencidas(s, bank, agora).filter((r) => filtro(r.item))
  if (vencidas.length && rng() < FRACAO_REVISAO) return vencidas[0].item
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
