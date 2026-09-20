import { useMemo } from 'react'
import { brier, MODELOS } from '../kt/modelos'
import type { StudentState } from '../kt/types'

/**
 * Comparação entre o modelo que pilota o treino e os que rodam em segundo plano.
 * O erro de Brier mede o quanto a previsão erra: 0 é perfeito, 0,25 é chutar 50% sempre.
 */
export function Modelos({ student }: { student: StudentState }) {
  const linhas = useMemo(() => brier(student.tentativas), [student.tentativas])
  if (linhas.length < 2 || linhas[0].n < 10) return null
  const nome = (id: string) => MODELOS.find((m) => m.id === id)!

  return (
    <section className="modelos" aria-labelledby="mod-titulo">
      <h2 id="mod-titulo" className="secao">Modelos de rastreamento</h2>
      <p className="fineprint">
        O <strong>Elo com Rasch</strong> pilota: é dele o domínio que você vê e a escolha das questões. Os outros preveem
        em segundo plano, para comparação. No estudo com os microdados do Enem, o BKT ficou 0,178 de AUC abaixo da TRI
        em 68 de 68 células, e por isso deixou de pilotar aqui.
      </p>
      <div className="tabela-rolagem">
        <table className="tabela-risco">
          <thead><tr><th>Modelo</th><th>Erro de Brier</th><th>Acertou a direção</th><th>Questões</th><th></th></tr></thead>
          <tbody>{linhas.map((l, i) => (
            <tr key={l.modelo}>
              <td>{nome(l.modelo).nome}{l.modelo === 'elo' && <span className="faixa ok">piloto</span>}</td>
              <td>{l.brier.toFixed(3)}{i === 0 && <small>melhor até aqui</small>}</td>
              <td>{Math.round(l.acerto * 100)}%</td>
              <td>{l.n}</td>
              <td><small>{nome(l.modelo).descricao}</small></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="fineprint">
        Comparação descritiva, com as suas respostas: poucas questões deixam qualquer ordem instável. Os parâmetros de
        PFA e AFM são de projeto, não estimados nesta base. As previsões ficam no CSV, com a posição de cada questão na
        sessão, para a análise de efeito de posição que o estudo recomenda.
      </p>
    </section>
  )
}
