import type { ReactNode } from 'react'
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

export function Tr({ children }: { children: ReactNode }) {
  return <tr className="border-t border-line">{children}</tr>
}
