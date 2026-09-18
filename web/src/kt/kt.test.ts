import { describe, expect, it } from 'vitest'
import { posterior, update } from './bkt'
import { makeBank, newStudent, nextItem, record, setConfianca } from './engine'
import { itensParaRevisar, phi, risco } from './feedback'
import { eap, info3pl, p3pl } from './irt'
import type { Item, SkillPrior } from './types'

const item = (id: string, h: number, b: number, c = 0.2): Item => ({
  id, co_item: Number(id), ano: 2099, area: 'MT', habilidade: h, a: 2, b, c, gabarito: 'A',
  enunciado: 'x', alternativas: ['1', '2', '3', '4', '5'],
})

describe('TRI', () => {
  it('p3pl respeita o piso de acerto casual', () => {
    expect(p3pl(-10, 2, 0, 0.2)).toBeCloseTo(0.2, 3)
    expect(p3pl(0, 2, 0, 0.2)).toBeCloseTo(0.6, 5)
  })
  it('informação é máxima perto da dificuldade', () => {
    expect(info3pl(0.2, 2, 0, 0.2)).toBeGreaterThan(info3pl(2.5, 2, 0, 0.2))
  })
  it('EAP sobe com acertos em itens difíceis', () => {
    const hard = { a: 2, b: 1.5, c: 0.2 }
    expect(eap(Array(6).fill({ ...hard, correct: true })).mean).toBeGreaterThan(eap(Array(6).fill({ ...hard, correct: false })).mean)
  })
})

describe('BKT', () => {
  const p = { guess: 0.2, slip: 0.1, learn: 0.1 }
  it('acerto aumenta e erro diminui a crença', () => {
    expect(posterior(0.5, true, p)).toBeGreaterThan(0.5)
    expect(posterior(0.5, false, p)).toBeLessThan(0.5)
  })
  it('guess alto torna o acerto menos informativo', () => {
    expect(posterior(0.5, true, { ...p, guess: 0.35 })).toBeLessThan(posterior(0.5, true, p))
  })
  it('aprendizagem nunca reduz P(L)', () => {
    expect(update(0.3, true, p)).toBeGreaterThanOrEqual(posterior(0.3, true, p))
  })
})

describe('motor', () => {
  const items = [item('1', 1, -1), item('2', 1, 0), item('3', 2, 0.5), item('4', 2, 2)]
  const priors: SkillPrior[] = [
    { area: 'MT', habilidade: 1, banda: 1, banda_label: '450-550', n: 1, p_acerto: 0.7, guess: 0.2, slip: 0.1, p_l0: 0.8 },
    { area: 'MT', habilidade: 2, banda: 1, banda_label: '450-550', n: 1, p_acerto: 0.3, guess: 0.2, slip: 0.1, p_l0: 0.1 },
  ]
  const bank = makeBank(items, priors, ['0-450', '450-550', '550-650', '650-750', '750-1000'])

  it('prioriza a habilidade mais frágil', () => {
    const s = newStudent(bank, 'teste', 1)
    expect(nextItem(s, bank, (i) => i.area === 'MT', () => 0.9)?.habilidade).toBe(2)
  })
  it('não repete questão já respondida', () => {
    let s = newStudent(bank, 'teste', 1)
    const first = nextItem(s, bank, (i) => i.area === 'MT', () => 0.9)!
    s = record(s, bank, first, 'A', false)
    expect(nextItem(s, bank, (i) => i.area === 'MT', () => 0.9)?.id).not.toBe(first.id)
  })
  it('nenhuma habilidade começa consolidada', () => {
    const s = newStudent(bank, 'teste', 1)
    expect(Math.max(...Object.values(s.mastery))).toBeLessThanOrEqual(0.85)
  })
  it('respeita o filtro de edição', () => {
    const s = newStudent(bank, 'teste', 1)
    expect(nextItem(s, bank, (i) => i.id === '4', () => 0.9)?.id).toBe('4')
    expect(nextItem(s, bank, () => false, () => 0.9)).toBeNull()
  })
  it('dica conta como erro para o rastreamento', () => {
    const s = newStudent(bank, 'teste', 1)
    const withHint = record(s, bank, items[2], 'A', true)
    const clean = record(s, bank, items[2], 'A', false)
    expect(withHint.mastery['MT-H2']).toBeLessThan(clean.mastery['MT-H2'])
  })
})

