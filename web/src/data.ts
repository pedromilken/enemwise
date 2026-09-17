import type { Item, Meta, SkillPrior } from './kt/types'

const url = (f: string) => `${import.meta.env.BASE_URL}data/${f}`

async function getJson<T>(f: string): Promise<T> {
  const r = await fetch(url(f))
  if (!r.ok) throw new Error(`Não foi possível carregar ${f} (${r.status}). Gere os dados com o pipeline.`)
  return r.json() as Promise<T>
}

/**
 * Habilidades da Matriz de Referência (opcional): data/habilidades.json
 *   {"MT-H17": "texto"}  ou  {"MT-H17": {"descricao": "texto", "bloom": "Aplicação", "bloom_sugerido": true}}
 */
export type Descricoes = Record<string, string>
type Bruto = Record<string, string | { descricao?: string; bloom?: string; bloom_sugerido?: boolean }>

function normalizar(raw: Bruto) {
  const descricoes: Descricoes = {}
  const bloom: Record<string, string> = {}
  for (const [k, v] of Object.entries(raw)) {
    if (typeof v === 'string') descricoes[k] = v
    else {
      if (v.descricao) descricoes[k] = v.descricao
      if (v.bloom) bloom[k] = v.bloom + (v.bloom_sugerido ? ' (sugerido)' : '')
    }
  }
  return { descricoes, bloom }
}

export async function loadBundle() {
  const meta = await getJson<Meta>('meta.json')
  const [shards, priors, descricoes] = await Promise.all([
    Promise.all(meta.edicoes_com_texto.map((ano) => getJson<Item[]>(`items/${ano}.json`))),
    getJson<SkillPrior[]>('priors.json'),
    getJson<Bruto>('habilidades.json').catch(() => ({}) as Bruto),
  ])
  return { meta, items: shards.flat(), priors, ...normalizar(descricoes) }
}
