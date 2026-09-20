import { CREDITO_DICA, DEFAULT_LEARN, MASTERY, type BktParams, updateParcial } from './bkt'
import { eap, info3pl, p3pl, thetaFromScore, getD } from './irt'
import { atualizarBkt, atualizarTodos, type Contexto, dominioElo, estadoInicial, previsoes } from './modelos'
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
  const t0 = thetaFromScore(bandCenter(bank.bandas[banda] ?? '450-550'))
  return {
    versao: 1, nome, banda, mastery, masteryBkt: { ...mastery },
    modelos: estadoInicial({ CN: t0, CH: t0, LC: t0, MT: t0 }),
    consolidadas: {}, tentativas: [],
  }
}

/** Domínio exibido: vem do piloto (Elo sobre os parâmetros do INEP). */
export function mastery(s: StudentState, bank: Bank, k: SkillKey) {
  // O Elo já parte da faixa de nota declarada, que é a mesma informação do prior empírico:
  // misturar os dois contaria o prior duas vezes. Só se não houver item calibrado é que o prior volta.
  const elo = s.modelos && dominioElo(s.modelos.elo, k.slice(0, 2) as Area, k, bank.bySkill.get(k) ?? [], getD())
  return elo ?? s.mastery[k] ?? initialMastery(bank, k, s.banda)
}

/** Domínio pelo BKT, mantido como sombra para comparação. */
export const masteryBkt = (s: StudentState, bank: Bank, k: SkillKey) =>
  s.masteryBkt?.[k] ?? s.mastery[k] ?? initialMastery(bank, k, s.banda)

export const DOMINIO_CONSOLIDADO = 0.85
const dia = (ts = Date.now()) => new Date(ts).toISOString().slice(0, 10)

/**
 * Consolidada = bateu o limiar e confirmou em outro dia.
 * Sem a confirmação, uma sequência de sorte no mesmo dia viraria "domínio".
 */
export function consolidada(s: StudentState, bank: Bank, k: SkillKey, hoje = dia()): boolean {
  const primeiro = s.consolidadas?.[k]
  return !!primeiro && primeiro < hoje && mastery(s, bank, k) >= DOMINIO_CONSOLIDADO
}

/** Dica usada conta como erro para o rastreamento (convenção do ASSISTments). */
export const nivelDe = (t: Pick<Attempt, 'usouDica' | 'nivelDica'>): 0 | 1 | 2 | 3 => t.nivelDica ?? (t.usouDica ? 3 : 0)

/** Sessão de treino: uma por aba/dia, para dar sentido à posição da questão. */
export function sessaoAtual(s: StudentState, agora = Date.now()): { sessao: string; posicao: number; nSessao: number } {
  const ultima = s.tentativas.at(-1)
  const mesma = ultima?.sessao && agora - ultima.ts < 2 * 3600_000 && dia(ultima.ts) === dia(agora)
  const sessoes = new Set(s.tentativas.map((t) => t.sessao).filter(Boolean))
  return mesma
    ? { sessao: ultima!.sessao!, posicao: (ultima!.posicao ?? 0) + 1, nSessao: sessoes.size || 1 }
    : { sessao: `${dia(agora)}-${Math.random().toString(36).slice(2, 7)}`, posicao: 1, nSessao: sessoes.size + 1 }
}

/** Dias desde a última prática DESTA habilidade. É a variável de retenção que o Enem não tem. */
export function diasDesdeHabilidade(s: StudentState, bank: Bank, k: SkillKey, agora = Date.now()): number | undefined {
  for (let i = s.tentativas.length - 1; i >= 0; i--) {
    const it = bank.byId.get(s.tentativas[i].itemId)
    if (it && skillKey(it.area, it.habilidade) === k) {
      return Math.round(((agora - s.tentativas[i].ts) / 86_400_000) * 100) / 100
    }
  }
  return undefined
}

