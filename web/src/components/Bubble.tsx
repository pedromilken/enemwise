import { useId } from 'react'

/** A bolinha do cartão-resposta, preenchida de baixo para cima conforme o domínio. */
export function Bubble({ value, label, size = 28, marked }: { value: number; label?: string; size?: number; marked?: boolean }) {
  const id = useId()
  const w = size, h = size * 0.62
  const fill = Math.max(0, Math.min(1, value))
  return (
    <svg className="bubble" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label}>
      <defs>
        <clipPath id={id}>
          <rect x="0" y={h * (1 - fill)} width={w} height={h * fill} />
        </clipPath>
      </defs>
      <ellipse cx={w / 2} cy={h / 2} rx={w / 2 - 1.5} ry={h / 2 - 1.5} className="bubble-ring" />
      <ellipse cx={w / 2} cy={h / 2} rx={w / 2 - 1.5} ry={h / 2 - 1.5} className={marked ? 'bubble-ink marked' : 'bubble-ink'} clipPath={`url(#${id})`} />
    </svg>
  )
}
