/**
 * Mescla do progresso local com o da nuvem.
 *
 * As tentativas são a fonte da verdade; o domínio é recalculado repassando todas em
 * ordem cronológica. Assim, treinar no celular e no computador soma, sem sobrescrever.
 */
import { aplicarTentativa, type Bank, newStudent } from './engine'
import type { Attempt, StudentState } from './types'

const chave = (t: Attempt) => `${t.itemId}|${t.ts}`

export function mesclar(bank: Bank, local: StudentState | null, remoto: StudentState | null): StudentState | null {
  if (!local) return remoto
  if (!remoto) return local
  const base = (remoto.atualizadoEm ?? 0) >= (local.atualizadoEm ?? 0) ? remoto : local
  const todas = new Map<string, Attempt>()
  for (const t of [...remoto.tentativas, ...local.tentativas]) {
    const atual = todas.get(chave(t))
    todas.set(chave(t), atual ? { ...atual, confianca: atual.confianca ?? t.confianca } : t)
  }
  const ordenadas = [...todas.values()].sort((a, b) => a.ts - b.ts)
  let s: StudentState = {
    ...newStudent(bank, base.nome, base.banda),
    meta: base.meta, dono: remoto.dono ?? local.dono, atualizadoEm: base.atualizadoEm,
  }
  for (const t of ordenadas) s = aplicarTentativa(s, bank, t)
  return s
}

/** Progresso local de outra pessoa (ou sem dono) não deve ser juntado sem perguntar. */
export function precisaConfirmarVinculo(local: StudentState | null, userId: string): boolean {
  return !!local && local.tentativas.length > 0 && local.dono !== userId
}
