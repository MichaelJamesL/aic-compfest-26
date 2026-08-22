import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

/**
 * Sentence-case headers, row dividers only — no outer border, no zebra.
 * Wide tables scroll inside their own container; the panel never scrolls.
 */
export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className="-mx-1 overflow-x-auto px-1">
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
        'pb-3 text-xs font-medium text-faint',
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
        'h-11 align-middle text-[13px]',
        align === 'right' && 'text-right tnum',
        tone === 'primary' && 'text-[13.5px] font-medium text-white',
        tone === 'muted' && 'text-faint',
        tone === 'default' && 'text-dim',
        className,
      )}
    >
      {children}
    </td>
  )
}

export function Tr({ children }: { children: ReactNode }) {
  return <tr className="border-t border-hair">{children}</tr>
}
