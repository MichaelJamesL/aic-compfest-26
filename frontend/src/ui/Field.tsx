import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'
import { useId } from 'react'
import { cn } from '../lib/cn'

/** Labels sit above the field. Not floating, not uppercase, not inside. */
export function Field({
  label,
  hint,
  children,
  htmlFor,
}: {
  label: string
  hint?: ReactNode
  children: ReactNode
  htmlFor?: string
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-[13px] font-medium text-content-2">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-content-3">{hint}</p>}
    </div>
  )
}

// No `outline-none` here. It sets `outline-style: none`, and a later
// `outline-2` only sets the width — so the ring never draws and keyboard users
// lose the caret entirely. The base `:focus-visible` rule in index.css handles
// this correctly for every control.
const CONTROL =
  'w-full rounded-control bg-surface-card px-3.5 text-sm text-content placeholder:text-content-3 ' +
  'border border-line transition-colors duration-100 hover:border-line-strong ' +
  'focus:border-line-strong'

export function TextInput({
  label,
  hint,
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label?: string; hint?: ReactNode }) {
  const id = useId()
  const input = <input id={id} {...rest} className={cn(CONTROL, 'h-10', className)} />
  return label ? (
    <Field label={label} hint={hint} htmlFor={id}>
      {input}
    </Field>
  ) : (
    input
  )
}

export function TextArea({
  label,
  hint,
  className,
  rows = 3,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; hint?: ReactNode }) {
  const id = useId()
  const area = (
    <textarea id={id} rows={rows} {...rest} className={cn(CONTROL, 'py-2.5 leading-6', className)} />
  )
  return label ? (
    <Field label={label} hint={hint} htmlFor={id}>
      {area}
    </Field>
  ) : (
    area
  )
}

export function Select({
  label,
  hint,
  className,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { label?: string; hint?: ReactNode }) {
  const id = useId()
  const select = (
    <select id={id} {...rest} className={cn(CONTROL, 'h-10 appearance-none pr-9', className)}>
      {children}
    </select>
  )
  const wrapped = (
    <div className="relative">
      {select}
      <span className="pointer-events-none absolute top-1/2 right-3.5 -translate-y-1/2 text-content-3">
        ▾
      </span>
    </div>
  )
  return label ? (
    <Field label={label} hint={hint} htmlFor={id}>
      {wrapped}
    </Field>
  ) : (
    wrapped
  )
}
