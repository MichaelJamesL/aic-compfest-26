import type { ReactNode } from 'react'
import { AlertCircle, RotateCcw } from 'lucide-react'
import { ApiError, errorCopy } from '../api/client'
import { Button } from './Button'

/** A sentence saying what to do. No illustration. SCREENS.md "State coverage". */
export function EmptyState({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-4 py-8">
      <p className="max-w-prose text-sm text-dim">{children}</p>
      {action}
    </div>
  )
}

/** Mapped copy, the request_id, and one retry action. Never a raw token. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const requestId = error instanceof ApiError ? error.requestId : null
  return (
    <div className="flex flex-col items-start gap-4 py-8">
      <div className="flex items-start gap-3">
        <AlertCircle size={18} className="mt-0.5 shrink-0 text-crit-text" />
        <div>
          <p className="text-sm text-white">{errorCopy(error)}</p>
          {requestId && <p className="mt-1 text-xs text-faint">Request ID: {requestId}</p>}
        </div>
      </div>
      {onRetry && (
        <Button onClick={onRetry} size="sm" icon={<RotateCcw size={14} />}>
          Coba lagi
        </Button>
      )}
    </div>
  )
}

/**
 * Partial input is a first-class state in this product, not a degraded one.
 * The absence is the message — never hide the section.
 */
export function MissingInput({ children }: { children: ReactNode }) {
  return <p className="text-[13px] text-faint">{children}</p>
}
