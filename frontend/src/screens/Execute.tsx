import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { ArrowLeft, Camera, Send } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api, getIdentity } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { Card, CardTitle, SectionTitle } from '../ui/Card'
import { Button } from '../ui/Button'
import { TextArea, TextInput } from '../ui/Field'
import { DropZone } from '../ui/DropZone'
import { ErrorState } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'

/**
 * Deliberately plain — this is a form filled on a factory floor. It submits a
 * result; it must never mark the work order complete. Verification decides the
 * outcome. SCREENS.md §5.
 */
export function ExecuteScreen() {
  const { id = '' } = useParams()
  const { data, error, loading, reload } = useRequest(
    () => api.workOrders().then((list) => list.find((order) => order.id === id) ?? null),
    [id],
  )

  const [done, setDone] = useState<string[]>([])
  const [findings, setFindings] = useState('')
  const [parts, setParts] = useState('')
  const [hours, setHours] = useState('')

  if (loading) {
    return (
      <AppShell title="Eksekusi">
        <Skeleton className="h-64 rounded-card" />
      </AppShell>
    )
  }

  if (error || !data) {
    return (
      <AppShell title="Eksekusi">
        <ErrorState error={error ?? new Error('not found')} onRetry={reload} />
      </AppShell>
    )
  }

  const steps = data.details_json.steps ?? []
  const isTechnician = getIdentity().user === 'demo-technician'

  return (
    <AppShell title={data.title} subtitle="Kirim hasil pekerjaan untuk diverifikasi.">
      <Link
        to={`/work-orders/${data.id}`}
        className="mb-3 inline-flex items-center gap-1.5 text-[13px] text-faint hover:text-white"
      >
        <ArrowLeft size={14} /> Kembali ke work order
      </Link>

      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-12 space-y-3 xl:col-span-8">
          <Card>
            <SectionTitle>Langkah SOP</SectionTitle>
            <ul className="mt-4 space-y-1">
              {steps.map((step) => (
                <li key={step}>
                  <label className="flex cursor-pointer items-start gap-3 rounded-control px-2 py-2 text-[13px] text-dim hover:bg-raised">
                    <input
                      type="checkbox"
                      className="mt-1 size-3.5 shrink-0 accent-white"
                      checked={done.includes(step)}
                      onChange={(event) =>
                        setDone((current) =>
                          event.target.checked
                            ? [...current, step]
                            : current.filter((item) => item !== step),
                        )
                      }
                    />
                    <span className={done.includes(step) ? 'text-white' : undefined}>{step}</span>
                  </label>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-faint">
              {done.length} dari {steps.length} langkah ditandai selesai.
            </p>
          </Card>

          <Card>
            <SectionTitle>Hasil pekerjaan</SectionTitle>
            <div className="mt-4 space-y-4">
              <TextArea
                label="Temuan di lapangan"
                rows={4}
                placeholder="Insert aus tidak merata di satu sisi; runout spindle 0.03 mm."
                value={findings}
                onChange={(event) => setFindings(event.target.value)}
              />
              <div className="grid gap-4 md:grid-cols-2">
                <TextInput
                  label="Sparepart terpakai"
                  hint="Pisahkan dengan koma"
                  placeholder="TNMG160408"
                  value={parts}
                  onChange={(event) => setParts(event.target.value)}
                />
                <TextInput
                  label="Waktu pengerjaan (jam)"
                  type="number"
                  min={0}
                  step={0.5}
                  placeholder="3"
                  value={hours}
                  onChange={(event) => setHours(event.target.value)}
                />
              </div>
            </div>
          </Card>

          <Card>
            <SectionTitle>Bukti</SectionTitle>
            <div className="mt-4">
              <DropZone
                label="Unggah foto hasil pekerjaan"
                hint="Belum tersedia — backend belum menerima berkas gambar"
                icon={<Camera size={20} />}
                disabled
                onFiles={() => {}}
              />
            </div>
          </Card>
        </div>

        <div className="col-span-12 xl:col-span-4">
          <Card tint="clay" className="xl:sticky xl:top-24">
            <CardTitle>Yang terjadi setelah ini</CardTitle>
            <p className="mt-3 text-[13px] leading-6">
              Hasil ini tidak menutup work order. AI memverifikasi bukti dan mengeluarkan
              verdict — bukan menyatakan selesai sendiri.
            </p>
            <p className="mt-4 border-t border-ink/10 pt-4 text-xs leading-5 text-soft">
              Verifikasi berjalan satu kali, sinkron, atas permintaan. Tidak ada loop umpan
              balik otomatis.
            </p>
          </Card>
        </div>
      </div>

      <div className="sticky bottom-4 z-20 mt-3">
        <div className="glass-dark flex flex-wrap items-center gap-3 rounded-card px-5 py-3.5">
          <p className="flex-1 text-[13px] text-dim">
            {isTechnician
              ? 'Kirim hasil untuk diverifikasi.'
              : 'Form ini diisi oleh teknisi — ganti peran di pojok kanan atas.'}
          </p>
          <Button
            size="sm"
            variant="primary"
            icon={<Send size={14} />}
            disabled
            title="Route POST /work-orders/{id}/result belum ada di backend"
          >
            Kirim hasil pekerjaan
          </Button>
        </div>
      </div>

      <p className="mt-3 text-xs leading-5 text-faint">
        Pengiriman hasil belum bisa diselesaikan: backend belum punya route
        <span className="text-dim"> POST /work-orders/{'{id}'}/result</span>. Lihat
        docs/API.md bagian “Routes that must exist and do not”.
      </p>
    </AppShell>
  )
}
