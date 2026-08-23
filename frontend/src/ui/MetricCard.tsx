import type { ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { Card } from './Card'
import { IconButton } from './Button'

/**
 * Icon chip · title · action, then the value, then caption + badge.
 * Nothing else goes in a metric card — no sparkline, no progress bar.
 * VISUAL_LANGUAGE.md §7.
 */
export function MetricCard({
  icon,
  title,
  value,
  caption,
  badge,
  onAction,
  actionLabel,
}: {
  icon: ReactNode
  title: string
  value: ReactNode
  caption?: ReactNode
  badge?: ReactNode
  onAction?: () => void
  actionLabel?: string
}) {
  return (
    <Card className="flex flex-col justify-between">
      <div className="flex items-center gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-surface-raised text-content-2">
          {icon}
        </span>
        <h3 className="flex-1 text-sm font-medium">{title}</h3>
        {onAction && (
          <IconButton label={actionLabel ?? title} onClick={onAction}>
            <ChevronRight size={14} />
          </IconButton>
        )}
      </div>

      <p className="tnum mt-5 text-[30px] leading-[34px] font-semibold -tracking-[0.02em]">
        {value}
      </p>

      {(caption || badge) && (
        <div className="mt-2 flex items-center justify-between gap-3">
          <span className="text-xs text-content-3">{caption}</span>
          {badge}
        </div>
      )}
    </Card>
  )
}