describe('pedagógico', () => {
  const its = Array.from({ length: 8 }, (_, i) => item(String(i + 1), 1, 0))
  const bank = makeBank(its, [], ['0-450', '450-550', '550-650', '650-750', '750-1000'])

  it('phi bate com a normal padrão', () => {
    expect(phi(0)).toBeCloseTo(0.5, 6)
    expect(phi(1.96)).toBeCloseTo(0.975, 3)
  })
  it('registra a previsão antes da resposta', () => {
    const s = record(newStudent(bank, 'a', 1), bank, its[0], 'A', false)
    expect(s.tentativas[0].pPrevisto).toBeGreaterThan(0)
    expect(s.tentativas[0].thetaAntes).toBeDefined()
  })
  it('não rotula risco sem evidência mínima', () => {
    const s = record(newStudent(bank, 'a', 1), bank, its[0], 'B', false)
    expect(risco(s, bank, 'MT', 600).faixa).toBe('evidência insuficiente')
  })
  it('muitos erros em itens médios levam a risco alto para meta 650', () => {
    let s = newStudent(bank, 'a', 1)
    for (const it of its) s = record(s, bank, it, 'B', false)
    expect(risco(s, bank, 'MT', 650).faixa).toBe('abaixo da meta provável')
  })
  it('autoavaliação fica na última tentativa do item', () => {
    let s = record(newStudent(bank, 'a', 1), bank, its[0], 'A', false)
    s = setConfianca(s, its[0].id, 'chute')
    expect(s.tentativas[0].confianca).toBe('chute')
  })
  it('sinaliza item que a turma erra muito além do esperado', () => {
    const turma = Array.from({ length: 4 }, (_, i) => {
      let s = newStudent(bank, `e${i}`, 4)
      for (const it of its.slice(0, 6)) s = record(s, bank, it, 'A', false)
      return record(s, bank, its[7], 'B', false)
    })
    expect(itensParaRevisar(turma, bank)[0]?.item.id).toBe('8')
  })
})

import { classificar, destaques, evidencias, porCompetencia } from './devolutiva'
import { mesclar, precisaConfirmarVinculo } from './sincronia'

describe('devolutiva pela Matriz', () => {
  const its = Array.from({ length: 12 }, (_, i) => ({ ...item(String(i + 1), i < 6 ? 16 : 3, 0), area: 'MT' as const }))
  const bank = makeBank(its, [], ['0-450', '450-550', '550-650', '650-750', '750-1000'])

  it('não rotula com menos de 3 tentativas', () => {
    expect(classificar(2, 2, 0.95, 2)).toBe('poucas tentativas')
  })
  it('separa ponto forte e a desenvolver, e agrupa por competência', () => {
    let s = newStudent(bank, 'a', 1)
    for (const it of its.slice(0, 6)) s = record(s, bank, it, 'A', false)   // MT-H16: acerta tudo
    for (const it of its.slice(6)) { s = record(s, bank, it, 'B', false); s = setConfianca(s, it.id, 'certeza') } // MT-H3: erra com certeza
    const ev = evidencias(s, bank)
    const h16 = ev.find((e) => e.habilidade === 16)!, h3 = ev.find((e) => e.habilidade === 3)!
    expect(h16.rotulo).toBe('ponto forte')
    expect(h3.rotulo).toBe('a desenvolver')
    expect(h16.competencia).toBe(4)   // H16 pertence à competência 4 de Matemática
    expect(h3.competencia).toBe(1)
    const d = destaques(ev)
    expect(d.concepcoes.map((e) => e.habilidade)).toEqual([3])
    expect(porCompetencia(ev).map((c) => c.numero)).toEqual([1, 4])
  })
})

