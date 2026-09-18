export type Area = 'CN' | 'CH' | 'LC' | 'MT'
export const AREAS: Area[] = ['LC', 'CH', 'CN', 'MT']

export interface Item {
  id: string
  co_item: number
  ano: number
  area: Area
  habilidade: number
  a: number
  b: number
  c: number
  gabarito: string
  p_banda?: (number | null)[]
  numero?: number
  topicos?: string[]
  enunciado?: string
  alternativas?: string[]
  descricao?: string[]
  figuras?: string[]
}

export interface SkillPrior {
  area: Area
  habilidade: number
  banda: number
  banda_label: string
  n: number
  p_acerto: number
  guess: number
  slip: number
  p_l0: number
  p_l0_sd?: number
  n_edicoes?: number
}

/** Conteúdo programático (geometria analítica, genética...), do catálogo gerado no pipeline. */
export interface Conteudo {
  id: string
  nome: string
  area: Area
  disciplina: string
}

export interface Meta {
  gerado_em: string
  sintetico: boolean
  D: number
  areas: Record<Area, string>
  bandas: string[]
  edicoes: number[]
  edicoes_com_texto: number[]
  n_itens_com_texto: number
  conteudos?: Conteudo[]
  cobertura_conteudos?: { area: Area; itens: number; com_topico: number; cobertura: number }[]
  auditoria_reprovada: string[]
  fonte: string
}

export type Confianca = 'chute' | 'duvida' | 'certeza'

export interface Attempt {
  itemId: string
  resposta: string
  correta: boolean
  usouDica: boolean
  /** 0 = sem dica; 1 = conceito; 2 = caminho; 3 = quase resposta. Ausente em registros antigos (= usouDica ? 3 : 0). */
  nivelDica?: 0 | 1 | 2 | 3
  ts: number
  // Registro prequencial: o que o modelo apostava ANTES da resposta.
  // É o que permite avaliar o modelo sem vazamento (ver pipeline/avaliacao.py).
  pPrevisto?: number
  pLAntes?: number
  thetaAntes?: number
  pBanda?: number
  // Medida indireta (autoavaliação): separa acerto por chute de acerto com domínio.
  confianca?: Confianca
}

/** Habilidade 0: o INEP não informou CO_HABILIDADE para o item. */
export const nomeHabilidade = (h: number | string) => (Number(h) === 0 ? 'habilidade não informada' : `H${h}`)

export type SkillKey = `${Area}-H${number}`
export const skillKey = (area: Area, h: number): SkillKey => `${area}-H${h}`

export interface StudentState {
  versao: 1
  nome: string
  banda: number
  meta?: number // nota-alvo na escala do ENEM (ex.: nota de corte do curso desejado)
  mastery: Record<SkillKey, number>
  tentativas: Attempt[]
  dono?: string        // id do usuário na nuvem a quem este progresso pertence
  atualizadoEm?: number // última alteração de nome, faixa ou meta (desempate na sincronia)
}
