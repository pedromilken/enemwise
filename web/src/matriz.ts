/** Matriz de Referência do Enem (INEP): áreas, competências, habilidades e eixos cognitivos. */
import dados from './data/matriz.json'
import { type Area, skillKey, type SkillKey } from './kt/types'

export interface Competencia { numero: number; descricao: string; habilidades: number[] }
export interface HabilidadeMatriz { descricao: string; competencia: number; bloom?: string | null }
interface AreaMatriz { nome: string; competencias: Competencia[]; habilidades: Record<string, HabilidadeMatriz> }

export const MATRIZ = dados as unknown as {
  fonte: string
  eixos: { sigla: string; nome: string; descricao: string }[]
  areas: Record<Area, AreaMatriz>
}

export const habilidade = (area: Area, h: number): HabilidadeMatriz | undefined => MATRIZ.areas[area]?.habilidades[String(h)]
export const competenciaDe = (area: Area, h: number): Competencia | undefined =>
  MATRIZ.areas[area]?.competencias.find((c) => c.habilidades.includes(h))

export function descricoesDaMatriz() {
  const descricoes: Record<string, string> = {}
  const bloom: Record<string, string> = {}
  for (const [area, a] of Object.entries(MATRIZ.areas) as [Area, AreaMatriz][]) {
    for (const [h, v] of Object.entries(a.habilidades)) {
      const k: SkillKey = skillKey(area, Number(h))
      descricoes[k] = v.descricao
      if (v.bloom) bloom[k] = `${v.bloom} (sugerido)`
    }
  }
  return { descricoes, bloom }
}
