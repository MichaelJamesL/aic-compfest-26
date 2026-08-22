import type { WorkOrderStatus } from '../api/types'
import { WORK_ORDER, WORK_ORDER_TRACK } from '../lib/severity'
import { cn } from '../lib/cn'

const TERMINAL: WorkOrderStatus[] = ['rejected', 'cancelled']

/**
 * Six labelled dots joined by hairlines. Current is filled and labelled, past
 * ones filled and dim, future ones hollow. A terminal state greys the track
 * and marks the ending step in --crit. SCREENS.md §4.
 */
export function StateTrack({ status }: { status: WorkOrderStatus }) {
  const ended = TERMINAL.includes(status)
  const index = WORK_ORDER_TRACK.indexOf(status)

  return (
    <ol className="flex items-center gap-1.5" aria-label="Status work order">
      {WORK_ORDER_TRACK.map((step, i) => {
        const past = !ended && index > i
        const current = !ended && index === i
        return (
          <li key={step} className="flex flex-1 items-center gap-1.5">
            <span className="flex flex-col gap-1.5">
              <span
                className={cn(
                  'size-2 rounded-full',
                  ended && 'bg-raised',
                  past && 'bg-dim',
                  current && 'bg-white',
                  !ended && !past && !current && 'border border-hair-strong',
                )}
                aria-hidden
              />
            </span>
            <span
              className={cn(
                'flex-1 truncate text-[11.5px]',
                current ? 'font-medium text-white' : 'text-faint',
              )}
            >
              {WORK_ORDER[step].label}
            </span>
            {i < WORK_ORDER_TRACK.length - 1 && (
              <span className="h-px flex-1 bg-hair" aria-hidden />
            )}
          </li>
        )
      })}
      {ended && (
        <li className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-crit" aria-hidden />
          <span className="text-[11.5px] font-medium text-crit-text">
            {WORK_ORDER[status].label}
          </span>
        </li>
      )}
    </ol>
  )
}
