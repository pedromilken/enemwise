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

export const pCorrect = (pL: number, { guess, slip }: BktParams) => pL * (1 - slip) + (1 - pL) * guess

export type Level = 'a construir' | 'em progresso' | 'consolidada'
export const level = (pL: number): Level => (pL >= MASTERY ? 'consolidada' : pL >= 0.5 ? 'em progresso' : 'a construir')
