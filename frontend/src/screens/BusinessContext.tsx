import { useState } from 'react'
import { Plus, Save, Trash2, UserPlus } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { Card, SectionTitle } from '../ui/Card'
import { Button } from '../ui/Button'
import { TextInput } from '../ui/Field'
import { Table, Td, Th, Tr } from '../ui/Table'
import { EmptyState, ErrorState } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'
import type {
  Asset,
  BusinessContext,
  DayOfWeek,
  SparePart,
  TechnicianSchedule,
  TimeInterval,
} from '../api/types'

const DAYS: { key: DayOfWeek; label: string }[] = [
  { key: 'monday', label: 'Senin' },
  { key: 'tuesday', label: 'Selasa' },
  { key: 'wednesday', label: 'Rabu' },
  { key: 'thursday', label: 'Kamis' },
  { key: 'friday', label: 'Jumat' },
  { key: 'saturday', label: 'Sabtu' },
  { key: 'sunday', label: 'Minggu' },
]

/** `<input type="time">` speaks "HH:MM"; the API speaks "HH:MM:SS". */
type Pair = { start: string; end: string }
type Week = Record<DayOfWeek, Pair>

const emptyWeek = (): Week =>
  Object.fromEntries(DAYS.map((day) => [day.key, { start: '', end: '' }])) as Week

function weekFrom(intervals: Partial<Record<DayOfWeek, TimeInterval>> | undefined): Week {
  const week = emptyWeek()
  for (const [day, interval] of Object.entries(intervals ?? {})) {
    if (interval) week[day as DayOfWeek] = { start: interval.start.slice(0, 5), end: interval.end.slice(0, 5) }
  }
  return week
}

/** Only complete pairs travel: a half-filled row is an unanswered question, not a constraint. */
function weekToApi(week: Week): Partial<Record<DayOfWeek, TimeInterval>> {
  return Object.fromEntries(
    DAYS.filter(({ key }) => week[key].start && week[key].end).map(({ key }) => [key, week[key]]),
  )
}

type Technician = { name: string; role: string; specialty: string; work: Week; busy: Week }

const blankTechnician = (): Technician => ({
  name: '',
  role: '',
  specialty: '',
  work: emptyWeek(),
  busy: emptyWeek(),
})

function technicianFrom(technician: TechnicianSchedule): Technician {
  return {
    name: technician.name,
    role: technician.role,
    specialty: technician.specialty ?? '',
    work: weekFrom(technician.work_time),
    // ponytail: one busy block per day. The contract takes a list — add rows if a
    // technician really is booked twice in one shift.
    busy: weekFrom(
      Object.fromEntries(
        Object.entries(technician.occupied_time ?? {}).map(([day, list]) => [day, list?.[0]]),
      ),
    ),
  }
}

function technicianToApi(technician: Technician): TechnicianSchedule {
  return {
    name: technician.name.trim(),
    role: technician.role.trim() || 'teknisi',
    specialty: technician.specialty.trim() || null,
    work_time: weekToApi(technician.work),
    occupied_time: Object.fromEntries(
      Object.entries(weekToApi(technician.busy)).map(([day, interval]) => [day, [interval]]),
    ),
  }
}

export function BusinessContextScreen() {
  const context = useRequest(() => api.businessContext(), [])
  const assets = useRequest(() => api.assets(), [])
  return (
    <AppShell
      title="Konteks bisnis"
      subtitle="Berlaku untuk seluruh pabrik — diisi sekali, dipakai setiap analisis."
    >
      {context.loading && <Skeleton className="h-64 rounded-card" />}
      {context.error != null && <ErrorState error={context.error} onRetry={context.reload} />}
      {context.data && assets.data && <Form initial={context.data} assets={assets.data} />}
    </AppShell>
  )
}

/** One column per schedule, seven rows — the week reads the same wherever it appears. */
function WeekTable({
  columns,
}: {
  columns: { label: string; week: Week; onChange: (week: Week) => void }[]
}) {
  return (
    <Table className="min-w-[420px]">
      <thead>
        <tr>
          <Th>Hari</Th>
          {columns.map((column) => (
            <Th key={column.label}>{column.label}</Th>
          ))}
        </tr>
      </thead>
      <tbody>
        {DAYS.map(({ key, label }) => (
          <Tr key={key}>
            <Td tone="primary">{label}</Td>
            {columns.map(({ label: column, week, onChange }) => (
              <Td key={column}>
                <div className="flex items-center gap-1.5">
                  {(['start', 'end'] as const).map((edge) => (
                    <input
                      key={edge}
                      type="time"
                      aria-label={`${column} ${label} ${edge === 'start' ? 'mulai' : 'selesai'}`}
                      value={week[key][edge]}
                      onChange={(event) =>
                        onChange({ ...week, [key]: { ...week[key], [edge]: event.target.value } })
                      }
                      className="h-9 rounded-control border border-line bg-surface-card px-2 text-[13px] text-content"
                    />
                  ))}
                </div>
              </Td>
            ))}
          </Tr>
        ))}
      </tbody>
    </Table>
  )
}

