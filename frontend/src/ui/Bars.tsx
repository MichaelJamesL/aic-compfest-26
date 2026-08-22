import { useState } from 'react'
import { cn } from '../lib/cn'

export interface Bar {
  label: string
  value: number
  highlighted?: boolean
}

/**
 * 14 wide, 10 gap, radius 6 on the top corners only, single colour with the
 * highlighted bar one step darker. Tooltip is the one glass element.
 */
export function Bars({
  bars,
  format = (v) => String(v),
  height = 140,
  color = 'var(--color-apricot)',
  highlightColor = 'var(--color-burnt)',
  className,
}: {
  bars: Bar[]
  format?: (value: number) => string
  height?: number
  color?: string
  highlightColor?: string
  className?: string
}) {
  const [active, setActive] = useState<number | null>(null)
  // Not `Math.max(..., 1)`: defect rates are fractions, and flooring the
  // scale at 1 flattens every bar to its raw percentage of the chart — which
  // hides exactly the batch-over-batch trend this chart exists to show.
  const max = Math.max(...bars.map((b) => b.value), 0) || 1

  return (
    <div className={cn('relative', className)}>
      <div className="flex items-end gap-2.5" style={{ height }}>
        {bars.map((bar, index) => (
          <div
            key={bar.label}
            className="relative flex flex-1 flex-col items-center justify-end"
            onMouseEnter={() => setActive(index)}
            onMouseLeave={() => setActive(null)}
          >
            {active === index && (
              <div className="glass-light absolute bottom-full z-10 mb-2 rounded-control px-3 py-2 text-ink">
                <p className="tnum text-sm font-semibold">{format(bar.value)}</p>
                <p className="text-[11.5px] text-ink-faint">{bar.label}</p>
              </div>
            )}
            <div
              className="w-full max-w-3.5 rounded-t-md transition-opacity duration-100"
              style={{
                height: `${Math.max((bar.value / max) * 100, 2)}%`,
                background: bar.highlighted ? highlightColor : color,
                opacity: active === null || active === index ? 1 : 0.6,
              }}
            />
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-2.5">
        {bars.map((bar) => (
          <span key={bar.label} className="flex-1 text-center text-[11.5px] text-faint">
            {bar.label}
          </span>
        ))}
      </div>
    </div>
  )
}

/** 4px confidence bar — no percentage ring. VISUAL_LANGUAGE.md §7. */
export function ConfidenceBar({ value }: { value: number }) {
  const percent = Math.round(Math.min(Math.max(value, 0), 1) * 100)
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-1 w-16 overflow-hidden rounded-full bg-raised">
        <span
          className="block h-full rounded-full bg-teal"
          style={{ width: `${percent}%` }}
        />
      </span>
      <span className="tnum text-xs text-dim">{percent}%</span>
    </span>
  )
}
