import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '../lib/cn'

type Variant = 'primary' | 'primary-light' | 'secondary' | 'ghost' | 'destructive'

const VARIANT: Record<Variant, string> = {
  primary: 'bg-white text-card hover:bg-white/90',
  'primary-light': 'bg-ink text-white hover:bg-ink/90',
  secondary: 'border border-hair-strong text-white hover:bg-raised',
  ghost: 'text-dim hover:text-white',
  destructive: 'bg-crit text-card hover:bg-crit/90',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'md' | 'sm'
  icon?: ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  className,
  children,
  ...rest
}: Props) {
  return (
    <button
      {...rest}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-control font-medium',
        'transition-colors duration-100 ease-out',
        'disabled:pointer-events-none disabled:opacity-40',
        size === 'md' ? 'h-10 px-[18px] text-sm' : 'h-8 px-3 text-[13px]',
        VARIANT[variant],
        className,
      )}
    >
      {icon}
      {children}
    </button>
  )
}

/** The small circular action in the corner of a metric card. */
export function IconButton({
  label,
  children,
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return (
    <button
      {...rest}
      aria-label={label}
      className={cn(
        'grid size-7 shrink-0 place-items-center rounded-full border border-hair',
        'text-dim transition-colors duration-100 hover:text-white hover:border-hair-strong',
        className,
      )}
    >
      {children}
    </button>
  )
}
