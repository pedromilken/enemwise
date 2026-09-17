/** TRI 3PL com os parâmetros oficiais do INEP (NU_PARAM_A/B/C). */

// Constante de escala. Confirmar contra a fórmula usada para replicar as notas (meta.D).
let D = 1.0
export const setD = (d: number) => { D = d }

export function p3pl(theta: number, a: number, b: number, c: number): number {
  return c + (1 - c) / (1 + Math.exp(-D * a * (theta - b)))
}

/** Informação de Fisher do item no 3PL. */
export function info3pl(theta: number, a: number, b: number, c: number): number {
  const p = p3pl(theta, a, b, c)
  const q = 1 - p
  return (D * a) ** 2 * (q / p) * ((p - c) / (1 - c)) ** 2
}

const GRID = Array.from({ length: 81 }, (_, i) => -4 + i * 0.1)
const normal = (x: number, m: number, s: number) => Math.exp(-0.5 * ((x - m) / s) ** 2)

export interface ThetaEstimate { mean: number; sd: number }

/** EAP em grade com priori normal. A priori pode vir da banda declarada pelo estudante. */
export function eap(
  obs: { a: number; b: number; c: number; correct: boolean }[],
  priorMean = 0,
  priorSd = 1,
): ThetaEstimate {
  const logw = GRID.map((t) => {
    let lw = Math.log(normal(t, priorMean, priorSd) + 1e-300)
    for (const o of obs) {
      const p = p3pl(t, o.a, o.b, o.c)
      lw += Math.log(o.correct ? p : 1 - p)
    }
    return lw
  })
  const max = Math.max(...logw)
  const w = logw.map((l) => Math.exp(l - max))
  const z = w.reduce((s, x) => s + x, 0)
  const mean = GRID.reduce((s, t, i) => s + t * w[i], 0) / z
  const varr = GRID.reduce((s, t, i) => s + (t - mean) ** 2 * w[i], 0) / z
  return { mean, sd: Math.sqrt(varr) }
}

/** Escala do ENEM (média 500, desvio 100 na referência) <-> theta. */
export const thetaFromScore = (score: number) => (score - 500) / 100
export const scoreFromTheta = (theta: number) => 500 + 100 * theta
