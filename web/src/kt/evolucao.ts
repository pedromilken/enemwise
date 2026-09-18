/**
 * Evolução: resultados externos registrados pelo estudante (Enem anterior, simulados)
 * lado a lado com a estimativa atual da plataforma e a meta.
 *
 * A estimativa vem do θ por área (EAP na TRI), convertido para a escala do Enem.
 * Comparar com um simulado real é o teste externo mais honesto que o app tem.
 */
import type { Bank } from './engine'
import { theta } from './engine'
import { scoreFromTheta } from './irt'
import { MIN_EVIDENCIA } from './feedback'
import { type Area, AREAS, type ResultadoAnterior, type StudentState } from './types'

export interface PontoEvolucao { data: string; origem: string; nota: number }
export interface EvolucaoArea {
  area: Area
  pontos: PontoEvolucao[]          // do mais antigo ao mais recente
  estimativa: number | null         // nota estimada pela plataforma agora (null sem evidência)
  variacao: number | null           // estimativa menos o último resultado registrado
  ultimo: PontoEvolucao | null
}

export function evolucao(s: StudentState, bank: Bank): EvolucaoArea[] {
  return AREAS.map((area) => {
    const pontos = (s.historico ?? [])
      .filter((h) => typeof h.notas[area] === 'number')
      .map((h) => ({ data: h.data, origem: h.origem, nota: h.notas[area]! }))
      .sort((a, b) => a.data.localeCompare(b.data))
    const n = s.tentativas.filter((t) => bank.byId.get(t.itemId)?.area === area).length
    const estimativa = n >= MIN_EVIDENCIA ? Math.round(scoreFromTheta(theta(s, bank, area).mean)) : null
    const ultimo = pontos.at(-1) ?? null
    return { area, pontos, estimativa, ultimo, variacao: estimativa !== null && ultimo ? estimativa - ultimo.nota : null }
  })
}

/** Nota estimada ao longo dos dias, a partir do θ registrado antes de cada resposta (prequencial). */
export function trajetoria(s: StudentState, bank: Bank, area: Area): { data: string; nota: number }[] {
  const porDia = new Map<string, number>()
  const ts = [...s.tentativas].filter((t) => bank.byId.get(t.itemId)?.area === area && typeof t.thetaAntes === 'number')
  for (const t of ts) porDia.set(new Date(t.ts).toISOString().slice(0, 10), Math.round(scoreFromTheta(t.thetaAntes!)))
  const atual = s.tentativas.filter((t) => bank.byId.get(t.itemId)?.area === area).length >= MIN_EVIDENCIA
    ? Math.round(scoreFromTheta(theta(s, bank, area).mean)) : null
  if (atual !== null) porDia.set(new Date().toISOString().slice(0, 10), atual)
  return [...porDia.entries()].map(([data, nota]) => ({ data, nota })).sort((a, b) => a.data.localeCompare(b.data))
}

export function novoResultado(data: string, origem: string, notas: Partial<Record<Area, number>>): ResultadoAnterior {
  const limpas: Partial<Record<Area, number>> = {}
  for (const a of AREAS) {
    const v = notas[a]
    if (typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1000) limpas[a] = Math.round(v)
  }
  return { id: `${data}-${Math.random().toString(36).slice(2, 8)}`, data, origem: origem.trim() || 'Resultado anterior', notas: limpas }
}