describe('sincronia', () => {
  const its = Array.from({ length: 6 }, (_, i) => item(String(i + 1), 1, 0))
  const bank = makeBank(its, [], ['0-450', '450-550', '550-650', '650-750', '750-1000'])

  it('soma tentativas de dois aparelhos e recalcula o domínio', () => {
    let celular = newStudent(bank, 'a', 1)
    let pc = newStudent(bank, 'a', 1)
    celular = record(celular, bank, its[0], 'A', false)
    pc = record(pc, bank, its[1], 'B', false)
    pc.tentativas[0].ts = celular.tentativas[0].ts + 1
    const m = mesclar(bank, celular, pc)!
    expect(m.tentativas.map((t) => t.itemId)).toEqual(['1', '2'])
    let esperado = newStudent(bank, 'a', 1)
    esperado = record(esperado, bank, its[0], 'A', false)
    esperado = record(esperado, bank, its[1], 'B', false)
    expect(m.mastery['MT-H1']).toBeCloseTo(esperado.mastery['MT-H1'], 10)
  })
  it('mesclar consigo mesmo não duplica', () => {
    const s = record(newStudent(bank, 'a', 1), bank, its[0], 'A', false)
    expect(mesclar(bank, s, s)!.tentativas).toHaveLength(1)
  })
  it('pede confirmação para progresso sem dono ou de outro usuário', () => {
    const s = record(newStudent(bank, 'a', 1), bank, its[0], 'A', false)
    expect(precisaConfirmarVinculo(s, 'u1')).toBe(true)
    expect(precisaConfirmarVinculo({ ...s, dono: 'u1' }, 'u1')).toBe(false)
    expect(precisaConfirmarVinculo(newStudent(bank, 'a', 1), 'u1')).toBe(false)
  })
})

describe('devolutiva: casos de borda', () => {
  it('habilidade não informada (0) fica fora e competência recebe desempenho', () => {
    const its = [...Array.from({ length: 6 }, (_, i) => item(String(i + 1), 3, 1.5)), item('9', 0, 0)]
    const bank = makeBank(its, [], ['0-450', '450-550', '550-650', '650-750', '750-1000'])
    let s = newStudent(bank, 'a', 1)
    for (const it of its) s = record(s, bank, it, 'A', false)
    const ev = evidencias(s, bank)
    expect(ev.some((e) => e.habilidade === 0)).toBe(false)
    const c = porCompetencia(ev)[0]
    expect(c.n).toBe(6)
    expect(c.desempenho).toBe('acima do esperado') // 6 de 6 em questões difíceis
  })
})

describe('política com habilidade não informada', () => {
  it('não escolhe H0 como alvo principal quando há habilidades da Matriz', () => {
    const its = [item('1', 0, 3), item('2', 0, 3), item('3', 5, -1)]
    const bank = makeBank(its, [], ['0-450', '450-550', '550-650', '650-750', '750-1000'])
    const s = newStudent(bank, 'a', 1)
    expect(nextItem(s, bank, () => true, () => 0.9)?.habilidade).toBe(5)
  })
})

import { mensagemErro } from '../nuvem'

describe('mensagens de erro do login', () => {
  it('traduz os casos comuns e repassa o resto', () => {
    expect(mensagemErro(new Error('Invalid login credentials'))).toBe('E-mail ou senha incorretos.')
    expect(mensagemErro(new Error('User already registered'))).toMatch(/Já existe uma conta/)
    expect(mensagemErro(new Error('Password should be at least 6 characters'))).toBe('A senha precisa ter pelo menos 6 caracteres.')
    expect(mensagemErro(new Error('Email not confirmed'))).toMatch(/Confirme o e-mail/)
    expect(mensagemErro(new Error('Unsupported provider: provider is not enabled'))).toMatch(/Google ainda não está ligada/)
    expect(mensagemErro(new Error('algo inesperado'))).toBe('algo inesperado')
  })
})

import { disponiveis, MIN_TENTATIVAS_CONTEUDO, porConteudo } from './conteudo'

describe('desempenho por conteúdo programático', () => {
  const CAT = [
    { id: 'geometria-espacial', nome: 'Geometria espacial e volumes', area: 'MT' as const, disciplina: 'Matemática' },
    { id: 'probabilidade', nome: 'Probabilidade', area: 'MT' as const, disciplina: 'Matemática' },
  ]
  const its = [
    { ...item('1', 8, 2.5), topicos: ['geometria-espacial'] },
    { ...item('2', 8, 2.5), topicos: ['geometria-espacial'] },
    { ...item('3', 8, 2.5), topicos: ['geometria-espacial'] },
    { ...item('4', 8, 2.5), topicos: ['geometria-espacial', 'probabilidade'] },
    { ...item('5', 28, 2.5), topicos: [] },
  ]
  const bank = makeBank(its, [], ['0-450', '450-550', '550-650', '650-750', '750-1000'])

  it('agrega por tópico, marca a habilidade tocada e ignora questão sem tópico', () => {
    let s = newStudent(bank, 'a', 1)
    for (const it of its) s = record(s, bank, it, 'A', false)
    const r = porConteudo(s, bank, CAT)
    const ge = r.find((c) => c.id === 'geometria-espacial')!
    expect(ge.n).toBe(4)
    expect(ge.acertos).toBe(4)
    expect(ge.habilidades).toEqual([8])
    expect(ge.desempenho).toBe('acima do esperado')
    expect(r.find((c) => c.id === 'probabilidade')!.desempenho).toBe('poucas tentativas')
    expect(MIN_TENTATIVAS_CONTEUDO).toBeGreaterThan(1)
  })

  it('lista os conteúdos com questões na área selecionada, com contagem', () => {
    const d = disponiveis(bank, CAT, ['MT'])
    expect(d.map((c) => [c.id, c.itens])).toEqual([['geometria-espacial', 4], ['probabilidade', 1]])
    expect(disponiveis(bank, CAT, ['LC'])).toEqual([])
  })
})

