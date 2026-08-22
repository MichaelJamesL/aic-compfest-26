import { useRequest } from '../lib/useRequest'
import { api } from '../api/client'
import { cn } from '../lib/cn'

/**
 * Engine mode, always visible. Presenting stub output as model output is the
 * one thing that would sink the submission — never hide this. SCREENS.md §0.
 */
export function StatusCard() {
  const { data, error } = useRequest(() => api.capabilities(), [])
  // Defensive: an unexpected body must not take down the whole shell.
  const live = data?.capabilities?.ai_engine === true
  const unknown = !data?.capabilities || error != null

  return (
    <div className="rounded-card bg-mint p-4 text-card">
      <h3 className="text-[13px] font-medium">Mesin analisis</h3>
      <p className="mt-2 flex items-center gap-2 text-[13px] font-medium">
        <span
          className={cn(
            'size-1.5 rounded-full',
            unknown ? 'bg-ink-faint' : live ? 'bg-teal' : 'bg-burnt',
          )}
          aria-hidden
        />
        {unknown ? 'Memeriksa…' : live ? 'DeepSeek aktif' : 'Mode offline (stub)'}
      </p>
      <p className="mt-3 text-xs leading-5 text-ink-dim">
        Semua proses sinkron. Tidak ada background job, auto-tuning, maupun loop umpan
        balik otomatis.
      </p>
    </div>
  )
}
