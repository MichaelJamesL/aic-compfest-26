import { useState } from 'react'
import { Images, ScanEye } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { formatBytes, formatDateTime } from '../lib/format'
import { Card, CardTitle, SectionTitle } from '../ui/Card'
import { Button } from '../ui/Button'
import { DropZone } from '../ui/DropZone'
import { Select, TextInput } from '../ui/Field'
import { EmptyState, ErrorState } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'
import { Table, Td, Th, Tr } from '../ui/Table'
import type { ModelFit } from '../api/types'

/**
 * Fit the visual inspection model from photos of good units.
 *
 * The machine list importer carries no images, and the new-machine form only
 * covers a machine being registered for the first time — a model for a machine
 * that already exists, or a retrain after the process changes, needs its own
 * way in.
 */
export function QCModelScreen() {
  const assets = useRequest(() => api.assets(), [])
  const models = useRequest(() => api.models(), [])

  const [assetId, setAssetId] = useState('')
  const [product, setProduct] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [fit, setFit] = useState<ModelFit | null>(null)
  const [error, setError] = useState<unknown>(null)

  const selected = assets.data?.find((asset) => asset.id === assetId) ?? null
  // The bank is named by product, and the batch that gets inspected has to name
  // the same one — so the default is shown, never left implicit.
  const effectiveProduct = product.trim() || selected?.asset_type || ''
  const existing = models.data?.find((model) => model.product === effectiveProduct) ?? null

  async function train() {
    if (!assetId || !files.length) return
    setBusy(true)
    setError(null)
    setFit(null)
    try {
      setFit(await api.trainModel(assetId, files, effectiveProduct))
      setFiles([])
      models.reload()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell
      title="Model QC"
      subtitle="Latih model visual dari citra unit normal, per produk."
    >
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-12 space-y-3 xl:col-span-8">
          <Card>
            <SectionTitle>Mesin dan produk</SectionTitle>
            {assets.loading && <Skeleton className="mt-4 h-24 rounded-card" />}
            {assets.data && assets.data.length === 0 && (
              <EmptyState>Belum ada mesin terdaftar.</EmptyState>
            )}
            {assets.data && assets.data.length > 0 && (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <Select
                  label="Mesin"
                  value={assetId}
                  onChange={(event) => setAssetId(event.target.value)}
                >
                  <option value="">— pilih —</option>
                  {assets.data.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.name} · {asset.asset_type}
                    </option>
                  ))}
                </Select>
                <TextInput
                  label="Produk"
                  hint={
                    selected
                      ? `Kosong berarti "${selected.asset_type}", tipe mesin ini.`
                      : 'Nama model. Kosong berarti memakai tipe mesin.'
                  }
                  placeholder="metal-nut-4lug"
                  value={product}
                  onChange={(event) => setProduct(event.target.value)}
                />
              </div>
            )}
            {existing && (
              <p className="mt-4 text-[13px] text-warn-text">
                Produk <span className="font-medium">{existing.product}</span> sudah punya model
                (dilatih {formatDateTime(existing.trained_at)}). Melatih ulang menggantinya.
              </p>
            )}
          </Card>

          <Card>
            <SectionTitle>Citra unit normal</SectionTitle>
            <p className="mt-2 text-[13px] text-content-3">
              Hanya unit yang <span className="text-content-2">tidak cacat</span>. Model belajar
              seperti apa normal itu, lalu menandai yang menyimpang — satu cacat yang ikut terunggah
              diajarkan sebagai normal.
            </p>
            <div className="mt-4">
              <DropZone
                label="Unggah citra referensi"
                hint={assetId ? 'PNG/JPEG · 20–50 citra sudah cukup' : 'Pilih mesin dulu.'}
                icon={<Images size={20} />}
                accept=".png,.jpg,.jpeg"
                multiple
                disabled={!assetId || busy}
                onFiles={(dropped) => setFiles((current) => [...current, ...dropped])}
              />
              {files.length > 0 && (
                <p className="mt-3 flex items-center gap-3 text-[13px] text-content-2">
                  <span className="text-content">{files.length} citra siap dilatih</span>
                  <button
                    type="button"
                    className="underline underline-offset-[3px]"
                    onClick={() => setFiles([])}
                  >
                    kosongkan
                  </button>
                </p>
              )}
            </div>
          </Card>

          {error != null && (
            <Card>
              <ErrorState error={error} onRetry={train} />
            </Card>
          )}

          {fit && (
            <Card tint="sage">
              <SectionTitle>Model terlatih</SectionTitle>
              <p className="mt-2 text-[13px]">
                Produk <span className="font-medium">{fit.product}</span> dilatih dari{' '}
                {fit.images_used} citra. Batch QC yang menyebut produk ini akan diperiksa
                terhadapnya.
              </p>
            </Card>
          )}

          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              icon={<ScanEye size={15} />}
              disabled={busy || !assetId || !files.length}
              onClick={train}
            >
              {busy ? 'Melatih…' : 'Latih model'}
            </Button>
            <p className="text-xs text-content-3">
              {!assetId
                ? 'Pilih mesin dulu.'
                : !files.length
                  ? 'Unggah citra referensi dulu.'
                  : 'Pelatihan berjalan sinkron, bisa beberapa menit.'}
            </p>
          </div>
        </div>

        <div className="col-span-12 xl:col-span-4">
          <Card className="xl:sticky xl:top-24">
            <CardTitle>Model yang ada</CardTitle>
            {models.loading && <Skeleton className="mt-4 h-24 rounded-card" />}
            {models.error != null && <ErrorState error={models.error} onRetry={models.reload} />}
            {models.data?.length === 0 && (
              <p className="mt-3 text-[13px] text-content-3">
                Belum ada model. Tanpa model, citra QC tidak diperiksa dan analisis melaporkannya
                sebagai tidak dinilai.
              </p>
            )}
            {models.data && models.data.length > 0 && (
              <div className="mt-3">
                <Table className="min-w-0">
                  <thead>
                    <tr>
                      <Th>Produk</Th>
                      <Th align="right">Dilatih</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {models.data.map((model) => (
                      <Tr key={model.product}>
                        <Td tone="primary">
                          {model.product}
                          <span className="block text-xs text-content-3">
                            {formatBytes(model.size_bytes)}
                          </span>
                        </Td>
                        <Td align="right" tone="muted">
                          {formatDateTime(model.trained_at)}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            )}
            <p className="mt-5 border-t border-line pt-4 text-[13px] leading-6 text-content-2">
              Model dilatih per produk, bukan per unit mesin — mesin lain yang membuat produk yang
              sama langsung memakainya.
            </p>
          </Card>
        </div>
      </div>
    </AppShell>
  )
}
