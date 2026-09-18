import type { Item } from './kt/types'

/**
 * Tutor opcional com LLM, modo "traga sua chave".
 * GitHub Pages é estático: não há servidor para guardar segredo. A chave fica no
 * sessionStorage deste navegador e vai direto para a API, nunca para o repositório.
 */
const K = 'enemwise:llm'
export interface LlmConfig { apiKey: string; model: string }
export const DEFAULT_MODEL = 'claude-sonnet-5'

export const getConfig = (): LlmConfig | null => {
  try { return JSON.parse(sessionStorage.getItem(K) ?? 'null') } catch { return null }
}
export const setConfig = (c: LlmConfig | null) =>
  c ? sessionStorage.setItem(K, JSON.stringify(c)) : sessionStorage.removeItem(K)

const questao = (it: Item) =>
  `${it.enunciado}\n${(it.descricao ?? []).join('\n')}\n` +
  (it.alternativas ?? []).map((a, i) => `${'ABCDE'[i]}) ${a}`).join('\n')

export type NivelDica = 1 | 2 | 3

export const NIVEIS_DICA: Record<NivelDica, { rotulo: string; credito: string }> = {
  1: { rotulo: 'Dica leve: o que a questão pede', credito: '75%' },
  2: { rotulo: 'Dica média: o caminho', credito: '50%' },
  3: { rotulo: 'Quase a resposta', credito: '0%' },
}

const INSTRUCAO: Record<NivelDica, string> = {
  1: 'Dê UMA dica leve (até 2 frases): diga que conceito ou habilidade a questão cobra e o que ela está pedindo, sem indicar caminho de resolução nem falar de alternativas.',
  2: 'Dê uma dica média (até 3 frases): aponte o caminho de resolução, o primeiro passo e a informação do enunciado que importa. Não revele a alternativa correta.',
  3: 'Dê uma dica forte (até 4 frases): conduza a resolução quase até o fim, deixando apenas o último passo para o estudante. Pode dizer quais alternativas NÃO fazem sentido e por quê, mas não nomeie a correta.',
}

export function prompt(kind: 'dica' | 'explicacao', it: Item, resposta?: string, nivel: NivelDica = 1) {
  const base = `Você é tutor de ENEM para estudantes do ensino médio brasileiro. Área ${it.area}, habilidade H${it.habilidade} da Matriz de Referência.`
  return kind === 'dica'
    ? `${base}\n${INSTRUCAO[nivel]}\n\n${questao(it)}`
    : `${base}\nO estudante marcou ${resposta}. O gabarito é ${it.gabarito}. Explique em até 6 frases por que o gabarito está correto e, se ele errou, qual raciocínio provavelmente levou à alternativa marcada.\n\n${questao(it)}`
}

export async function ask(cfg: LlmConfig, text: string): Promise<string> {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': cfg.apiKey,
      'anthropic-version': '2023-06-01',
      'anthropic-dangerous-direct-browser-access': 'true',
    },
    body: JSON.stringify({ model: cfg.model, max_tokens: 600, messages: [{ role: 'user', content: text }] }),
  })
  if (!r.ok) throw new Error(`A API respondeu ${r.status}. Confira a chave e o modelo.`)
  const data = await r.json()
  return data.content.map((b: { type: string; text?: string }) => (b.type === 'text' ? b.text : '')).join('\n')
}

/** Dica sem IA: elimina alternativas erradas, em ordem estável por questão. */
export function eliminar(it: Item, quantas = 1): string[] {
  const erradas = [...'ABCDE'].filter((l) => l !== it.gabarito)
  const inicio = it.co_item % erradas.length
  return Array.from({ length: Math.min(quantas, erradas.length) }, (_, i) => erradas[(inicio + i) % erradas.length])
}

/** Dica sem IA por nível: descrição da habilidade, depois eliminação progressiva. */
export function dicaLocal(it: Item, nivel: NivelDica, descricaoHabilidade?: string, conteudo?: string): string {
  if (nivel === 1) {
    const partes = [conteudo ? `Conteúdo: ${conteudo}.` : '', descricaoHabilidade ? `A questão pede para ${descricaoHabilidade.charAt(0).toLowerCase()}${descricaoHabilidade.slice(1)}` : '']
    return partes.filter(Boolean).join(' ') || 'Releia o comando da questão: o que exatamente está sendo pedido?'
  }
  const n = nivel === 2 ? 1 : 3
  const el = eliminar(it, n)
  return n === 1 ? `A alternativa ${el[0]} não é a correta.` : `As alternativas ${el.join(', ')} não são a correta. Sobram duas.`
}

/**
 * Página da resolução comentada do Curso Objetivo para a prova da questão (site externo).
 * O ENEMWise não copia o texto, que é obra do Objetivo; só aponta para ele.
 * Dia da prova: de 2009 a 2016, CH e CN no 1º dia; a partir de 2017, LC e CH no 1º dia.
 */
export function linkObjetivo(it: Item): string | null {
  if (it.ano < 2009 || (it.aplicacao ?? 1) !== 1) return null
  const primeiroDia = it.ano <= 2016 ? ['CH', 'CN'] : ['LC', 'CH']
  const dia = primeiroDia.includes(it.area) ? 1 : 2
  const sufixo = it.ano === 2020 ? '_presencial' : ''
  return `https://www.curso-objetivo.br/vestibular/resolucao-comentada/enem/enem${it.ano}_${dia}dia${sufixo}.aspx`
}

/** Link para relatar problema na questão: abre uma issue já preenchida no repositório. */
export function linkRelato(it: Item, repo = 'pedromilken/enemwise'): string {
  const titulo = `Problema na questão ${it.numero ?? ''} do ENEM ${it.ano} (${it.area}, id ${it.id})`
  const corpo = `**Questão:** ENEM ${it.ano}, nº ${it.numero ?? '?'}, área ${it.area}, habilidade H${it.habilidade}, id \`${it.id}\`\n\n**O que está errado:** (texto cortado, fórmula ilegível, gabarito, imagem faltando...)\n\n**Como deveria ser:**`
  return `https://github.com/${repo}/issues/new?title=${encodeURIComponent(titulo)}&body=${encodeURIComponent(corpo)}&labels=quest%C3%A3o`
}
