import { useEffect, useState } from 'react'

/**
 * One transient message, bottom-right. Deliberately not a provider or a queue:
 * a screen shows one outcome at a time, and a rejected action needs to be read
 * where it happened, not stacked with three others.
 *
 * `role="status"` so it is announced without stealing focus. It does not
 * auto-dismiss errors — a failure the user must act on should not vanish while
 * they are still reading it.
 */
export function Toast({
  message,
  tone = 'error',
  onClose,
}: {
  message: string | null
  tone?: 'error' | 'success'
  onClose: () => void
}) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    setVisible(Boolean(message))
    if (!message || tone === 'error') return
    const timer = setTimeout(onClose, 4000)
    return () => clearTimeout(timer)
  }, [message, tone, onClose])

  if (!message || !visible) return null

  return (
    <div
      role="status"
      className="fixed right-4 bottom-4 z-50 max-w-sm rounded-card border border-line bg-surface-card p-3.5 shadow-lg"
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className={`mt-1.5 size-2 shrink-0 rounded-full ${tone === 'error' ? 'bg-crit' : 'bg-ok'}`}
        />
        <p className="text-[13px] leading-5 text-content">{message}</p>
        <button
          type="button"
          onClick={onClose}
          aria-label="Tutup notifikasi"
          className="ml-auto text-content-3 hover:text-content"
        >
          ×
        </button>
      </div>
    </div>
  )
}
