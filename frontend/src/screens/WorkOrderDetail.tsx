import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { CalendarClock, ShieldAlert } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api, errorCopy, getIdentity } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { formatDateTime, formatDuration } from '../lib/format'
import { WORK_ORDER, priorityLabel, priorityTone } from '../lib/severity'
import { Card, CardTitle, SectionTitle } from '../ui/Card'
import { Select, TextArea, TextInput } from '../ui/Field'
import { Badge } from '../ui/Badge'
import { BackLink, Button, LinkButton } from '../ui/Button'
import { StateTrack } from '../ui/StateTrack'
import { ErrorState } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'
import { Toast } from '../ui/Toast'
import type { WorkOrder } from '../api/types'

/** Only these roles may approve or reject. SCREENS.md §3 approval bar. */
const APPROVERS = ['demo-manager', 'demo-admin']

export function WorkOrderDetailScreen() {
  const { id = '' } = useParams()
  const { data, error, loading, reload, setData } = useRequest(
    () => api.workOrders().then((list) => list.find((order) => order.id === id) ?? null),
    [id],
  )

  if (loading) {
    return (
      <AppShell title="Work order">
        <Skeleton className="h-64 rounded-card" />
      </AppShell>
    )
  }

  if (error || !data) {
    return (
      <AppShell title="Work order">
        <Card>
          <ErrorState
            error={error ?? new Error('not found')}
            onRetry={reload}
            action={
              <LinkButton to="/work-orders" size="sm" variant="primary">Semua work order</LinkButton>
            }
          />
        </Card>
      </AppShell>
    )
  }

  return <Detail order={data} onChange={setData} />
}