function Form({ initial, assets }: { initial: BusinessContext; assets: Asset[] }) {
  const [production, setProduction] = useState(() => weekFrom(initial.production_schedule?.work_time))
  const [technicians, setTechnicians] = useState<Technician[]>(() =>
    initial.technicians.map(technicianFrom),
  )
  const [inventory, setInventory] = useState<SparePart[]>(initial.inventory)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)

  function editTechnician(index: number, patch: Partial<Technician>) {
    setTechnicians((roster) => roster.map((one, i) => (i === index ? { ...one, ...patch } : one)))
  }

  function editPart(index: number, patch: Partial<SparePart>) {
    setInventory((parts) => parts.map((part, i) => (i === index ? { ...part, ...patch } : part)))
  }

  async function save() {
    setSaving(true)
    setError(null)
    setNotice(null)
    const productionWeek = weekToApi(production)
    try {
      await api.setBusinessContext({
        production_schedule: Object.keys(productionWeek).length ? { work_time: productionWeek } : null,
        // A row without a name is half-typed, not data.
        inventory: inventory
          .filter((part) => part.name.trim())
          .map((part) => ({ ...part, id: part.id || part.name.trim().toLowerCase().replace(/\s+/g, '-') })),
        technicians: technicians.filter((one) => one.name.trim()).map(technicianToApi),
      })
      setNotice('Konteks bisnis tersimpan.')
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-3">
      <Card>
        <SectionTitle>Jadwal produksi</SectionTitle>
        <p className="mt-2 text-[13px] text-content-3">
          Menentukan jendela maintenance. Hari yang dikosongkan berarti tidak ada produksi.
        </p>
        <div className="mt-4">
          <WeekTable columns={[{ label: 'Produksi', week: production, onChange: setProduction }]} />
        </div>
      </Card>

      <Card>
        <SectionTitle>Teknisi</SectionTitle>
        <p className="mt-2 text-[13px] text-content-3">
          Jam kerja menentukan siapa yang bisa mengerjakan work order, jam sibuk menentukan kapan.
          Teknisi tanpa nama tidak ikut tersimpan.
        </p>

        <div className="mt-4 space-y-3">
          {technicians.length === 0 && (
            <EmptyState>
              Belum ada teknisi. Tanpa roster, usulan penugasan hanya berdasarkan skill.
            </EmptyState>
          )}

          {technicians.map((technician, index) => (
            <div key={index} className="rounded-card border border-line p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="grid flex-1 gap-4 md:grid-cols-3">
                  <TextInput
                    label={`Nama teknisi ${index + 1}`}
                    placeholder="Budi"
                    value={technician.name}
                    onChange={(event) => editTechnician(index, { name: event.target.value })}
                  />
                  <TextInput
                    label={`Peran teknisi ${index + 1}`}
                    placeholder="teknisi mekanik"
                    value={technician.role}
                    onChange={(event) => editTechnician(index, { role: event.target.value })}
                  />
                  <TextInput
                    label={`Spesialisasi teknisi ${index + 1}`}
                    placeholder="rotating equipment"
                    value={technician.specialty}
                    onChange={(event) => editTechnician(index, { specialty: event.target.value })}
                  />
                </div>
                <Button
                  size="sm"
                  className="mt-6"
                  icon={<Trash2 size={14} />}
                  aria-label={`Hapus teknisi ${index + 1}`}
                  onClick={() => setTechnicians((roster) => roster.filter((_, i) => i !== index))}
                />
              </div>
              <div className="mt-4">
                <WeekTable
                  columns={[
                    {
                      label: `Teknisi ${index + 1} kerja`,
                      week: technician.work,
                      onChange: (week) => editTechnician(index, { work: week }),
                    },
                    {
                      label: `Teknisi ${index + 1} sibuk`,
                      week: technician.busy,
                      onChange: (week) => editTechnician(index, { busy: week }),
                    },
                  ]}
                />
              </div>
            </div>
          ))}
        </div>

        <Button
          className="mt-3"
          icon={<UserPlus size={15} />}
          onClick={() => setTechnicians((roster) => [...roster, blankTechnician()])}
        >
          Tambah teknisi
        </Button>
      </Card>

      <Card>
        <SectionTitle>Stok sparepart</SectionTitle>
        <div className="mt-4">
          <Table>
            <thead>
              <tr>
                <Th>Nama</Th>
                <Th>Stok</Th>
                <Th>Satuan</Th>
                <Th>Stok minimum</Th>
                <Th>ETA</Th>
                <Th>Mesin</Th>
                <Th>{''}</Th>
              </tr>
            </thead>
            <tbody>
              {inventory.map((part, index) => (
                <Tr key={index}>
                  <Td>
                    <TextInput
                      aria-label={`Nama sparepart ${index + 1}`}
                      value={part.name}
                      onChange={(e) => editPart(index, { name: e.target.value })}
                    />
                  </Td>
                  <Td>
                    <TextInput
                      type="number"
                      min={0}
                      aria-label={`Stok sparepart ${index + 1}`}
                      value={part.stock}
                      onChange={(e) => editPart(index, { stock: Number(e.target.value) })}
                    />
                  </Td>
                  <Td>
                    <TextInput
                      aria-label={`Satuan sparepart ${index + 1}`}
                      value={part.unit}
                      onChange={(e) => editPart(index, { unit: e.target.value })}
                    />
                  </Td>
                  <Td>
                    <TextInput
                      type="number"
                      min={0}
                      aria-label={`Stok minimum sparepart ${index + 1}`}
                      value={part.min_stock ?? ''}
                      onChange={(e) =>
                        editPart(index, { min_stock: e.target.value ? Number(e.target.value) : null })
                      }
                    />
                  </Td>
                  <Td>
                    <TextInput
                      aria-label={`ETA sparepart ${index + 1}`}
                      placeholder="2 hari"
                      value={part.eta ?? ''}
                      onChange={(e) => editPart(index, { eta: e.target.value || null })}
                    />
                  </Td>
                  <Td>
                    <fieldset className="max-h-24 w-44 overflow-y-auto">
                      <legend className="sr-only">{`Mesin sparepart ${index + 1}`}</legend>
                      {assets.map((asset) => (
                        <label key={asset.id} className="flex items-center gap-2 py-0.5 text-[13px]">
                          <input
                            type="checkbox"
                            aria-label={`${asset.name} pakai sparepart ${index + 1}`}
                            checked={part.asset_ids.includes(asset.id)}
                            onChange={(event) =>
                              editPart(index, {
                                asset_ids: event.target.checked
                                  ? [...part.asset_ids, asset.id]
                                  : part.asset_ids.filter((id) => id !== asset.id),
                              })
                            }
                          />
                          {asset.name}
                        </label>
                      ))}
                      {assets.length === 0 && <span className="text-xs text-content-3">Belum ada mesin</span>}
                    </fieldset>
                  </Td>
                  <Td align="right">
                    <Button
                      size="sm"
                      icon={<Trash2 size={14} />}
                      aria-label={`Hapus sparepart ${index + 1}`}
                      onClick={() => setInventory((parts) => parts.filter((_, i) => i !== index))}
                    />
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
          {inventory.length === 0 && (
            <p className="py-3 text-[13px] text-content-3">
              Belum ada sparepart. Tanpa stok, ETA tidak bisa jadi blocker penjadwalan.
            </p>
          )}
          <p className="mt-1 text-xs text-content-3">
            Analisis sebuah mesin hanya melihat sparepart yang terpasang ke mesin itu. Satu
            sparepart boleh dipakai banyak mesin.
          </p>
          <Button
            className="mt-3"
            icon={<Plus size={15} />}
            onClick={() =>
              setInventory((parts) => [
                ...parts,
                { id: '', name: '', stock: 0, unit: 'pcs', min_stock: null, eta: null, asset_ids: [] },
              ])
            }
          >
            Tambah sparepart
          </Button>
        </div>
      </Card>

      {error != null && (
        <Card>
          <ErrorState error={error} onRetry={save} />
        </Card>
      )}

      <div className="flex items-center gap-3">
        <Button variant="primary" icon={<Save size={15} />} disabled={saving} onClick={save}>
          Simpan konteks
        </Button>
        {notice && <p className="text-[13px] text-content-2">{notice}</p>}
      </div>
    </div>
  )
}
