import { useRequest } from '../lib/useRequest'
import { api } from '../api/client'
import { cn } from '../lib/cn'

function useEngineMode() {
  const { data, error } = useRequest(() => api.capabilities(), [])
  // Defensive: an unexpected body must not take down the whole shell.
  const unknown = !data?.capabilities || error != null
  return {
    unknown,
    live: data?.capabilities?.ai_engine === true,
    label: unknown ? 'Memeriksa…' : data?.capabilities?.ai_engine ? 'DeepSeek aktif' : 'Mode offline (stub)',
  }
}

/**
 * The icon-rail version. The engine mode must survive the narrow layout —
 * presenting stub output as model output is the one thing that would sink the
 * submission.
 */
export function StatusDotCompact() {
  const { unknown, live, label } = useEngineMode()
  return (
    <div
      title={`Mesin analisis: ${label}`}
      aria-label={`Mesin analisis: ${label}`}
      className="grid size-10 place-items-center rounded-control bg-mint"
    >
      <span
        className={cn(
          'size-2 rounded-full',
          unknown ? 'bg-content-3' : live ? 'bg-teal-ink' : 'bg-burnt',
        )}
      />
    </div>
  )
}

/**
 * Engine mode, always visible. Presenting stub output as model output is the
 * one thing that would sink the submission — never hide this. SCREENS.md §0.
 */
export function StatusCard() {
  const { unknown, live, label } = useEngineMode()

  return (
    <div className="rounded-card bg-mint p-4 text-card">
      <h3 className="text-[13px] font-medium">Mesin analisis</h3>
      <p className="mt-2 flex items-center gap-2 text-[13px] font-medium">
        <span
          className={cn(
            'size-1.5 rounded-full',
            unknown ? 'bg-content-3' : live ? 'bg-teal-ink' : 'bg-burnt',
          )}
          aria-hidden
        />
        {label}
      </p>
    </div>
  )
}
