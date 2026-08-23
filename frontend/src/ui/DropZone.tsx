import { useRef, useState, type ReactNode } from 'react'
import { cn } from '../lib/cn'

/**
 * Dashed hairline, 120 tall, solid border on drag-over. No animation beyond
 * that. VISUAL_LANGUAGE.md §7 / SCREENS.md §1.
 */
export function DropZone({
  label,
  hint,
  icon,
  accept,
  multiple = false,
  disabled = false,
  onFiles,
}: {
  label: string
  hint: string
  icon: ReactNode
  accept?: string
  multiple?: boolean
  disabled?: boolean
  onFiles: (files: File[]) => void
}) {
  const [over, setOver] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  function handle(list: FileList | null) {
    if (!list?.length) return
    onFiles(Array.from(list))
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault()
        setOver(false)
        if (!disabled) handle(event.dataTransfer.files)
      }}
    >
      <button
        type="button"
        disabled={disabled}
        onClick={() => input.current?.click()}
        className={cn(
          'flex h-[120px] w-full flex-col items-center justify-center gap-1.5 rounded-control',
          'border border-dashed px-4 text-center transition-colors duration-100',
          'disabled:pointer-events-none disabled:opacity-40',
          over ? 'border-solid border-dim bg-surface-raised' : 'border-line-strong hover:border-dim',
        )}
      >
        <span className="text-content-2">{icon}</span>
        <span className="text-[13px] font-medium text-content">{label}</span>
        <span className="text-xs text-content-3">{hint}</span>
      </button>
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(event) => {
          handle(event.target.files)
          event.target.value = ''
        }}
      />
    </div>
  )
}