import { CREDITO_DICA, updateParcial } from './bkt'

describe('dicas em níveis: crédito parcial', () => {
  const p = { guess: 0.2, slip: 0.1, learn: 0.12 }
  it('acerto com dica fica entre acerto pleno e erro, e nível 3 vale como erro', () => {
    const pleno = updateParcial(0.5, true, CREDITO_DICA[0], p)
    const n1 = updateParcial(0.5, true, CREDITO_DICA[1], p)
    const n2 = updateParcial(0.5, true, CREDITO_DICA[2], p)
    const n3 = updateParcial(0.5, true, CREDITO_DICA[3], p)
    const erro = updateParcial(0.5, false, 1, p)
    expect(pleno).toBeGreaterThan(n1)
    expect(n1).toBeGreaterThan(n2)
    expect(n2).toBeGreaterThan(n3)
    expect(n3).toBeCloseTo(erro, 10)
  })
  it('record registra o nível e aplica o crédito; registros antigos continuam válidos', () => {
    const its = [item('1', 3, 0)]
    const bank = makeBank(its, [], ['0-450', '450-550', '550-650', '650-750', '750-1000'])
    const s0 = newStudent(bank, 'a', 1)
    const semDica = record(s0, bank, its[0], 'A', 0)
    const comDica2 = record(s0, bank, its[0], 'A', 2)
    const antigo = record(s0, bank, its[0], 'A', true)  // API antiga: usouDica = true
    expect(semDica.tentativas[0].nivelDica).toBe(0)
    expect(comDica2.tentativas[0]).toMatchObject({ nivelDica: 2, usouDica: true })
    expect(antigo.tentativas[0].nivelDica).toBe(3)
    expect(semDica.mastery['MT-H3']).toBeGreaterThan(comDica2.mastery['MT-H3'])
    expect(comDica2.mastery['MT-H3']).toBeGreaterThan(antigo.mastery['MT-H3'])
  })
})

import { evolucao, novoResultado } from './evolucao'

describe('evolução com resultados anteriores', () => {
  const its = Array.from({ length: 8 }, (_, i) => item(String(i + 1), 3, 0))
  const bank = makeBank(its, [], ['0-450', '450-550', '550-650', '650-750', '750-1000'])
  it('compara a estimativa atual com o último registro e ordena por data', () => {
    let s = newStudent(bank, 'a', 1)
    for (const it of its) s = record(s, bank, it, 'A', 0)
    s = { ...s, historico: [novoResultado('2026-03-10', 'ENEM 2025', { MT: 520 }), novoResultado('2025-11-05', 'Simulado', { MT: 480, LC: 600 })] }
    const mt = evolucao(s, bank).find((a) => a.area === 'MT')!
    expect(mt.pontos.map((p) => p.nota)).toEqual([480, 520])
    expect(mt.ultimo?.origem).toBe('ENEM 2025')
    expect(mt.estimativa).not.toBeNull()
    expect(mt.variacao).toBe(mt.estimativa! - 520)
    const lc = evolucao(s, bank).find((a) => a.area === 'LC')!
    expect(lc.estimativa).toBeNull()   // sem questões de LC, não há estimativa
    expect(lc.variacao).toBeNull()
  })
  it('descarta notas fora da escala e a sincronia une históricos', () => {
    const r = novoResultado('2026-01-01', '  ', { MT: 1500, CN: 610.4 })
    expect(r.notas).toEqual({ CN: 610 })
    expect(r.origem).toBe('Resultado anterior')
    const a = { ...newStudent(bank, 'a', 1), historico: [r] }
    const b = { ...newStudent(bank, 'a', 1), historico: [novoResultado('2025-06-01', 'Simulado', { LC: 500 })] }
    expect(mesclar(bank, a, b)!.historico!.map((h) => h.data)).toEqual(['2025-06-01', '2026-01-01'])
  })
})