export function record(s: StudentState, bank: Bank, item: Item, resposta: string, dica: boolean | 0 | 1 | 2 | 3): StudentState {
  const nivel: 0 | 1 | 2 | 3 = typeof dica === 'boolean' ? (dica ? 3 : 0) : dica
  const correta = resposta === item.gabarito
  const credito = CREDITO_DICA[nivel]
  const k = skillKey(item.area, item.habilidade)
  const params = paramsFor(bank, item, s.banda)
  const pLPiloto = mastery(s, bank, k)
  const pLBkt = masteryBkt(s, bank, k)
  const estado = s.modelos ?? estadoInicial({ CN: 0, CH: 0, LC: 0, MT: 0 })
  const ctx: Contexto = { item, skill: k, estado, pL: pLBkt, params, thetaIrt: theta(s, bank, item.area).mean, D: getD() }
  const prev = previsoes(ctx)
  const { sessao, posicao, nSessao } = sessaoAtual(s)
  const t: Attempt = {
    itemId: item.id, resposta, correta, usouDica: nivel > 0, nivelDica: nivel, ts: Date.now(),
    pPrevisto: prev.elo, pLAntes: round4(pLPiloto), previsoes: prev, sessao, posicao, nSessao,
    diasDesdeHabilidade: diasDesdeHabilidade(s, bank, k),
    thetaAntes: round4(ctx.thetaIrt), pBanda: item.p_banda?.[s.banda] ?? undefined,
  }
  const modelos = atualizarTodos(ctx, correta, credito)
  const depois = { ...s, modelos, masteryBkt: { ...s.masteryBkt, [k]: atualizarBkt(pLBkt, correta && credito >= 0.5, params, DEFAULT_LEARN) },
                   mastery: { ...s.mastery, [k]: updateParcial(pLPiloto, correta, credito, params) },
                   tentativas: [...s.tentativas, t] }
  return marcarConsolidada(depois, bank, k)
}

/** Registra o primeiro dia em que a habilidade bateu o limiar; a confirmação vem em outro dia. */
function marcarConsolidada(s: StudentState, bank: Bank, k: SkillKey): StudentState {
  if (s.consolidadas?.[k] || mastery(s, bank, k) < DOMINIO_CONSOLIDADO) return s
  return { ...s, consolidadas: { ...s.consolidadas, [k]: dia() } }
}

/** Aplica uma tentativa já registrada (de outro aparelho, por exemplo) sem alterar o registro. */
export function aplicarTentativa(s: StudentState, bank: Bank, t: Attempt): StudentState {
  const item = bank.byId.get(t.itemId)
  if (!item) return { ...s, tentativas: [...s.tentativas, t] } // questão fora do banco atual: guarda, não rastreia
  const k = skillKey(item.area, item.habilidade)
  const credito = CREDITO_DICA[nivelDe(t)]
  const params = paramsFor(bank, item, s.banda)
  const estado = s.modelos ?? estadoInicial({ CN: 0, CH: 0, LC: 0, MT: 0 })
  const ctx: Contexto = { item, skill: k, estado, pL: masteryBkt(s, bank, k), params, thetaIrt: theta(s, bank, item.area).mean, D: getD() }
  const depois = {
    ...s,
    modelos: atualizarTodos(ctx, t.correta, credito),
    masteryBkt: { ...s.masteryBkt, [k]: atualizarBkt(ctx.pL, t.correta && credito >= 0.5, params, DEFAULT_LEARN) },
    mastery: { ...s.mastery, [k]: updateParcial(mastery(s, bank, k), t.correta, credito, params) },
    tentativas: [...s.tentativas, t],
  }
  return marcarConsolidada(depois, bank, k)
}

const round4 = (x: number) => Math.round(x * 1e4) / 1e4

export function setDicaUtil(s: StudentState, itemId: string, v: NonNullable<Attempt['dicaUtil']>): StudentState {
  const idx = s.tentativas.map((t) => t.itemId).lastIndexOf(itemId)
  if (idx < 0) return s
  const tentativas = s.tentativas.slice()
  tentativas[idx] = { ...tentativas[idx], dicaUtil: v }
  return { ...s, tentativas }
}

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
