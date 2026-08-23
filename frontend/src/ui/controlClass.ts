import { cn } from '../lib/cn'

export type Variant = 'primary' | 'secondary' | 'ghost' | 'destructive'
export type Size = 'md' | 'sm'

// One fill per row of the hierarchy, on the light work surface.
const VARIANT: Record<Variant, string> = {
  primary: 'bg-content text-surface-card hover:bg-content/90',
  secondary: 'border border-line-strong text-content hover:bg-surface-raised',
  ghost: 'text-content-2 hover:text-content',
  destructive: 'bg-crit text-card hover:bg-crit/90',
}

/**
 * Shared by `Button` and `LinkButton`, so a link can never drift from a button
 * that does the same job. Lives in its own module: a file that exports
 * non-components breaks fast refresh.
 */
export function controlClass(variant: Variant, size: Size, className?: string) {
  return cn(
    'inline-flex items-center justify-center gap-2 rounded-control font-medium',
    'transition-colors duration-100 ease-out',
    // A blocked action must not stay the loudest element: disabled drops the
    // fill entirely rather than just fading it.
    'disabled:pointer-events-none disabled:border disabled:border-line',
    'disabled:bg-transparent disabled:text-content-3 disabled:shadow-none',
    size === 'md' ? 'h-10 px-[18px] text-sm' : 'h-8 px-3 text-[13px]',
    VARIANT[variant],
    className,
  )
}
