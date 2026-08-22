import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { Images, Play, Table2 } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { parseCsv, toReadings, type ParsedReading } from '../lib/csv'
import { FORM_INPUTS } from '../lib/health'
import { Card, CardTitle, SectionTitle } from '../ui/Card'
import { Button } from '../ui/Button'
import { DropZone } from '../ui/DropZone'
import { Select, TextArea, TextInput } from '../ui/Field'
import { EmptyState, ErrorState } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'
import { RunProgress } from './RunProgress'

export function AnalyzeScreen() {
  const navigate = useNavigate()
  const assets = useRequest(() => api.assets(), [])

  const [assetId, setAssetId] = useState('')
  const [readings, setReadings] = useState<ParsedReading[]>([])
  const [csvName, setCsvName] = useState('')
  const [condition, setCondition] = useState('')
  const [schedule, setSchedule] = useState('')
  const [spareparts, setSpareparts] = useState('')
  const [eta, setEta] = useState('')
  const [technicians, setTechnicians] = useState('')
  const [operator, setOperator] = useState('')

  const [running, setRunning] = useState(false)
  const [step, setStep] = useState(0)
  const [error, setError] = useState<unknown>(null)

  const selected = assets.data?.find((asset) => asset.id === assetId) ?? null

  const coverage = useMemo(() => {
    const present: Record<string, boolean> = {
      sensor: readings.length > 0,
      qc: false,
      schedule: schedule.trim().length > 0,
      parts: spareparts.trim().length > 0,
      tech: technicians.trim().length > 0,
      condition: (condition || operator).trim().length > 0,
    }
    return FORM_INPUTS.map((input) => ({ ...input, present: present[input.key] }))
  }, [readings.length, schedule, spareparts, technicians, condition, operator])

  async function run() {
    if (!assetId) return
    setRunning(true)
    setError(null)
    setStep(0)
    try {
      if (readings.length) {
        setStep(1)
        // No batch endpoint yet (docs/API.md), so one request per reading.
        for (const reading of readings) {
          await api.addReading(assetId, { ...reading, source: 'csv', external_id: null })
        }
      }

      setStep(2)
      await api.setBusinessContext(assetId, {
        production_schedule: schedule.trim() || null,
        spareparts: spareparts
          .split(',')
          .map((part) => part.trim())
          .filter(Boolean),
        sparepart_eta: eta.trim() || null,
        technicians_available: technicians.trim() ? Number(technicians) : null,
        operator_report: operator.trim() || null,
      })

      setStep(3)
      const run = await api.analyze(assetId, {
        tier: 'professional',
        manual_condition: condition.trim() || null,
      })
      navigate(`/analysis/${run.id}`)
    } catch (err) {
      setError(err)
      setRunning(false)
    }
  }

  if (running) {
    return (
      <AppShell title="Menjalankan analisis" subtitle={selected?.name}>
        <RunProgress step={step} readingCount={readings.length} />
      </AppShell>
    )
  }

  return (
    <AppShell
      title="Analisis baru"
      subtitle="Satu form, satu keluaran. Analisis berjalan atas permintaan."
    >
      {assets.loading && <Skeleton className="h-64 rounded-card" />}
      {assets.error != null && <ErrorState error={assets.error} onRetry={assets.reload} />}

      {assets.data && assets.data.length === 0 && (
        <Card>
          <EmptyState
            action={<Button variant="primary" onClick={() => navigate('/setup')}>Buka Setup</Button>}
          >
            Belum ada mesin terdaftar. Unggah daftar mesin di Setup sebelum menjalankan
            analisis.
          </EmptyState>
        </Card>
      )}

      {assets.data && assets.data.length > 0 && (
        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-12 space-y-3 xl:col-span-8">
            <Card>
              <SectionTitle>Mesin</SectionTitle>
              <div className="mt-4">
                <Select
                  label="Pilih mesin"
                  value={assetId}
                  onChange={(event) => setAssetId(event.target.value)}
                >
                  <option value="">— pilih —</option>
                  {assets.data.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.name} · {asset.asset_type} · kritikalitas {asset.criticality}
                    </option>
                  ))}
                </Select>
              </div>
            </Card>

            <Card>
              <SectionTitle>Data sensor</SectionTitle>
              <div className="mt-4">
                <DropZone
                  label="Unggah CSV ekspor PLC / sensor"
                  hint="Format panjang (tag,value,unit,recorded_at) atau lebar (timestamp + kolom per tag)"
                  icon={<Table2 size={20} />}
                  accept=".csv"
                  onFiles={async ([file]) => {
                    const parsed = toReadings(parseCsv(await file.text()))
                    setReadings(parsed.slice(0, 500))
                    setCsvName(file.name)
                  }}
                />
                {readings.length > 0 && (
                  <p className="mt-3 text-[13px] text-dim">
                    <span className="text-white">{csvName}</span> — {readings.length} pembacaan,{' '}
                    {new Set(readings.map((r) => r.tag)).size} tag terdeteksi
                    {readings.length === 500 && ' (dibatasi 500 baris)'}
                  </p>
                )}
              </div>
            </Card>

            <Card>
              <SectionTitle>Citra QC</SectionTitle>
              <div className="mt-4">
                <DropZone
                  label="Unggah batch citra produk"
                  hint="Belum tersedia — backend belum menerima berkas gambar"
                  icon={<Images size={20} />}
                  disabled
                  onFiles={() => {}}
                />
              </div>
            </Card>

            <Card>
              <SectionTitle>Konteks bisnis</SectionTitle>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <TextInput
                  label="Jadwal produksi"
                  placeholder="Sen–Sab, 2 shift, target 480 unit/hari"
                  value={schedule}
                  onChange={(event) => setSchedule(event.target.value)}
                />
                <TextInput
                  label="Stok sparepart"
                  hint="Pisahkan dengan koma"
                  placeholder="insert TNMG, seal spindle"
                  value={spareparts}
                  onChange={(event) => setSpareparts(event.target.value)}
                />
                <TextInput
                  label="ETA sparepart"
                  placeholder="insert TNMG ETA 2 hari"
                  value={eta}
                  onChange={(event) => setEta(event.target.value)}
                />
                <TextInput
                  label="Teknisi tersedia"
                  type="number"
                  min={0}
                  placeholder="2"
                  value={technicians}
                  onChange={(event) => setTechnicians(event.target.value)}
                />
                <div className="md:col-span-2">
                  <TextArea
                    label="Laporan operator"
                    placeholder="Terdengar chatter saat finishing pass sejak shift malam."
                    value={operator}
                    onChange={(event) => setOperator(event.target.value)}
                  />
                </div>
              </div>
            </Card>

            <Card>
              <SectionTitle>Kondisi manual</SectionTitle>
              <p className="mt-2 text-[13px] text-faint">
                Selalu tersedia. Ini yang membuat analisis tetap jalan pada pabrik tanpa
                sensor sama sekali.
              </p>
              <div className="mt-4">
                <TextArea
                  placeholder="Getaran meningkat, permukaan hasil potong kasar."
                  value={condition}
                  onChange={(event) => setCondition(event.target.value)}
                />
              </div>
            </Card>

            {error != null && (
              <Card>
                <ErrorState error={error} onRetry={run} />
              </Card>
            )}

            <div className="flex items-center gap-3">
              <Button
                variant="primary"
                icon={<Play size={15} />}
                disabled={!assetId}
                onClick={run}
              >
                Jalankan analisis
              </Button>
              <p className="text-xs text-faint">
                {assetId ? 'Proses sinkron, bisa memakan waktu hingga 2 menit.' : 'Pilih mesin dulu.'}
              </p>
            </div>
          </div>

          <div className="col-span-12 xl:col-span-4">
            <Card tint="clay" className="xl:sticky xl:top-24">
              <h3 className="text-sm font-medium">Kelengkapan input</h3>
              <ul className="mt-4 space-y-2.5">
                {coverage.map((item) => (
                  <li key={item.key} className="flex items-center gap-2.5 text-[13px]">
                    <span
                      className={
                        item.present
                          ? 'size-2 rounded-full bg-ink'
                          : 'size-2 rounded-full border border-ink/30'
                      }
                      aria-hidden
                    />
                    <span className={item.present ? '' : 'text-ink-dim'}>{item.label}</span>
                  </li>
                ))}
              </ul>

              <p className="mt-5 border-t border-ink/10 pt-4 text-[13px] leading-6">
                Sistem tetap menghasilkan analisis dengan input apa pun yang tersedia; makin
                lengkap input, makin dalam keputusannya.
              </p>

              <div className="mt-4">
                <CardTitle muted>Yang hilang, dan akibatnya</CardTitle>
                <ul className="mt-2 space-y-1.5">
                  {coverage
                    .filter((item) => !item.present)
                    .map((item) => (
                      <li key={item.key} className="text-xs leading-5 text-ink-dim">
                        <span className="font-medium">{item.label}</span> — {item.cost}
                      </li>
                    ))}
                  {coverage.every((item) => item.present) && (
                    <li className="text-xs text-ink-dim">Seluruh input tersedia.</li>
                  )}
                </ul>
              </div>
            </Card>
          </div>
        </div>
      )}
    </AppShell>
  )
}
