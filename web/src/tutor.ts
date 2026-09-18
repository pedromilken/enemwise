import type { Item } from './kt/types'

/**
 * Tutor opcional com LLM, modo "traga sua chave", com qualquer provedor.
 * GitHub Pages é estático: não há servidor para guardar segredo. A chave fica no
 * sessionStorage deste navegador e vai direto para a API do provedor escolhido,
 * nunca para o repositório.
 *
 * Quase todos falam o dialeto de "chat completions" da OpenAI; a Anthropic e o Google
 * têm formato próprio. Os três estão cobertos abaixo, e "Outro (compatível)" aceita
 * qualquer serviço que siga o dialeto da OpenAI, inclusive um local.
 */
const K = 'enemwise:llm'

export type Provedor = 'anthropic' | 'openai' | 'google' | 'compativel'

export interface ProvedorInfo {
  id: Provedor
  nome: string
  modeloPadrao: string
  exemplos: string
  endpointFixo?: string
  ajuda: string
  chaveEm: string
}

export const PROVEDORES: ProvedorInfo[] = [
  { id: 'anthropic', nome: 'Anthropic (Claude)', modeloPadrao: 'claude-sonnet-5',
    exemplos: 'claude-sonnet-5, claude-haiku-4-5-20251001', chaveEm: 'console.anthropic.com',
    ajuda: 'A chave começa com sk-ant-.' },
  { id: 'openai', nome: 'OpenAI (GPT)', modeloPadrao: 'gpt-4o-mini',
    exemplos: 'gpt-4o-mini, gpt-4o, o4-mini', chaveEm: 'platform.openai.com',
    ajuda: 'A chave começa com sk-.' },
  { id: 'google', nome: 'Google (Gemini)', modeloPadrao: 'gemini-2.5-flash',
    exemplos: 'gemini-2.5-flash, gemini-2.5-pro', chaveEm: 'aistudio.google.com',
    ajuda: 'Pegue a chave no Google AI Studio.' },
  { id: 'compativel', nome: 'Outro compatível com OpenAI', modeloPadrao: '',
    exemplos: 'deepseek-chat, qwen-plus, llama-3.3-70b, modelos locais', chaveEm: 'seu provedor',
    ajuda: 'Informe o endereço base da API, por exemplo https://api.deepseek.com/v1 ou https://dashscope-intl.aliyuncs.com/compatible-mode/v1.' },
]

export interface LlmConfig { provedor: Provedor; apiKey: string; model: string; baseUrl?: string }
export const DEFAULT_MODEL = 'claude-sonnet-5'

export const getConfig = (): LlmConfig | null => {
  try {
    const c = JSON.parse(sessionStorage.getItem(K) ?? 'null')
    return c && typeof c === 'object' ? { provedor: 'anthropic', ...c } : null   // configs antigas não tinham provedor
  } catch { return null }
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

const SEM_ENFEITE = 'Comece direto pelo conteúdo, sem saudação e sem se apresentar. Texto corrido, sem markdown, sem asteriscos, sem títulos.'

const INSTRUCAO: Record<NivelDica, string> = {
  1: `Dê UMA dica leve, em 2 frases completas: diga que conceito a questão cobra e o que ela pede. Não indique caminho de resolução nem fale de alternativas. ${SEM_ENFEITE}`,
  2: `Dê uma dica média, em até 3 frases completas: aponte o caminho, o primeiro passo e a informação do enunciado que importa. Não revele a alternativa correta. ${SEM_ENFEITE}`,
  3: `Dê uma dica forte, em até 4 frases completas: conduza o raciocínio quase até o fim, deixando o último passo para o estudante. Pode dizer quais alternativas não fazem sentido e por quê, mas não nomeie a correta. ${SEM_ENFEITE}`,
}

/** Modelos insistem em markdown mesmo quando o pedido proíbe; tiramos os enfeites que sobram. */
export function limpar(texto: string): string {
  return texto
    .replace(/\*\*(.+?)\*\*/gs, '$1')
    .replace(/(^|\s)\*(\S.*?\S)\*(?=\s|$)/gs, '$1$2')
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/^\s*[-*]\s+/gm, '• ')
    .replace(/^(olá|ola|oi|fala|e aí|eai|beleza)[^.!?\n]*[.!?]\s*/i, '')
    .trim()
}

