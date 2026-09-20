import { Marca } from '../components/Marca'
import type { Bank } from '../kt/engine'
import type { Meta, StudentState } from '../kt/types'

/** Página de entrada: o que é, de onde vêm os dados e por onde começar. */
export function Home({ bank, meta, student }: { bank: Bank; meta: Meta; student: StudentState | null }) {
  const comTexto = bank.items.filter((i) => i.enunciado).length
  const edicoes = meta.edicoes_com_texto ?? []
  const respondidas = student?.tentativas.length ?? 0

  return (
    <div className="home">
      <section className="folha hero">
        <p className="hero-marca"><Marca size={44} /></p>
        <h1 className="display">Treine o que ainda falta dominar.</h1>
        <p className="lede">
          Questões reais do Enem, escolhidas a partir do que você já acertou e errou, habilidade por habilidade da
          Matriz de Referência. A dificuldade de cada questão e o seu ponto de partida vêm dos microdados do INEP,
          com milhões de participantes.
        </p>
        <div className="mapa-acoes">
          <a className="btn primary" href="#treinar">{respondidas ? 'Continuar treino' : 'Começar a treinar'}</a>
          <a className="btn" href="#banco">Ver o banco de questões</a>
        </div>
        <p className="fineprint">
          Grátis, sem cadastro para treinar. O progresso fica no seu navegador; entrar guarda o histórico e libera a
          devolutiva. Software livre sob GPL-3.0.
        </p>
      </section>

      <section className="numeros" aria-label="O que tem dentro">
        {[
          [comTexto.toLocaleString('pt-BR'), 'questões com enunciado'],
          [`${edicoes.length}`, 'edições do Enem'],
          ['120', 'habilidades da Matriz'],
          [`${(meta.conteudos ?? []).length}`, 'conteúdos de disciplina'],
        ].map(([n, l]) => (
          <div key={l} className="numero"><strong>{n}</strong><span>{l}</span></div>
        ))}
      </section>

      <section className="home-blocos">
        <article className="folha">
          <h2>Para estudar</h2>
          <p>
            O treino escolhe a habilidade mais frágil e explora o resto do banco. Você pede dica em três níveis, avalia se
            ajudou, marca a questão como fácil ou difícil, e ela volta no intervalo certo: erro em 1 dia, difícil em 3,
            fácil em 21.
          </p>
          <p><a href="#treinar">Ir para o treino</a></p>
        </article>
        <article className="folha">
          <h2>Para saber onde está</h2>
          <p>
            A devolutiva compara o seu acerto com o esperado para aquelas questões, e não com a média da turma. Sai por
            competência da Matriz, por conteúdo (geometria analítica, genética, variação linguística) e como relatório
            para imprimir. Dá para registrar notas de simulados e acompanhar a evolução.
          </p>
          <p><a href="#mapa">Ver meu retorno</a></p>
        </article>
        <article className="folha">
          <h2>Para ensinar</h2>
          <p>
            A área do professor recebe os arquivos da turma e mostra risco por estudante, competências e conteúdos que
            mais pedem aula, e uma planilha para contato. Também exporta o log de pesquisa, anonimizado.
          </p>
          <p><a href="#professor">Abrir área do professor</a></p>
        </article>
      </section>

      <section className="folha home-dados">
        <h2>De onde vêm os dados</h2>
        <ul>
          <li><strong>Microdados do Enem (INEP)</strong>, edições {meta.edicoes[0]} a {meta.edicoes.at(-1)}: dificuldade, discriminação e acerto casual de cada questão, além do desempenho por faixa de nota.</li>
          <li><strong>Alinhamento certificado</strong> contra o gabarito impresso, caderno a caderno, pelo pipeline <code>enem_kt_confounds</code> v9.2.</li>
          <li><strong>Enunciados abertos</strong> do ENEM Challenge e do maritaca-ai/enem; nas edições sem fonte aberta, as questões entram só no cálculo do ponto de partida.</li>
          <li><strong>Rastreamento:</strong> um Elo sobre os parâmetros do INEP decide o treino; TRI, BKT, PFA e AFM preveem em segundo plano, para comparação.</li>
        </ul>
        <p className="fineprint">
          As questões do Enem são documentos públicos do INEP. Este site não é oficial e não tem vínculo com o INEP.
          Código e método abertos em <a href="https://github.com/pedromilken/enemwise" target="_blank" rel="noopener noreferrer">github.com/pedromilken/enemwise</a>.
        </p>
      </section>
    </div>
  )
}
