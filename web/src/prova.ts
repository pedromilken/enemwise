/**
 * Simulado (modo prova): a 1ª etapa do ENEM como foi aplicada em cada edição.
 * Os dados vêm de data/prova/ (gerados por tools/modo-prova/exportar_web.py) e são os MESMOS usados pelos agentes do
 * modo prova: mesma ordem de cada cor de caderno, mesmo texto, mesmo gabarito, mesma duração oficial.
 */
import type { Area } from './kt/types'

export interface DiaProva { dia: number; data?: string; duracao_min: number; redacao: boolean; areas: Area[]; cores?: string[] }
export interface ItemCaderno {
  pos: number; area: Area; co_item: number; co_prova: number; lingua: 'ingles' | 'espanhol' | null
  gab: string; anulado: boolean; hab: number | null; a: number | null; b: number | null; c: number | null
}
export interface TextoItem { enunciado: string; alternativas: string[]; descricao: string[] }
export interface EdicaoProva {
  ano: number; dias: DiaProva[]
  cadernos: Record<string, { cor: string; itens: ItemCaderno[] }[]>
  itens: Record<string, TextoItem>
}
export interface IndiceProva { versao: number; anos: { ano: number; dias: DiaProva[] }[] }

/** Uma prova em andamento ou entregue. Fica no navegador até ser descartada. */
export interface Sessao {
  id: string
  ano: number
  dia: number
  cor: string
  lingua: 'ingles' | 'espanhol'
  reservaRedacao: number            // minutos reservados para a redação (0 se o dia não tem redação ou se o estudante tirou)
  inicio: number                    // epoch ms
  limite: number                    // epoch ms em que o tempo acaba
  atual: number                     // índice da questão aberta
  respostas: Record<number, string> // índice -> letra
  revisar: number[]                 // índices marcados para revisão
  tempoMs: Record<number, number>   // índice -> tempo com a questão aberta
  visitas: Record<number, number>
  entregue: number | null           // epoch ms da entrega (ou do fim do tempo)
  motivo?: 'entregou' | 'tempo'
  contouNoTreino?: boolean
}

const url = (f: string) => `${import.meta.env.BASE_URL}data/prova/${f}`
const cache = new Map<number, Promise<EdicaoProva>>()

export async function carregarIndice(): Promise<IndiceProva> {
  const r = await fetch(url('index.json'))
  if (!r.ok) throw new Error('O simulado ainda não foi gerado (data/prova/index.json). Rode tools/modo-prova/exportar_web.py.')
  return r.json()
}
export function carregarEdicao(ano: number): Promise<EdicaoProva> {
  if (!cache.has(ano)) cache.set(ano, fetch(url(`${ano}.json`)).then((r) => { if (!r.ok) throw new Error(`Edição ${ano} indisponível`); return r.json() }))
  return cache.get(ano)!
}

/** Itens do caderno na ordem impressa, só a língua escolhida nas cinco primeiras de LC. */
export function itensDoCaderno(ed: EdicaoProva, s: Pick<Sessao, 'dia' | 'cor' | 'lingua'>): ItemCaderno[] {
  const c = (ed.cadernos[String(s.dia)] ?? []).find((x) => x.cor === s.cor)
  return (c?.itens ?? []).filter((i) => !i.lingua || i.lingua === s.lingua).sort((a, b) => a.pos - b.pos)
}

const KEY = 'enemwise:simulado'
export function lerSessoes(): Sessao[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') as Sessao[] } catch { return [] }
}
export function gravarSessoes(s: Sessao[]) {
  try { localStorage.setItem(KEY, JSON.stringify(s)) } catch { /* armazenamento cheio ou bloqueado */ }
}

/** Nota estimada: EAP do 3PL com os parâmetros do INEP (D = 1,7), escala 500 + 100θ; itens anulados ficam de fora. */
export function notaEAP(resp: { a: number | null; b: number | null; c: number | null; correta: boolean | null }[]): number | null {
  let num = 0, den = 0, usados = 0
  for (let k = 0; k <= 80; k++) {
    const th = -4 + k * 0.1
    let lp = -th * th / 2
    for (const r of resp) {
      if (r.correta === null || r.a === null || r.b === null || r.c === null) continue
      const p = r.c + (1 - r.c) / (1 + Math.exp(-1.7 * r.a * (th - r.b)))
      lp += r.correta ? Math.log(p) : Math.log(1 - p)
      if (k === 0) usados++
    }
    const w = Math.exp(lp); num += th * w; den += w
  }
  return usados && den > 0 ? Math.round(500 + 100 * num / den) : null
}

export const fmtTempo = (ms: number) => {
  const t = Math.max(0, Math.floor(ms / 1000)), h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60
  return (h ? `${h}h` : '') + `${String(m).padStart(h ? 2 : 1, '0')}min` + (h ? '' : ` ${String(s).padStart(2, '0')}s`)
}
