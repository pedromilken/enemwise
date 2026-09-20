/**
 * Modelos de rastreamento do conhecimento.
 *
 * Um modelo PILOTA: calcula o domínio exibido, decide quando a habilidade está
 * consolidada e escolhe a próxima questão. Os demais rodam como SOMBRA: antes de cada
 * resposta registram a probabilidade de acerto que previam e atualizam o próprio estado,
 * sem interferir no treino. Assim dá para comparar depois, com dados reais de uso.
 *
 * Por que o piloto deixou de ser o BKT. No estudo dos confundidores com o ENEM
 * (68 células, 262 milhões de registros), o BKT ficou 0,178 de AUC abaixo do teto
 * psicométrico (TRI 3PL com parâmetros do INEP) em 68 de 68 células, e ainda estimou
 * transição de aprendizagem positiva (mediana p(T) = 0,047) onde não havia nada a
 * aprender: a prova é uma sessão única, sem ensino entre itens. O mesmo estudo mostrou
 * que a vantagem das arquiteturas profundas vem de recalibração de item e de ordem de
 * apresentação, e que as duas mais precisas são justamente as que têm estrutura do lado
 * do item (embeddings estilo Rasch).
 *
 * A conclusão prática: estrutura do lado do item é o que paga. O ENEMWise já tem os
 * parâmetros a, b e c calibrados pelo INEP para cada questão, então o piloto é um Elo
 * online sobre essa estrutura: a habilidade do estudante se move pela surpresa da
 * resposta, com a dificuldade e o chute da questão conhecidos. É o "Elo com Rasch" do
 * DevWise, aqui com parâmetros reais em vez de estimados.
 *
 * Nada disso está validado para este uso: o estudo avaliou previsão sem aprendizagem.
 * Por isso os outros modelos continuam rodando e o log guarda as previsões de todos.
 */
import { pCorrect, posterior, type BktParams } from './bkt'
import { p3pl } from './irt'
import type { Area, Attempt, Item, SkillKey } from './types'

export type ModeloId = 'elo' | 'irt' | 'bkt' | 'pfa' | 'afm'

/**
 * Configuração dos modelos, carimbada no log exportado.
 * Sem ela, uma análise posterior não sabe com que parâmetros as previsões foram feitas,
 * e comparar duas coletas vira comparar coisas diferentes.
 */
export const CONFIG_MODELOS = {
  versao: 1,
  piloto: 'elo' as ModeloId,
  elo: { k0: 0.8, decaimento: 0.06, pesoErro: 0.7, pesoArea: 0.5 },
  bkt: { transicao: 0.12 },
  pfa: { beta: -0.6, gamma: 0.28, rho: -0.10 },
  afm: { beta: -0.6, gamma: 0.12 },
  creditoDica: [1, 0.75, 0.5, 0],
  dominioConsolidado: 0.85,
  confirmacaoEmOutroDia: true,
}

export const MODELOS: { id: ModeloId; nome: string; descricao: string }[] = [
  { id: 'elo', nome: 'Elo com Rasch', descricao: 'Habilidade online sobre os parâmetros do INEP. Piloto.' },
  { id: 'irt', nome: 'TRI 3PL (EAP)', descricao: 'Teto psicométrico do estudo: habilidade por EAP, item fixo.' },
  { id: 'bkt', nome: 'BKT', descricao: 'Modelo clássico de dois estados. Sombra.' },
  { id: 'pfa', nome: 'PFA', descricao: 'Acertos e erros anteriores na habilidade. Sombra.' },
  { id: 'afm', nome: 'AFM', descricao: 'Contagem de oportunidades na habilidade. Sombra.' },
]

/**
 * Elo em dois níveis: a habilidade da ÁREA (o que vira nota) e um desvio por HABILIDADE
 * da Matriz. Sem o desvio, errar geometria derrubaria o domínio de estatística, porque a
 * área é a mesma; sem a área, cada habilidade começaria do zero e ignoraria o que já se
 * sabe do estudante. A previsão usa a soma dos dois.
 */
