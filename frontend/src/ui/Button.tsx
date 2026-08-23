import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { controlClass, type Size, type Variant } from './controlClass'
import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router'
import { cn } from '../lib/cn'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
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
    <button {...rest} className={controlClass(variant, size, className)}>
      {icon}
      {children}
    </button>
  )
}

/**
 * A navigation that looks like a button. Renders one anchor — wrapping a
 * `<Button>` in a `<Link>` nests interactive content, which gives two focus
 * stops and an ambiguous role.
 */
export function LinkButton({
  to,
  variant = 'secondary',
  size = 'md',
  icon,
  className,
  children,
}: {
  to: string
  variant?: Variant
  size?: Size
  icon?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <Link to={to} className={controlClass(variant, size, className)}>
      {icon}
      {children}
    </Link>
  )
}

/**
 * Going back up a level. Reads as a control rather than as a caption: a
 * hairline border, a hover surface, and content-level text.
 */
export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className={cn(
        'mb-3 inline-flex h-8 items-center gap-1.5 rounded-control border border-line',
        'px-2.5 text-[13px] font-medium text-content-2',
        'transition-colors duration-100 hover:bg-surface-raised hover:text-content',
      )}
    >
      <ArrowLeft size={14} />
      {children}
    </Link>
  )
}

/**
 * An inline link inside running text. Underlined always, not only on hover —
 * hover is not an affordance on a touch screen, and it is invisible in a
 * screenshot.
 */
export function TextLink({
  to,
  children,
  className,
}: {
  to: string
  children: ReactNode
  className?: string
}) {
  return (
    <Link
      to={to}
      className={cn(
        'font-medium text-content underline decoration-line-strong underline-offset-[3px]',
        'transition-colors duration-100 hover:decoration-content',
        className,
      )}
    >
      {children}
    </Link>
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
        'grid size-7 shrink-0 place-items-center rounded-full border border-line',
        'text-content-2 transition-colors duration-100 hover:text-content hover:border-line-strong',
        className,
      )}
    >
      {children}
    </button>
  )
}