function Detail({ order, onChange }: { order: WorkOrder; onChange: (o: WorkOrder) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const canApprove = APPROVERS.includes(getIdentity().user)
  const state = WORK_ORDER[order.status]
  const details = order.details_json

  async function act(action: string) {
    setBusy(true)
    setError(null)
    try {
      onChange(await api.transition(order.id, action))
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  async function reject() {
    setBusy(true)
    setError(null)
    try {
      onChange(await api.rejectWorkOrder(order.id, reason.trim()))
      setRejecting(false)
      setReason('')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell title={order.title} subtitle={`Work order ${order.id.slice(0, 8)}`}>
      <BackLink to={"/work-orders"}>Semua work order</BackLink>

      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={priorityTone(order.priority)}>Prioritas {priorityLabel(order.priority)}</Badge>
          <Badge tone={state.tone}>{state.label}</Badge>
          <span className="ml-auto text-xs text-content-3">
            Dibuat {formatDateTime(order.created_at)}
          </span>
        </div>

        <div className="mt-5 border-t border-line pt-5">
          <StateTrack status={order.status} />
        </div>
      </Card>

      <Assignment order={order} canEdit={canApprove} onChange={onChange} onError={setToast} />

      <Card className="mt-3">
        <SectionTitle>Pekerjaan</SectionTitle>
        <p className="mt-2 max-w-prose text-[13px] leading-6 text-content-2">{order.description}</p>

        <div className="mt-5 grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <CardTitle muted>Langkah dari SOP</CardTitle>
            <ol className="mt-2.5 space-y-2">
              {details.steps?.map((step, index) => (
                <li key={step} className="flex gap-3 text-[13px] text-content-2">
                  <span className="tnum shrink-0 text-content-3">{index + 1}.</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>

          <dl className="space-y-4 lg:col-span-5">
            <div>
              <dt className="text-xs text-content-3">Sparepart</dt>
              <dd className="mt-1 text-[13px] text-content-2">
                {details.parts?.length ? details.parts.join(', ') : 'Tidak ada'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-content-3">Skill</dt>
              <dd className="mt-1 text-[13px] text-content-2">
                {details.required_skills?.length ? details.required_skills.join(', ') : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-content-3">Estimasi durasi</dt>
              <dd className="tnum mt-1 text-[13px] text-content-2">
                {formatDuration(details.est_duration_h)}
              </dd>
            </div>
          </dl>
        </div>

        {details.safety_notes?.length > 0 && (
          <div className="mt-5 rounded-control border border-crit/40 p-4">
            <p className="flex items-center gap-2 text-[13px] font-medium text-crit-text">
              <ShieldAlert size={14} /> Catatan keselamatan
            </p>
            <ul className="mt-2 space-y-1">
              {details.safety_notes.map((note) => (
                <li key={note} className="text-[13px] text-content-2">
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {error != null && <p className="mt-3 text-[13px] text-crit-text">{errorCopy(error)}</p>}

      <div className="sticky bottom-4 z-20 mt-3">
        <div className="glass-light flex flex-wrap items-center gap-3 rounded-card px-5 py-3.5">
          <p className="flex-1 text-[13px] text-content-2">
            AI mengusulkan dan menyiapkan; coordinator menyetujui; teknisi mengeksekusi; AI
            memverifikasi bukti.
          </p>

          <LinkButton to={`/work-orders/${order.id}/execute`} size="sm">
            Form teknisi
          </LinkButton>
          <LinkButton to={`/work-orders/${order.id}/report`} size="sm">
            Verifikasi & laporan
          </LinkButton>

          {order.status === 'draft' && (
            <Button size="sm" variant="primary" disabled={busy} onClick={() => act('submit')}>
              Ajukan persetujuan
            </Button>
          )}

          {order.status === 'pending_approval' && (
            <>
              <Button
                size="sm"
                variant="ghost"
                disabled={busy || !canApprove}
                title={canApprove ? undefined : 'Hanya coordinator yang bisa menolak'}
                onClick={() => setRejecting(true)}
              >
                Tolak
              </Button>
              <Button
                size="sm"
                variant="primary"
                disabled={busy || !canApprove}
                title={canApprove ? undefined : 'Hanya coordinator yang bisa menyetujui'}
                onClick={() => act('approve')}
              >
                Setujui
              </Button>
            </>
          )}

          {order.status === 'approved' && (
            <Button size="sm" variant="primary" disabled={busy} onClick={() => act('schedule')}>
              Jadwalkan
            </Button>
          )}
          {order.status === 'scheduled' && (
            <Button size="sm" variant="primary" disabled={busy} onClick={() => act('start')}>
              Mulai kerjakan
            </Button>
          )}
        </div>
      </div>

      {rejecting && (
        <Card className="mt-3">
          <SectionTitle>Alasan penolakan</SectionTitle>
          <p className="mt-2 text-[13px] text-content-3">
            Alasan disimpan pada work order dan dibaca analisis berikutnya.
          </p>
          <div className="mt-4">
            <TextArea
              label="Alasan"
              placeholder="Sparepart belum datang; tunda sampai insert tiba."
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
          <div className="mt-4 flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => setRejecting(false)}>
              Batal
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={busy || reason.trim().length === 0}
              onClick={reject}
            >
              Tolak work order
            </Button>
          </div>
        </Card>
      )}

      {order.status === 'rejected' && order.details_json.rejection_reason && (
        <Card className="mt-3">
          <SectionTitle>Alasan penolakan</SectionTitle>
          <p className="mt-2 text-[13px] leading-6 text-content-2">
            {order.details_json.rejection_reason}
          </p>
        </Card>
      )}
      <Toast message={toast} onClose={() => setToast(null)} />
    </AppShell>
  )
}


/** "2026-09-01T08:00:00Z" -> "2026-09-01T08:00", what datetime-local speaks. */
function toLocalInput(value: string | null | undefined): string {
  return value ? value.slice(0, 16) : ''
}

function Assignment({
  order,
  canEdit,
  onChange,
  onError,
}: {
  order: WorkOrder
  canEdit: boolean
  onChange: (o: WorkOrder) => void
  onError: (message: string) => void
}) {
  const roster = useRequest(() => api.businessContext().then((c) => c.technicians), [])
  const [editing, setEditing] = useState(false)
  const [technician, setTechnician] = useState(order.assigned_technician ?? '')
  const [start, setStart] = useState(toLocalInput(order.scheduled_start))
  const [end, setEnd] = useState(toLocalInput(order.scheduled_end))
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setTechnician(order.assigned_technician ?? '')
    setStart(toLocalInput(order.scheduled_start))
    setEnd(toLocalInput(order.scheduled_end))
  }, [order.assigned_technician, order.scheduled_start, order.scheduled_end])

  async function save() {
    setSaving(true)
    try {
      onChange(await api.reassign(order.id, {
        technician,
        start: new Date(start).toISOString(),
        end: new Date(end).toISOString(),
      }))
      setEditing(false)
    } catch (err) {
      // A double booking is the coordinator's to resolve, so it is said out
      // loud rather than left as a red line under a field.
      onError(errorCopy(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="mt-3">
      <SectionTitle>Penugasan</SectionTitle>
      {order.assigned_technician ? (
        <p className="mt-2 text-[13px] text-content-2">
          <span className="text-content">{order.assigned_technician}</span> ·{' '}
          {formatDateTime(order.scheduled_start!)} – {formatDateTime(order.scheduled_end!).slice(-5)}
          {order.schedule_note === 'during_production' && (
            <span className="ml-2 text-warn">menabrak jam produksi</span>
          )}
        </p>
      ) : (
        <p className="mt-2 text-[13px] text-content-3">
          Belum ada teknisi —{' '}
          {order.schedule_note === 'no_technicians'
            ? 'roster teknisi masih kosong di Konteks bisnis.'
            : 'tidak ada slot kosong sebelum tenggat prioritas ini.'}
        </p>
      )}

      {canEdit && !editing && (
        <Button
          className="mt-4"
          size="sm"
          icon={<CalendarClock size={14} />}
          onClick={() => setEditing(true)}
        >
          Ubah teknisi / jadwal
        </Button>
      )}

      {canEdit && editing && (
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <Select
            label="Teknisi"
            value={technician}
            onChange={(event) => setTechnician(event.target.value)}
          >
            <option value="">— pilih —</option>
            {(roster.data ?? []).map((one) => (
              <option key={one.name} value={one.name}>
                {one.name} · {one.role}
              </option>
            ))}
          </Select>
          <TextInput
            label="Mulai"
            type="datetime-local"
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />
          <TextInput
            label="Selesai"
            type="datetime-local"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
          />
          <div className="flex items-center gap-3 md:col-span-3">
            <Button
              variant="primary"
              size="sm"
              disabled={saving || !technician || !start || !end}
              onClick={save}
            >
              Simpan jadwal
            </Button>
            <Button size="sm" onClick={() => setEditing(false)}>Batal</Button>
          </div>
        </div>
      )}
    </Card>
  )
}
