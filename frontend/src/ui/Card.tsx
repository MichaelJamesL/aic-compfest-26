import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

type Tint = 'dark' | 'sage' | 'apricot' | 'clay' | 'mint'

/** Tinted cards always use #111111 for text — never white on these tones. */
const TINT: Record<Tint, string> = {
  dark: 'bg-card text-white',
  sage: 'bg-sage text-card',
  apricot: 'bg-apricot text-card',
  clay: 'bg-clay text-card',
  mint: 'bg-mint text-card',
}

export function Card({
  tint = 'dark',
  className,
  children,
  as: Tag = 'section',
}: {
  tint?: Tint
  className?: string
  children: ReactNode
  as?: 'section' | 'div' | 'article'
}) {
  // No shadow. On dark, elevation is fill. VISUAL_LANGUAGE.md §5.
  return <Tag className={cn('rounded-card p-5', TINT[tint], className)}>{children}</Tag>
}

export function CardTitle({
  children,
  muted = false,
}: {
  children: ReactNode
  muted?: boolean
}) {
  return (
    <h2 className={cn('text-sm font-medium', muted && 'text-dim')}>{children}</h2>
  )
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-[17px] leading-6 font-semibold -tracking-[0.01em]">{children}</h2>
}

/** The line that marks a number as computed, not written by the model. */
export function DeterministicNote({ children }: { children?: ReactNode }) {
  return (
    <p className="text-[11.5px] leading-4 text-teal">
      {children ?? 'Dihitung deterministik, bukan oleh LLM.'}
    </p>
  )
}
