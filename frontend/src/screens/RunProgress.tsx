import { useEffect, useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { Card, SectionTitle } from '../ui/Card'
import { Button } from '../ui/Button'
import { cn } from '../lib/cn'

/**
 * POST /analyses blocks for up to 120s with no progress endpoint, so this is
 * an *estimate*, and it says so. Never a spinner for two minutes.
 * SCREENS.md §2 "The waiting state".
 */
interface Stage {
  label: string
  kind: string
  /** Seconds into the engine call at which this stage is assumed to start. */
  at: number
  available: boolean
}

const STAGES: Stage[] = [
  { label: 'Deteksi anomali', kind: 'deterministik', at: 0, available: true },
  { label: 'Klasifikasi defect QC', kind: 'model fine-tuned', at: 1, available: false },
  { label: 'Mapping defect → failure mode', kind: 'tabel pengetahuan', at: 2, available: false },
  { label: 'Retrieval SOP & histori', kind: 'deterministik', at: 2, available: true },
  { label: 'Menyusun diagnosis', kind: 'DeepSeek', at: 4, available: true },
  { label: 'Jendela maintenance', kind: 'deterministik', at: 30, available: false },
  { label: 'Draft work order', kind: 'DeepSeek', at: 32, available: true },
]

const TIMEOUT_S = 120

export function RunProgress({
  step,
  readingCount,
  onCancel,
}: {
  step: number
  readingCount: number
  onCancel?: () => void
}) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setElapsed((value) => value + 1), 1000)
    return () => clearInterval(timer)
  }, [])

  const outer = [
    { label: `Mengunggah ${readingCount} pembacaan sensor`, done: step > 1, active: step === 1, skip: readingCount === 0 },
    { label: 'Menyimpan kondisi mesin', done: step > 2, active: step === 2, skip: false },
    { label: 'Memanggil mesin analisis', done: false, active: step === 3, skip: false },
  ].filter((item) => !item.skip)

  const engineElapsed = step >= 3 ? elapsed : 0
  const overtime = engineElapsed > TIMEOUT_S

  return (
    <div className="grid grid-cols-12 gap-3">
      {/*
        The wait can run to two minutes with no progress from the server, so it
        is announced rather than left silent for anyone not watching the list.
      */}
      <p aria-live="polite" className="sr-only">
        {overtime
          ? 'Analisis masih berjalan, melewati perkiraan waktu.'
          : `Analisis sedang berjalan, ${engineElapsed} detik.`}
      </p>

      <Card className="col-span-12 xl:col-span-7">
        <div className="flex items-center gap-3">
          <SectionTitle>Proses</SectionTitle>
          {onCancel && (
            <Button size="sm" variant="ghost" className="ml-auto" onClick={onCancel}>
              Batalkan
            </Button>
          )}
        </div>
        <ol className="mt-4 space-y-3">
          {outer.map((item) => (
            <li key={item.label} className="flex items-center gap-3 text-[13px]">
              <Marker done={item.done} active={item.active} />
              <span className={item.done || item.active ? 'text-content' : 'text-content-3'}>
                {item.label}
              </span>
            </li>
          ))}
        </ol>

        <div className="mt-6 border-t border-line pt-5">
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="text-sm font-medium">Perkiraan tahap</h3>
            <span className="tnum text-xs text-content-3">
              {overtime ? 'masih berjalan…' : `${engineElapsed}s`}
            </span>
          </div>
          <p className="mt-1.5 text-xs leading-5 text-content-3">
            Urutan ini mencerminkan pipeline, bukan telemetri dari server — backend tidak
            mengirim progres antara.
          </p>

          <ol className="mt-4 space-y-3">
            {STAGES.map((stage) => {
              const reached = stage.available && engineElapsed > stage.at
              const running =
                stage.available && !overtime && reached && engineElapsed <= stage.at + 4
              return (
                <li key={stage.label} className="flex items-center gap-3 text-[13px]">
                  <Marker done={reached && !running} active={running} muted={!stage.available} />
                  <span className={cn('flex-1', stage.available ? 'text-content-2' : 'text-content-3')}>
                    {stage.label}
                  </span>
                  <span className="text-[11.5px] text-content-3">
                    {stage.available ? stage.kind : 'belum tersedia'}
                  </span>
                </li>
              )
            })}
          </ol>
        </div>
      </Card>
    </div>
  )
}

function Marker({
  done,
  active,
  muted,
}: {
  done: boolean
  active: boolean
  muted?: boolean
}) {
  if (active) return <Loader2 size={14} className="shrink-0 animate-spin text-content" />
  if (done)
    return (
      <span className="grid size-3.5 shrink-0 place-items-center rounded-full bg-ok-fill text-ok-text">
        <Check size={9} strokeWidth={3} />
      </span>
    )
  return (
    <span
      className={cn(
        'size-3.5 shrink-0 rounded-full border',
        muted ? 'border-line' : 'border-line-strong',
      )}
      aria-hidden
    />
  )
}
