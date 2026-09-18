import type { StudentState } from './kt/types'

const KEY = 'enemwise:estudante'
const TURMA = 'enemwise:turma'

function read<T>(k: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(k)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}
function write(k: string, v: unknown) {
  try { localStorage.setItem(k, JSON.stringify(v)) } catch { /* armazenamento cheio ou bloqueado */ }
}

export const loadStudent = () => read<StudentState | null>(KEY, null)
export const saveStudent = (s: StudentState | null) => (s ? write(KEY, s) : localStorage.removeItem(KEY))
export const loadTurma = () => read<StudentState[]>(TURMA, [])
export const saveTurma = (t: StudentState[]) => write(TURMA, t)

export function downloadTexto(filename: string, texto: string, tipo: string) {
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob([texto], { type: tipo })), download: filename })
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

export function download(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data)], { type: 'application/json' })
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: filename })
  a.click()
  URL.revokeObjectURL(a.href)
}

export function isStudentState(x: unknown): x is StudentState {
  const s = x as StudentState
  return !!s && s.versao === 1 && typeof s.mastery === 'object' && Array.isArray(s.tentativas)
}
