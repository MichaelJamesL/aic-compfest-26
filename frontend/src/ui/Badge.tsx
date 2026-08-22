import type { ReactNode } from 'react'
import { cn } from '../lib/cn'
import { TONE_DOT, TONE_FILL, type Tone } from '../lib/severity'

/** Height 22, padding 0 8, pill, 11.5/500. One word or a signed number. */
export function Badge({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: Tone
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex h-[22px] items-center rounded-full px-2 text-[11.5px] font-medium',
        TONE_FILL[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

/** Colour is never the only channel: a dot always carries a label. */
export function StatusDot({
  tone,
  children,
  className,
}: {
  tone: Tone
  children: ReactNode
  className?: string
}) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <span className={cn('size-1.5 shrink-0 rounded-full', TONE_DOT[tone])} aria-hidden />
      {children}
    </span>
  )
}