import { INTERVALO_REVISAO_DIAS, revisoesVencidas, setDificuldade } from './engine'
import { trajetoria } from './evolucao'

describe('revisão espaçada por dificuldade percebida', () => {
  const its = Array.from({ length: 6 }, (_, i) => item(String(i + 1), 3, 0))
  const bank = makeBank(its, [], ['0-450', '450-550', '550-650', '650-750', '750-1000'])
  const DIA = 86_400_000
  it('erro volta em 1 dia, difícil em 3, fácil em 21; ordem: erro, difícil, mais atrasada', () => {
    let s = newStudent(bank, 'a', 1)
    s = record(s, bank, its[0], 'B', 0)                       // errou
    s = setDificuldade(record(s, bank, its[1], 'A', 0), '2', 'dificil')
    s = setDificuldade(record(s, bank, its[2], 'A', 0), '3', 'facil')
    const t0 = s.tentativas[0].ts
    expect(revisoesVencidas(s, bank, t0).map((r) => r.item.id)).toEqual([])
    expect(revisoesVencidas(s, bank, t0 + 1.5 * DIA).map((r) => r.item.id)).toEqual(['1'])
    expect(revisoesVencidas(s, bank, t0 + 4 * DIA).map((r) => r.item.id)).toEqual(['1', '2'])
    expect(revisoesVencidas(s, bank, t0 + 22 * DIA).map((r) => r.item.id)).toEqual(['1', '2', '3'])
    expect(INTERVALO_REVISAO_DIAS.facil).toBeGreaterThan(INTERVALO_REVISAO_DIAS.dificil)
  })
  it('a política reapresenta questões vencidas e ignora as não vencidas', () => {
    let s = record(newStudent(bank, 'a', 1), bank, its[0], 'B', 0)
    const t0 = s.tentativas[0].ts
    const escolhaComRevisao = nextItem(s, bank, () => true, () => 0.1, t0 + 2 * DIA)  // rng abaixo da fração de revisão
    expect(escolhaComRevisao?.id).toBe('1')
    const semRevisao = nextItem(s, bank, () => true, () => 0.1, t0)                   // ainda não venceu
    expect(semRevisao?.id).not.toBe('1')
  })
  it('a trajetória usa o θ registrado antes de cada resposta, um ponto por dia', () => {
    let s = newStudent(bank, 'a', 1)
    for (const it of its) s = record(s, bank, it, 'A', 0)
    const tr = trajetoria(s, bank, 'MT')
    expect(tr.length).toBe(1)                     // tudo hoje: um ponto (a estimativa atual)
    expect(tr[0].nota).toBeGreaterThan(500)       // seis acertos acima da faixa inicial
    expect(trajetoria(s, bank, 'LC')).toEqual([])
  })
})

import { linkObjetivo } from '../tutor'

describe('link para a resolução do Objetivo', () => {
  it('escolhe o dia certo por edição e área e ignora a 2ª aplicação', () => {
    expect(linkObjetivo({ ...item('1', 1, 0), ano: 2015, area: 'CH' })).toMatch(/enem2015_1dia\.aspx$/)
    expect(linkObjetivo({ ...item('1', 1, 0), ano: 2015, area: 'MT' })).toMatch(/enem2015_2dia\.aspx$/)
    expect(linkObjetivo({ ...item('1', 1, 0), ano: 2023, area: 'LC' })).toMatch(/enem2023_1dia\.aspx$/)
    expect(linkObjetivo({ ...item('1', 1, 0), ano: 2023, area: 'CN' })).toMatch(/enem2023_2dia\.aspx$/)
    expect(linkObjetivo({ ...item('1', 1, 0), ano: 2020, area: 'MT' })).toMatch(/enem2020_2dia_presencial\.aspx$/)
    expect(linkObjetivo({ ...item('1', 1, 0), ano: 2016, area: 'MT', aplicacao: 2 })).toBeNull()
  })
})
