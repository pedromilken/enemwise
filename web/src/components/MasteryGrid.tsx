import { level } from '../kt/bkt'
import { type Area, AREAS, skillKey, type SkillKey } from '../kt/types'
import { Bubble } from './Bubble'

export function MasteryGrid({ value, areas, descricoes, note }: {
  value: (k: SkillKey) => number | null
  areas: Record<Area, string>
  descricoes: Record<string, string>
  note?: (k: SkillKey) => string | undefined
}) {
  return (
    <div className="sheet-grid" role="table" aria-label="Domínio por habilidade">
      {AREAS.map((area) => (
        <div className="sheet-col" role="rowgroup" key={area}>
          <h3 className="sheet-head">{areas[area]}</h3>
          {Array.from({ length: 30 }, (_, i) => i + 1).map((h) => {
            const k = skillKey(area, h)
            const v = value(k)
            const desc = descricoes[k]
            const title = v == null ? `H${h}: sem questões no banco` : `H${h}: ${Math.round(v * 100)}% (${level(v)})${desc ? `. ${desc}` : ''}`
            return (
              <div className={v == null ? 'sheet-row empty' : 'sheet-row'} role="row" key={k} title={title}>
                <span className="sheet-num">H{h}</span>
                {v == null ? <span className="sheet-dash" aria-label="sem questões" /> : <Bubble value={v} label={title} size={34} marked={v >= 0.95} />}
                <span className="sheet-note">{v == null ? '' : note?.(k) ?? `${Math.round(v * 100)}%`}</span>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}
