import { cn } from '../lib/cn'

export interface Segment {
  label: string
  value: number
  /** A CSS colour, always from the token set. */
  color: string
}

const SIZE = 150
const STROKE = 26
const GAP = 2 // px of arc between segments, as in the reference

/**
 * 150 diameter, 26 stroke, 2px gaps, butt caps. The centre holds one number.
 * Segment colours come from the accent list in a fixed order — never a
 * generated ramp. VISUAL_LANGUAGE.md §7.
 */
export function Donut({
  segments,
  value,
  suffix,
  caption,
  captionClass,
  className,
}: {
  segments: Segment[]
  value: string | number
  suffix?: string
  caption?: string
  captionClass?: string
  className?: string
}) {
  const radius = (SIZE - STROKE) / 2
  const circumference = 2 * Math.PI * radius
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1

  // Cumulative offsets, built in one pass so nothing mutates across a callback.
  const arcs: (Segment & { dash: string; offset: number })[] = []
  let consumed = 0
  for (const segment of segments) {
    if (segment.value <= 0) continue
    const length = (segment.value / total) * circumference
    const visible = Math.max(length - GAP, 0.5)
    arcs.push({
      ...segment,
      dash: `${visible} ${circumference - visible}`,
      offset: -consumed,
    })
    consumed += length
  }

  return (
    <div className={cn('flex flex-col items-center', className)}>
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden>
          <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
            {arcs.map((arc) => (
              <circle
                key={arc.label}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={radius}
                fill="none"
                stroke={arc.color}
                strokeWidth={STROKE}
                strokeDasharray={arc.dash}
                strokeDashoffset={arc.offset}
              />
            ))}
          </g>
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="tnum text-[30px] leading-[34px] font-semibold -tracking-[0.02em]">
            {value}
            {suffix && <span className="text-base text-faint">{suffix}</span>}
          </p>
        </div>
      </div>

      {/* Below the ring, not inside it: the inner circle is only ~84px wide at
          the caption's height, and Indonesian band labels are longer. */}
      {caption && (
        <p className={cn('mt-3 text-center text-xs', captionClass ?? 'text-dim')}>{caption}</p>
      )}
    </div>
  )
}

/** The 2×2 legend beneath the donut, as in the reference. */
export function DonutLegend({ segments }: { segments: Segment[] }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1
  return (
    <dl className="mt-5 space-y-2.5">
      {segments.map((segment) => (
        <div key={segment.label} className="flex items-center gap-2">
          <span
            className="size-1.5 shrink-0 rounded-full"
            style={{ background: segment.color }}
            aria-hidden
          />
          <dt className="flex-1 text-xs text-dim">{segment.label}</dt>
          <dd className="tnum text-xs font-medium">
            {Math.round((segment.value / total) * 100)}%
          </dd>
        </div>
      ))}
    </dl>
  )
}