const EXPLICACAO = `Escreva a resolução comentada, em português do Brasil, para quem acabou de responder. Sem saudação e sem se apresentar:

1. Comece dizendo o que a questão pede e qual conceito resolve.
2. Mostre o raciocínio passo a passo até o gabarito. Em matemática e ciências, faça as contas.
3. Diga, em uma frase cada, por que as alternativas erradas são tentadoras. Se o estudante errou, comece pela que ele marcou.
4. Termine com "Para lembrar:" e uma frase com a ideia que resolve questões parecidas.

Parágrafos curtos separados por linha em branco. Sem markdown, sem títulos, sem asteriscos. Escreva direto para o estudante, sem saudação.`

export function prompt(kind: 'dica' | 'explicacao', it: Item, resposta?: string, nivel: NivelDica = 1) {
  const base = `Você é tutor de ENEM para estudantes do ensino médio brasileiro. Área ${it.area}, habilidade H${it.habilidade} da Matriz de Referência.`
  return kind === 'dica'
    ? `${base}\n${INSTRUCAO[nivel]}\n\n${questao(it)}`
    : `${base}\nO estudante marcou ${resposta ?? '?'}; o gabarito é ${it.gabarito}.\n${EXPLICACAO}\n\n${questao(it)}`
}

/** Monta requisição e leitura da resposta conforme o provedor. */
const MAX_SAIDA = 1500
const CORTADA = '\n\n[A resposta foi cortada pelo limite do provedor. Peça de novo ou escolha outro modelo.]'

