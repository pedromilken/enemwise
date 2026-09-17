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

export function prompt(kind: 'dica' | 'explicacao', it: Item, resposta?: string) {
  const base = `Você é tutor de ENEM para estudantes do ensino médio brasileiro. Área ${it.area}, habilidade H${it.habilidade} da Matriz de Referência.`
  return kind === 'dica'
    ? `${base}\nDê UMA dica curta (até 3 frases) que ajude a raciocinar. Não revele a alternativa correta nem elimine alternativas explicitamente.\n\n${questao(it)}`
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

/** Dica sem IA: elimina uma alternativa errada, escolhida de forma estável. */
export function eliminar(it: Item): string {
  const erradas = [...'ABCDE'].filter((l) => l !== it.gabarito)
  return erradas[it.co_item % erradas.length]
}
