import { useState } from 'react'
import { Images, Plus, Table2, Trash2, Wrench } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api } from '../api/client'
import { Card, SectionTitle } from '../ui/Card'
import { Button, LinkButton } from '../ui/Button'
import { DropZone } from '../ui/DropZone'
import { Select, TextInput } from '../ui/Field'
import { ErrorState } from '../ui/States'
import type { Asset, BaselineFit, Criticality, ModelFit } from '../api/types'

const CRITICALITY: { value: Criticality; label: string }[] = [
  { value: 'low', label: 'Rendah' },
  { value: 'medium', label: 'Sedang' },
  { value: 'high', label: 'Tinggi' },
  { value: 'critical', label: 'Kritis' },
]

type Spec = { key: string; value: string }

/** "85" → 85, "true" → true, everything else stays the string it was typed as. */
function parseSpec(value: string): unknown {
  const trimmed = value.trim()
  if (trimmed === '') return ''
  if (trimmed === 'true' || trimmed === 'false') return trimmed === 'true'
  const asNumber = Number(trimmed)
  return Number.isNaN(asNumber) ? trimmed : asNumber
}

export function NewMachineScreen() {
  const [name, setName] = useState('')
  const [assetType, setAssetType] = useState('')
  const [criticality, setCriticality] = useState<Criticality>('medium')
  const [location, setLocation] = useState('')
  const [externalId, setExternalId] = useState('')
  const [specs, setSpecs] = useState<Spec[]>([])
  const [references, setReferences] = useState<File[]>([])
  const [history, setHistory] = useState<File | null>(null)

  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState<Asset | null>(null)
  const [fit, setFit] = useState<ModelFit | null>(null)
  const [baseline, setBaseline] = useState<BaselineFit | null>(null)
  const [imported, setImported] = useState<number | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [historyError, setHistoryError] = useState<unknown>(null)
  // The machine outlives a failed training run — say so instead of pretending it failed whole.
  const [trainingError, setTrainingError] = useState<unknown>(null)

  function editSpec(index: number, patch: Partial<Spec>) {
    setSpecs((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }

  /** Import the history, then fit the baseline from it — two calls, one intent. */
  async function learnHistory(asset: Asset) {
    if (!history) return
    setHistoryError(null)
    try {
      const result = await api.importReadings(asset.id, history)
      setImported(result.count)
      setBaseline(await api.fitBaseline(asset.id))
    } catch (err) {
      setHistoryError(err)
    }
  }

  async function train(asset: Asset) {
    setTrainingError(null)
    try {
      setFit(await api.trainModel(asset.id, references, asset.asset_type))
    } catch (err) {
      setTrainingError(err)
    }
  }

  async function submit() {
    if (!name.trim()) return
    setBusy(true)
    setError(null)
    setTrainingError(null)
    try {
      const asset = await api.createAsset({
        name: name.trim(),
        asset_type: assetType.trim() || 'machine',
        criticality,
        location: location.trim() || null,
        external_id: externalId.trim() || null,
        specs_json: Object.fromEntries(
          specs.filter((row) => row.key.trim()).map((row) => [row.key.trim(), parseSpec(row.value)]),
        ),
      })
      setCreated(asset)
      await learnHistory(asset)
      if (references.length) await train(asset)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  function reset() {
    setName('')
    setAssetType('')
    setCriticality('medium')
    setLocation('')
    setExternalId('')
    setSpecs([])
    setReferences([])
    setHistory(null)
    setCreated(null)
    setFit(null)
    setBaseline(null)
    setImported(null)
    setError(null)
    setTrainingError(null)
    setHistoryError(null)
  }

  if (created) {
    return (
      <AppShell title="Mesin terdaftar" subtitle={created.name}>
        <Card>
          <SectionTitle>{created.name}</SectionTitle>
          <dl className="mt-4 grid gap-3 text-[13px] md:grid-cols-2">
            <div>
              <dt className="text-content-3">Tipe</dt>
              <dd>{created.asset_type}</dd>
            </div>
            <div>
              <dt className="text-content-3">Kritikalitas</dt>
              <dd>{CRITICALITY.find((one) => one.value === created.criticality)?.label}</dd>
            </div>
            <div>
              <dt className="text-content-3">Lokasi</dt>
              <dd>{created.location || '—'}</dd>
            </div>
            <div>
              <dt className="text-content-3">Baseline anomali sensor</dt>
              <dd>
                {baseline && Object.keys(baseline.tags).length > 0
                  ? `terpasang dari ${imported ?? baseline.readings_available} pembacaan · ${Object.entries(baseline.tags).map(([tag, points]) => `${tag} (${points})`).join(', ')}`
                  : historyError != null
                    ? 'gagal dipasang'
                    : baseline
                      ? 'histori terlalu sedikit untuk dipelajari — deteksi memakai pagar IQR per batch'
                      : 'belum ada — deteksi memakai pagar IQR per batch'}
              </dd>
            </div>
            <div>
              <dt className="text-content-3">Model visual QC</dt>
              <dd>
                {fit
                  ? `terlatih dari ${fit.images_used} citra referensi, produk "${fit.product}"`
                  : trainingError != null
                    ? 'gagal dilatih'
                    : 'belum ada — mesin tetap bisa dianalisis tanpa citra QC'}
              </dd>
            </div>
          </dl>

          {historyError != null && (
            <div className="mt-4">
              <p className="text-[13px] text-content-2">
                Mesin sudah tersimpan; hanya histori sensor yang gagal diproses. Analisis tetap
                jalan memakai pagar IQR per batch.
              </p>
              <ErrorState error={historyError} onRetry={() => learnHistory(created)} />
            </div>
          )}

          {trainingError != null && (
            <div className="mt-4">
              <p className="text-[13px] text-content-2">
                Mesin sudah tersimpan; hanya pelatihan model yang gagal. Analisis tetap bisa
                dijalankan, tanpa deteksi defect visual.
              </p>
              <ErrorState error={trainingError} onRetry={() => train(created)} />
            </div>
          )}

          <div className="mt-5 flex items-center gap-3">
            <LinkButton to="/analyze" variant="primary">
              Jalankan analisis
            </LinkButton>
            <Button onClick={reset}>Tambah mesin lagi</Button>
          </div>
        </Card>
      </AppShell>
    )
  }

  return (
    <AppShell
      title="Mesin baru"
      subtitle="Daftarkan satu mesin, lengkap dengan histori sensor dan citra kondisi normalnya."
    >
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-12 space-y-3 xl:col-span-8">
          <Card>
            <SectionTitle>Identitas mesin</SectionTitle>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <TextInput
                label="Nama"
                placeholder="CNC-02"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <TextInput
                label="Tipe"
                hint="Dipakai sebagai nama produk saat melatih model visual."
                placeholder="cnc-mill"
                value={assetType}
                onChange={(event) => setAssetType(event.target.value)}
              />
              <Select
                label="Kritikalitas"
                value={criticality}
                onChange={(event) => setCriticality(event.target.value as Criticality)}
              >
                {CRITICALITY.map((one) => (
                  <option key={one.value} value={one.value}>
                    {one.label}
                  </option>
                ))}
              </Select>
              <TextInput
                label="Lokasi"
                placeholder="Lini A"
                value={location}
                onChange={(event) => setLocation(event.target.value)}
              />
              <TextInput
                label="ID internal pabrik"
                hint="Opsional. Dipakai agar impor CSV berikutnya tidak menggandakan mesin ini."
                placeholder="MC-014"
                value={externalId}
                onChange={(event) => setExternalId(event.target.value)}
              />
            </div>
          </Card>

          <Card>
            <SectionTitle>Spesifikasi</SectionTitle>
            <p className="mt-2 text-[13px] text-content-3">
              Batas yang dikutip analisis saat menilai pembacaan sensor, misal{' '}
              <span className="text-content-2">max_temp_c</span> = 85. Baris tanpa nama tidak
              tersimpan.
            </p>
            <div className="mt-4 space-y-2">
              {specs.map((row, index) => (
                <div key={index} className="flex items-end gap-2">
                  <TextInput
                    label={`Nama spesifikasi ${index + 1}`}
                    placeholder="max_temp_c"
                    value={row.key}
                    onChange={(event) => editSpec(index, { key: event.target.value })}
                  />
                  <TextInput
                    label={`Nilai spesifikasi ${index + 1}`}
                    placeholder="85"
                    value={row.value}
                    onChange={(event) => editSpec(index, { value: event.target.value })}
                  />
                  <Button
                    size="sm"
                    className="mb-0.5"
                    icon={<Trash2 size={14} />}
                    aria-label={`Hapus spesifikasi ${index + 1}`}
                    onClick={() => setSpecs((rows) => rows.filter((_, i) => i !== index))}
                  />
                </div>
              ))}
            </div>
            <Button
              className="mt-3"
              icon={<Plus size={15} />}
              onClick={() => setSpecs((rows) => [...rows, { key: '', value: '' }])}
            >
              Tambah spesifikasi
            </Button>
          </Card>

          <Card>
            <SectionTitle>Histori data sensor</SectionTitle>
            <p className="mt-2 text-[13px] text-content-3">
              Dipakai untuk mempelajari kondisi normal mesin ini, sekali di awal. Tanpa histori,
              anomali hanya dinilai relatif terhadap batch yang sedang dianalisis — mesin yang
              memburuk perlahan terlihat normal terhadap dirinya sendiri.
            </p>
            <div className="mt-4">
              <DropZone
                label="Unggah CSV histori sensor"
                hint="tag,value,unit,recorded_at · minimal 8 titik per tag agar bisa dipelajari"
                icon={<Table2 size={20} />}
                accept=".csv"
                disabled={busy}
                onFiles={([file]) => setHistory(file)}
              />
              {history && (
                <p className="mt-3 flex items-center gap-3 text-[13px] text-content-2">
                  <span className="text-content">{history.name}</span>
                  <button
                    type="button"
                    className="underline underline-offset-[3px]"
                    onClick={() => setHistory(null)}
                  >
                    hapus
                  </button>
                </p>
              )}
            </div>
          </Card>

          <Card>
            <SectionTitle>Citra referensi (kondisi normal)</SectionTitle>
            <p className="mt-2 text-[13px] text-content-3">
              Hanya unit yang <span className="text-content-2">tidak cacat</span>. Model belajar
              seperti apa normal itu, lalu menandai yang menyimpang. Satu cacat yang ikut terunggah
              akan diajarkan sebagai normal.
            </p>
            <div className="mt-4">
              <DropZone
                label="Unggah citra unit normal"
                hint="PNG/JPEG · 20–50 citra sudah cukup · dilatih per tipe mesin"
                icon={<Images size={20} />}
                accept=".png,.jpg,.jpeg"
                multiple
                disabled={busy}
                onFiles={(files) => setReferences((current) => [...current, ...files])}
              />
              {references.length > 0 && (
                <p className="mt-3 flex items-center gap-3 text-[13px] text-content-2">
                  <span className="text-content">{references.length} citra siap dilatih</span>
                  <button
                    type="button"
                    className="underline underline-offset-[3px]"
                    onClick={() => setReferences([])}
                  >
                    kosongkan
                  </button>
                </p>
              )}
            </div>
          </Card>

          {error != null && (
            <Card>
              <ErrorState error={error} onRetry={submit} />
            </Card>
          )}

          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              icon={<Wrench size={15} />}
              disabled={busy || !name.trim()}
              onClick={submit}
            >
              {busy ? 'Menyimpan…' : 'Daftarkan mesin'}
            </Button>
            <p className="text-xs text-content-3">
              {!name.trim()
                ? 'Nama mesin wajib diisi.'
                : references.length
                  ? 'Pelatihan model bisa memakan waktu beberapa menit.'
                  : 'Citra referensi opsional — bisa ditambahkan nanti.'}
            </p>
          </div>
        </div>

        <div className="col-span-12 xl:col-span-4">
          <Card tint="clay" className="xl:sticky xl:top-24">
            <h3 className="text-sm font-medium">Urutan yang dilakukan</h3>
            <ol className="mt-4 space-y-2.5 text-[13px]">
              <li>1. Mesin didaftarkan ke pabrik ini.</li>
              <li>2. Histori sensor diimpor, lalu baseline anomali dipelajari darinya.</li>
              <li>3. Citra referensi melatih model visual, jika ada.</li>
              <li>4. Sparepart dan jadwal diatur di Konteks bisnis.</li>
              <li>5. Analisis dijalankan dari tab Analisis.</li>
            </ol>
            <p className="mt-5 border-t border-ink/10 pt-4 text-[13px] leading-6">
              Model visual dilatih per tipe mesin, bukan per unit — mesin lain dengan tipe yang sama
              langsung memakai model ini.
            </p>
          </Card>
        </div>
      </div>
    </AppShell>
  )
}