export interface EstadoElo {
  theta: Record<Area, number>
  n: Record<Area, number>
  hab: Record<SkillKey, number>   // desvio da habilidade em relação à área
  nHab: Record<SkillKey, number>
}
/** PFA e AFM guardam contagens por habilidade. */
export interface Contagens { acertos: Record<SkillKey, number>; erros: Record<SkillKey, number> }

export interface EstadoModelos {
  elo: EstadoElo
  pfa: Contagens
  afm: Contagens
}

export const estadoInicial = (thetaPorArea: Record<Area, number>): EstadoModelos => ({
  elo: { theta: { ...thetaPorArea }, n: { CN: 0, CH: 0, LC: 0, MT: 0 }, hab: {}, nHab: {} },
  pfa: { acertos: {}, erros: {} },
  afm: { acertos: {}, erros: {} },
})

// --- Elo com estrutura de item (Rasch/3PL) ---------------------------------
export const ELO_K0 = 0.8      // passo inicial, na escala de theta (~80 pontos do ENEM)
export const ELO_DEC = 0.06    // o passo encolhe conforme a evidência se acumula
export const ELO_PESO_ERRO = 0.7 // erro pesa menos: distração e cansaço existem

/**
 * A área agrega dezenas de habilidades: ela deve andar devagar. O desvio da habilidade
 * responde ao que acabou de acontecer nela. Por isso a surpresa move a habilidade inteira
 * e a área pela metade, e não o contrário.
 */
export const PESO_AREA = 0.5
export const passoElo = (n: number) => ELO_K0 / (1 + ELO_DEC * n)

export const thetaElo = (e: EstadoElo, area: Area, k: SkillKey) => (e.theta[area] ?? 0) + (e.hab[k] ?? 0)

/** Habilidade nova = antiga + passo × (alvo − previsto), na área e na habilidade. */
export function atualizarElo(e: EstadoElo, area: Area, k: SkillKey, p: number, alvo: number): EstadoElo {
  const peso = alvo >= 0.5 ? 1 : ELO_PESO_ERRO          // erro pesa menos: distração e cansaço existem
  const surpresa = alvo - p
  return {
    theta: { ...e.theta, [area]: (e.theta[area] ?? 0) + passoElo(e.n[area] ?? 0) * peso * PESO_AREA * surpresa },
    n: { ...e.n, [area]: (e.n[area] ?? 0) + 1 },
    hab: { ...e.hab, [k]: (e.hab[k] ?? 0) + passoElo(e.nHab[k] ?? 0) * peso * surpresa },
    nHab: { ...e.nHab, [k]: (e.nHab[k] ?? 0) + 1 },
  }
}

// --- PFA e AFM (família logística) -----------------------------------------
// Coeficientes de projeto, não estimativas: o estudo recomenda recalibrar nos logs reais.
export const PFA = { beta: -0.6, gamma: 0.28, rho: -0.10 }
export const AFM = { beta: -0.6, gamma: 0.12 }
const sigmoide = (z: number) => 1 / (1 + Math.exp(-Math.max(-30, Math.min(30, z))))

export const pPfa = (c: Contagens, k: SkillKey, dif: number) =>
  sigmoide(PFA.beta - dif + PFA.gamma * (c.acertos[k] ?? 0) + PFA.rho * (c.erros[k] ?? 0))

export const pAfm = (c: Contagens, k: SkillKey, dif: number) =>
  sigmoide(AFM.beta - dif + AFM.gamma * ((c.acertos[k] ?? 0) + (c.erros[k] ?? 0)))

export const somar = (c: Contagens, k: SkillKey, correta: boolean): Contagens =>
  correta ? { ...c, acertos: { ...c.acertos, [k]: (c.acertos[k] ?? 0) + 1 } }
          : { ...c, erros: { ...c.erros, [k]: (c.erros[k] ?? 0) + 1 } }

