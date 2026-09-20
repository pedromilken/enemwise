/**
 * Log de pesquisa: uma linha por resposta, de toda a turma, no formato que a análise
 * entre sessões precisa.
 *
 * O primeiro estudo mediu o que a previsão esconde quando não há aprendizagem: prova de
 * sessão única, sem ensino entre itens. O que falta medir é o contrário, e só um tutor
 * em uso pode fornecer: intervalo entre sessões, revisão, esquecimento e retenção. Por isso
 * cada linha traz a previsão dos cinco modelos feita ANTES da resposta, a posição na sessão,
 * o número da sessão e os dias desde a última prática daquela habilidade.
 *
 * Identificação: o nome do estudante não sai daqui. Vai um código estável, derivado do nome,
 * que permite juntar as linhas da mesma pessoa sem identificá-la.
 */
import type { Bank } from './kt/engine'
import { nivelDe } from './kt/engine'
import { CONFIG_MODELOS } from './kt/modelos'
import type { Meta, StudentState } from './kt/types'

/** Código estável e não reversível do estudante (FNV-1a de 32 bits sobre o nome). */
export function codigo(nome: string): string {
  let h = 0x811c9dc5
  for (const ch of nome.trim().toLowerCase()) {
    h ^= ch.charCodeAt(0)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return `e${h.toString(36)}`
}

const COLUNAS = [
  'estudante', 'ts', 'data', 'sessao', 'n_sessao', 'posicao', 'dias_desde_habilidade',
  'item', 'edicao', 'numero', 'area', 'habilidade', 'conteudos', 'item_a', 'item_b', 'item_c',
  'correta', 'resposta', 'gabarito', 'nivel_dica', 'dica_util', 'confianca', 'dificuldade_percebida',
  'p_elo', 'p_irt', 'p_bkt', 'p_pfa', 'p_afm', 'banda_declarada',
] as const

export function logPesquisa(turma: StudentState[], bank: Bank, meta: Meta): string {
  const q = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const nomeConteudo = (id: string) => (meta.conteudos ?? []).find((c) => c.id === id)?.nome ?? id
  const linhas = [COLUNAS.join(';')]
  for (const s of turma) {
    for (const t of s.tentativas) {
      const it = bank.byId.get(t.itemId)
      linhas.push([
        codigo(s.nome), t.ts, new Date(t.ts).toISOString(), t.sessao ?? '', t.nSessao ?? '', t.posicao ?? '',
        t.diasDesdeHabilidade ?? '', t.itemId, it?.ano ?? '', it?.numero ?? '', it?.area ?? '', it?.habilidade ?? '',
        (it?.topicos ?? []).map(nomeConteudo).join(' | '), it?.a ?? '', it?.b ?? '', it?.c ?? '',
        t.correta ? 1 : 0, t.resposta, it?.gabarito ?? '', nivelDe(t), t.dicaUtil ?? '', t.confianca ?? '',
        t.dificuldade ?? '', t.previsoes?.elo ?? '', t.previsoes?.irt ?? '', t.previsoes?.bkt ?? '',
        t.previsoes?.pfa ?? '', t.previsoes?.afm ?? '', s.banda,
      ].map(q).join(';'))
    }
  }
  return '\ufeff' + linhas.join('\r\n')
}

/** Carimbo da configuração: sem ele, duas coletas não são comparáveis. */
export function configPesquisa(turma: StudentState[], meta: Meta) {
  const tentativas = turma.flatMap((s) => s.tentativas)
  const sessoes = new Set(tentativas.map((t) => t.sessao).filter(Boolean))
  return {
    gerado_em: new Date().toISOString(),
    fonte_do_banco: meta.fonte,
    edicoes: meta.edicoes,
    D: meta.D,
    modelos: CONFIG_MODELOS,
    estudantes: turma.length,
    respostas: tentativas.length,
    sessoes: sessoes.size,
    com_previsoes: tentativas.filter((t) => t.previsoes).length,
    com_intervalo: tentativas.filter((t) => typeof t.diasDesdeHabilidade === 'number').length,
  }
}
