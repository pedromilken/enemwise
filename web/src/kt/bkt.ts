/**
 * BKT por habilidade da Matriz de Referência, com guess por item.
 *
 * Analogia: o P(L) é um termômetro; cada resposta é uma medição ruidosa.
 * Guess e slip dizem o quanto confiar no termômetro. Aqui o guess de cada questão
 * vem do parâmetro c da TRI, então chutar certo numa questão "chutável" pesa menos.
 */
export interface BktParams { guess: number; slip: number; learn: number }

// P(T) não é identificável no ENEM (sem aprendizagem intercalada). Valor inicial,
// a ser reajustado com os logs de uso do próprio ENEMWise.
export const DEFAULT_LEARN = 0.12
export const MASTERY = 0.95

export function posterior(pL: number, correct: boolean, { guess, slip }: BktParams): number {
  const num = correct ? pL * (1 - slip) : pL * slip
  const den = correct ? num + (1 - pL) * guess : num + (1 - pL) * (1 - guess)
  return den === 0 ? pL : num / den
}

export function update(pL: number, correct: boolean, params: BktParams): number {
  const post = posterior(pL, correct, params)
  return post + (1 - post) * params.learn
}

/**
 * Crédito de um acerto conforme o nível de dica usado. Nível 0: acerto pleno.
 * Nível 3 é quase a resposta, então vale como erro: o modelo não aprende nada sobre domínio.
 */
export const CREDITO_DICA = [1, 0.75, 0.5, 0] as const

/**
 * Atualização com crédito parcial: mistura do posterior "acertou" com o posterior "errou",
 * pesada pelo crédito. É a forma mais simples de dizer "provavelmente sabia, mas não por si só".
 */
export function updateParcial(pL: number, correct: boolean, credito: number, params: BktParams): number {
  if (!correct) return update(pL, false, params)
  const w = Math.max(0, Math.min(1, credito))
  return w * update(pL, true, params) + (1 - w) * update(pL, false, params)
}

export const pCorrect = (pL: number, { guess, slip }: BktParams) => pL * (1 - slip) + (1 - pL) * guess

export type Level = 'a construir' | 'em progresso' | 'consolidada'
export const level = (pL: number): Level => (pL >= MASTERY ? 'consolidada' : pL >= 0.5 ? 'em progresso' : 'a construir')