// --- previsões de todos os modelos, antes da resposta ----------------------
export interface Contexto {
  item: Item
  skill: SkillKey
  estado: EstadoModelos
  pL: number            // domínio BKT da habilidade
  params: BktParams     // guess/slip do item, para o BKT
  thetaIrt: number      // habilidade por EAP (teto psicométrico)
  D: number
}

export function previsoes(c: Contexto): Record<ModeloId, number> {
  const { item, skill, estado } = c
  const r4 = (x: number) => Math.round(x * 1e4) / 1e4
  return {
    elo: r4(p3pl(thetaElo(estado.elo, item.area, skill), item.a, item.b, item.c)),
    irt: r4(p3pl(c.thetaIrt, item.a, item.b, item.c)),
    bkt: r4(pCorrect(c.pL, c.params)),
    pfa: r4(pPfa(estado.pfa, skill, item.b)),
    afm: r4(pAfm(estado.afm, skill, item.b)),
  }
}

/** Atualiza os cinco estados com a resposta observada. */
export function atualizarTodos(c: Contexto, correta: boolean, creditoDica = 1): EstadoModelos {
  const peso = Math.max(0, Math.min(1, creditoDica))
  const pElo = p3pl(thetaElo(c.estado.elo, c.item.area, c.skill), c.item.a, c.item.b, c.item.c)
  // acerto com dica vale o crédito da dica: entrega quase pronta não move a habilidade
  const alvo = correta ? peso : 0
  return {
    elo: atualizarElo(c.estado.elo, c.item.area, c.skill, pElo, alvo),
    pfa: somar(c.estado.pfa, c.skill, correta),
    afm: somar(c.estado.afm, c.skill, correta),
  }
}

/** Domínio pelo piloto: chance de acertar um item típico (mediana) da habilidade. */
export function dominioElo(e: EstadoElo, area: Area, skill: SkillKey, itensDaHabilidade: Item[], D: number): number | null {
  if (!itensDaHabilidade.length) return null
  const meds = (xs: number[]) => xs.slice().sort((x, y) => x - y)[Math.floor(xs.length / 2)]
  const b = meds(itensDaHabilidade.map((i) => i.b))
  const a = meds(itensDaHabilidade.map((i) => i.a))
  const c = meds(itensDaHabilidade.map((i) => i.c))
  const p = p3pl(thetaElo(e, area, skill), a, b, c)
  // desconta o chute: o que interessa é o domínio, não o acerto casual
  return Math.max(0, Math.min(1, (p - c) / (1 - c)))
}

/** Erro de Brier por modelo (0 é perfeito), para comparar piloto e sombras no uso real. */
export function brier(tentativas: Attempt[]): { modelo: ModeloId; n: number; brier: number; acerto: number }[] {
  const acc = new Map<ModeloId, { n: number; soma: number; acertos: number }>()
  for (const t of tentativas) {
    for (const [m, p] of Object.entries(t.previsoes ?? {}) as [ModeloId, number][]) {
      const cur = acc.get(m) ?? { n: 0, soma: 0, acertos: 0 }
      cur.n += 1
      cur.soma += ((t.correta ? 1 : 0) - p) ** 2
      cur.acertos += (p >= 0.5) === t.correta ? 1 : 0
      acc.set(m, cur)
    }
  }
  return MODELOS.filter((m) => acc.has(m.id)).map((m) => {
    const a = acc.get(m.id)!
    return { modelo: m.id, n: a.n, brier: a.soma / a.n, acerto: a.acertos / a.n }
  }).sort((x, y) => x.brier - y.brier)
}

/** BKT continua rodando como sombra, com a mesma atualização de antes. */
export const atualizarBkt = (pL: number, correta: boolean, params: BktParams, learn: number) => {
  const post = posterior(pL, correta, params)
  return post + (1 - post) * learn
}
