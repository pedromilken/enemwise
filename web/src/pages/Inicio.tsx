import { useState } from 'react'

export function Inicio({ bandas, onStart }: { bandas: string[]; onStart: (nome: string, banda: number) => void }) {
  const [nome, setNome] = useState('')
  const [banda, setBanda] = useState(1)
  return (
    <section className="folha inicio">
      <h1 className="display small">Duas perguntas antes de começar</h1>
      <p className="lede">
        Servem para o treino partir do lugar certo: a faixa de nota define a dificuldade inicial das questões, calculada
        a partir de como os participantes dessa faixa se saíram.
      </p>
      <form className="stack" onSubmit={(e) => { e.preventDefault(); onStart(nome.trim() || 'Estudante', banda) }}>
        <label className="field">
          <span>Como quer ser chamado</span>
          <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Opcional" maxLength={40} />
        </label>
        <fieldset className="field">
          <legend>Qual nota média você espera tirar hoje?</legend>
          <div className="bandas">
            {bandas.map((b, i) => (
              <label key={b} className={i === banda ? 'banda on' : 'banda'}>
                <input type="radio" name="banda" checked={i === banda} onChange={() => setBanda(i)} />
                {b.replace('-', ' a ')}
              </label>
            ))}
          </div>
          <small>Não sabe? Deixe em 450 a 550. O treino ajusta a estimativa conforme você responde.</small>
        </fieldset>
        <button className="btn primary" type="submit">Começar treino</button>
      </form>
      <p className="fineprint">Seu progresso fica salvo só neste navegador. Nada sai dele, a menos que você ative o tutor com IA.</p>
    </section>
  )
}