export function requisicao(cfg: LlmConfig, text: string): { url: string; init: RequestInit; ler: (d: unknown) => string } {
  const corpo = (o: object) => JSON.stringify(o)
  if (cfg.provedor === 'anthropic') {
    return {
      url: 'https://api.anthropic.com/v1/messages',
      init: {
        method: 'POST',
        headers: { 'content-type': 'application/json', 'x-api-key': cfg.apiKey,
                   'anthropic-version': '2023-06-01', 'anthropic-dangerous-direct-browser-access': 'true' },
        body: corpo({ model: cfg.model, max_tokens: MAX_SAIDA, messages: [{ role: 'user', content: text }] }),
      },
      ler: (d) => {
        const r = d as { content?: { type: string; text?: string }[]; stop_reason?: string }
        const t = (r.content ?? []).map((b) => (b.type === 'text' ? b.text ?? '' : '')).join('\n').trim()
        return r.stop_reason === 'max_tokens' ? t + CORTADA : t
      },
    }
  }
  if (cfg.provedor === 'google') {
    return {
      url: `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(cfg.model)}:generateContent`,
      init: {
        method: 'POST',
        headers: { 'content-type': 'application/json', 'x-goog-api-key': cfg.apiKey },
        // thinkingBudget 0: sem isso, o "pensamento" do Gemini consome o limite e a resposta chega cortada
        body: corpo({ contents: [{ parts: [{ text }] }],
                      generationConfig: { maxOutputTokens: MAX_SAIDA, thinkingConfig: { thinkingBudget: 0 } } }),
      },
      ler: (d) => {
        const c = (d as { candidates?: { content?: { parts?: { text?: string }[] }; finishReason?: string }[] }).candidates?.[0]
        const t = (c?.content?.parts ?? []).map((p) => p.text ?? '').join('\n').trim()
        return c?.finishReason === 'MAX_TOKENS' ? t + CORTADA : t
      },
    }
  }
  const base = (cfg.provedor === 'openai' ? 'https://api.openai.com/v1' : (cfg.baseUrl ?? '').replace(/\/+$/, ''))
  return {
    url: `${base}/chat/completions`,
    init: {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${cfg.apiKey}` },
      // OpenAI: modelos de raciocínio recusam max_tokens; os compatíveis (DeepSeek, Qwen) usam max_tokens
      body: corpo(cfg.provedor === 'openai'
        ? { model: cfg.model, max_completion_tokens: MAX_SAIDA, messages: [{ role: 'user', content: text }] }
        : { model: cfg.model, max_tokens: MAX_SAIDA, messages: [{ role: 'user', content: text }] }),
    },
    ler: (d) => {
      const c = (d as { choices?: { message?: { content?: string }; finish_reason?: string }[] }).choices?.[0]
      const t = (c?.message?.content ?? '').trim()
      return c?.finish_reason === 'length' ? t + CORTADA : t
    },
  }
}

export async function ask(cfg: LlmConfig, text: string): Promise<string> {
  if (cfg.provedor === 'compativel' && !cfg.baseUrl) throw new Error('Informe o endereço base da API do seu provedor.')
  const { url, init, ler } = requisicao(cfg, text)
  let r: Response
  try {
    r = await fetch(url, init)
  } catch {
    // provedores sem CORS liberado bloqueiam a chamada direta do navegador
    throw new Error('Não foi possível falar com o provedor. Ele pode não permitir chamadas direto do navegador (CORS).')
  }
  if (!r.ok) {
    const detalhe = r.status === 401 || r.status === 403 ? 'Confira a chave.'
      : r.status === 404 ? 'Confira o nome do modelo e, se for o caso, o endereço base.'
      : r.status === 429 ? 'Limite de uso atingido; espere um pouco.' : 'Confira a chave e o modelo.'
    throw new Error(`A API respondeu ${r.status}. ${detalhe}`)
  }
  const texto = limpar(ler(await r.json()))
  if (!texto) throw new Error('O provedor respondeu sem texto. Tente outro modelo.')
  return texto
}

/** Dica sem IA: elimina alternativas erradas, em ordem estável por questão. */
export function eliminar(it: Item, quantas = 1): string[] {
  const erradas = [...'ABCDE'].filter((l) => l !== it.gabarito)
  const inicio = it.co_item % erradas.length
  return Array.from({ length: Math.min(quantas, erradas.length) }, (_, i) => erradas[(inicio + i) % erradas.length])
}

/** Estratégia por área, para a dica sem IA dizer algo além de eliminar alternativas. */
const ESTRATEGIA: Record<string, string> = {
  LC: 'Volte ao trecho e procure a palavra do comando (finalidade, crítica, efeito de sentido): a resposta costuma estar colada a ela.',
  CH: 'Situe o documento no tempo e pergunte a quem ele serve; alternativas com termos absolutos costumam extrapolar o texto.',
  CN: 'Escreva os dados com unidades e identifique a grandeza pedida antes de escolher a fórmula ou o processo.',
  MT: 'Anote o que a pergunta pede, converta as unidades e estime a ordem de grandeza: isso já elimina alternativas.',
}

/**
 * Dica sem IA, por nível: conteúdo e habilidade, depois competência e estratégia da área,
 * e por fim eliminação de alternativas. Cada nível acrescenta algo novo, não só mais eliminação.
 */
export function dicaLocal(it: Item, nivel: NivelDica, descricaoHabilidade?: string, conteudo?: string,
                          competencia?: string): string {
  if (nivel === 1) {
    const partes = [conteudo ? `Conteúdo: ${conteudo}.` : '',
                    descricaoHabilidade ? `A questão pede para ${descricaoHabilidade.charAt(0).toLowerCase()}${descricaoHabilidade.slice(1)}` : '']
    return partes.filter(Boolean).join(' ') || 'Releia o comando da questão: o que exatamente está sendo pedido?'
  }
  if (nivel === 2) {
    const partes = [competencia ? `Competência cobrada: ${competencia}` : '', ESTRATEGIA[it.area] ?? '',
                    `Uma alternativa que não serve: ${eliminar(it, 1)[0]}.`]
    return partes.filter(Boolean).join(' ')
  }
  const el = eliminar(it, 3)
  return `Sobram duas alternativas: as outras três (${el.join(', ')}) não respondem ao que foi pedido. Compare as que restaram com o comando da questão, palavra por palavra.`
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
