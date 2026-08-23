import type { ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import { cn } from '../lib/cn'

/**
 * Sentence-case headers, row dividers only — no outer border, no zebra.
 * Wide tables scroll inside their own container; the panel never scrolls.
 */
export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className={cn('w-full min-w-[560px] border-collapse text-left', className)}>
        {children}
      </table>
    </div>
  )
}

export function Th({
  children,
  align = 'left',
  className,
}: {
  children: ReactNode
  align?: 'left' | 'right'
  className?: string
}) {
  return (
    <th
      scope="col"
      className={cn(
        'pb-3 pr-6 text-xs font-medium text-content-3 last:pr-0',
        align === 'right' && 'text-right',
        className,
      )}
    >
      {children}
    </th>
  )
}

export function Td({
  children,
  align = 'left',
  tone = 'default',
  className,
}: {
  children: ReactNode
  align?: 'left' | 'right'
  tone?: 'default' | 'primary' | 'muted'
  className?: string
}) {
  return (
    <td
      className={cn(
        'h-11 pr-6 align-middle text-[13px] last:pr-0',
        align === 'right' && 'text-right tnum',
        tone === 'primary' && 'text-[13.5px] font-medium text-content',
        tone === 'muted' && 'text-content-3',
        tone === 'default' && 'text-content-2',
        className,
      )}
    >
      {children}
    </td>
  )
}

/**
 * `to` marks a row that navigates. The row gains a hover surface so it reads as
 * interactive at rest, and callers pair it with `NavCell` for the visible link
 * and `ChevronCell` for the direction. Hover alone is not an affordance: it
 * does not exist on touch and does not show in a screenshot.
 */
export function Tr({
  children,
  to,
  className,
}: {
  children: ReactNode
  to?: string
  className?: string
}) {
  return (
    <tr
      className={cn(
        'border-t border-line',
        to && 'transition-colors duration-100 hover:bg-surface-raised',
        className,
      )}
    >
      {children}
    </tr>
  )
}

/** The cell that carries the row's link. Underlined at rest, not on hover. */
export function NavCell({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Td tone="primary" className="pr-6">
      <Link
        to={to}
        className="font-medium text-content underline decoration-line-strong underline-offset-[3px] transition-colors duration-100 hover:decoration-content"
      >
        {children}
      </Link>
    </Td>
  )
}

/** A trailing chevron so the row's direction is visible without hovering. */
export function ChevronCell({ to, label }: { to: string; label: string }) {
  return (
    <td className="h-11 w-10 align-middle text-right">
      <Link
        to={to}
        aria-label={label}
        tabIndex={-1}
        className="inline-grid size-7 place-items-center rounded-full text-content-3 transition-colors duration-100 hover:bg-surface-card hover:text-content"
      >
        <ChevronRight size={15} />
      </Link>
    </td>
  )
}
