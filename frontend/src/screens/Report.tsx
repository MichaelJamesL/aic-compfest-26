import { useState } from 'react'
import { useParams } from 'react-router'
import { Download } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { ApiError, api } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { VERDICT } from '../lib/severity'
import { Card, CardTitle, SectionTitle } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { BackLink, Button, LinkButton } from '../ui/Button'
import { ErrorState } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'
import type { MaintenanceReport, WorkOrder } from '../api/types'

/**
 * Verdict + evidence, then the final report. A `not_resolved` verdict offers a
 * re-run that is visibly manual — an automatic one would be a feedback loop,
 * which the scope rules forbid. SCREENS.md §6.
 */
export function ReportScreen() {
  const { id = '' } = useParams()
  const { data, error, loading, reload } = useRequest<{ order: WorkOrder; report: MaintenanceReport | null }>(
    () => api.workOrders().then(async (list) => {
      const order = list.find((item) => item.id === id)
      if (!order) throw new Error('not found')
      try {
        return { order, report: await api.workOrderReport(id) }
      } catch (reason) {
        if (reason instanceof ApiError && reason.status === 404) {
          return { order, report: null }
        }
        throw reason
      }
    }),
    [id],
  )

  if (loading) {
    return (
      <AppShell title="Laporan">
        <Skeleton className="h-64 rounded-card" />
      </AppShell>
    )
  }

  if (error || !data) {
    return (
      <AppShell title="Laporan">
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

  const { order, report } = data

  return (
    <AppShell title="Verifikasi & laporan" subtitle={order.title}>
      <BackLink to={`/work-orders/${order.id}`}>Kembali ke work order</BackLink>

      {report ? <Verdict orderId={order.id} report={report} /> : (
         <NotYetVerified orderId={order.id} hasTechnicianResult={order.technician_result_json != null && order.status === 'in_progress'} onVerified={reload} />
      )}
    </AppShell>
  )
}

function NotYetVerified({ orderId, hasTechnicianResult, onVerified }: {
  orderId: string; hasTechnicianResult: boolean; onVerified: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)

  async function verify() {
    setBusy(true)
    setError(false)
    try {
      await api.verifyWorkOrder(orderId)
      onVerified()
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Card>
        <SectionTitle>Belum diverifikasi</SectionTitle>
        <p className="mt-3 max-w-prose text-[13px] leading-6 text-content-2">
          Verifikasi berjalan setelah teknisi mengirim hasil pekerjaan. AI membandingkan
          hasil itu dengan SOP dan kondisi mesin, lalu mengeluarkan verdict beserta
          buktinya — bukan menyatakan selesai sendiri.
        </p>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          {(['resolved', 'partial', 'not_resolved'] as const).map((verdict) => (
            <div key={verdict} className="rounded-control border border-line p-4">
              <Badge tone={VERDICT[verdict].tone}>{VERDICT[verdict].label}</Badge>
              <p className="mt-2.5 text-xs leading-5 text-content-3">
                {verdict === 'resolved' && 'Bukti mendukung bahwa masalah kondisi mesin hilang.'}
                {verdict === 'partial' && 'Sebagian tindakan terbukti, sisanya butuh tindak lanjut.'}
                {verdict === 'not_resolved' && 'Bukti tidak mendukung; diagnosis ulang bisa diminta.'}
              </p>
            </div>
          ))}
        </div>
      </Card>

      {hasTechnicianResult ? (
        <div className="mt-3 flex items-center gap-3">
          <Button size="sm" variant="primary" onClick={verify} disabled={busy}>
            {busy ? 'Memverifikasi…' : 'Jalankan verifikasi'}
          </Button>
          {error && <span className="text-xs text-crit-text">Verifikasi gagal dijalankan.</span>}
        </div>
      ) : (
        <p className="mt-3 text-xs leading-5 text-faint">
          Hasil pekerjaan teknisi diperlukan sebelum verifikasi dapat dijalankan. Minta teknisi
          mengisi dan mengirim hasil pekerjaan terlebih dahulu.
        </p>
      )}
    </>
  )
}

function Verdict({ orderId, report }: { orderId: string; report: MaintenanceReport }) {
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState(false)

  async function exportReport(format: 'json' | 'csv') {
    setExporting(true)
    setExportError(false)
    try {
      const blob = await api.exportWorkOrder(orderId, format)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      const safeId = orderId.replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 64) || 'unknown'
      link.download = `work-order-${safeId}.${format}`
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      setExportError(true)
    } finally {
      setExporting(false)
    }
  }
  const state = VERDICT[report.verdict.verdict]
  const unresolved = report.verdict.verdict !== 'resolved'

  return (
    <>
      <Card tint={state.tint} className={state.tint === 'dark' ? 'border border-crit' : undefined}>
        <h3 className="text-sm font-medium">Hasil verifikasi</h3>
        <p className="mt-2 text-[22px] leading-7 font-semibold -tracking-[0.015em]">
          {state.label}
        </p>
        <p className="mt-3 max-w-prose text-[13px] leading-6">{report.findings}</p>

        <div className="mt-5 border-t border-ink/10 pt-4">
          <p className="text-xs font-medium">Bukti</p>
          <ul className="mt-2 space-y-1.5">
            {report.verdict.evidence.map((item) => (
              <li key={item} className="text-[13px] leading-6">
                {item}
              </li>
            ))}
          </ul>
        </div>
      </Card>

      {unresolved && report.verdict.follow_up.length > 0 && (
        <Card className="mt-3">
          <SectionTitle>Tindak lanjut</SectionTitle>
          <ul className="mt-4 space-y-2">
            {report.verdict.follow_up.map((item) => (
              <li key={item} className="text-[13px] text-content-2">
                {item}
              </li>
            ))}
          </ul>
          <div className="mt-5">
            <p className="text-xs text-content-3">Diagnosis ulang belum tersedia pada API saat ini.</p>
          </div>
        </Card>
      )}

      <Card className="mt-3">
        <div className="flex flex-wrap items-center gap-3">
            <SectionTitle>Laporan akhir</SectionTitle>
            <div className="ml-auto flex gap-2">
              <Button size="sm" icon={<Download size={14} />} onClick={() => exportReport('json')} disabled={exporting}>
                {exporting ? 'Menyiapkan…' : 'Ekspor JSON'}
              </Button>
              <Button size="sm" variant="secondary" onClick={() => exportReport('csv')} disabled={exporting}>
                Ekspor CSV
              </Button>
            </div>
        </div>
        {exportError && <p className="mt-3 text-xs text-crit-text">Ekspor gagal disiapkan.</p>}
        <dl className="mt-4 space-y-4">
          <div>
            <CardTitle muted>Masalah</CardTitle>
            <dd className="mt-1 text-[13px] leading-6 text-content-2">{report.problem}</dd>
          </div>
          <div>
            <CardTitle muted>Tindakan</CardTitle>
            <dd className="mt-1 text-[13px] leading-6 text-content-2">{report.action}</dd>
          </div>
          <div>
            <CardTitle muted>Kondisi akhir mesin</CardTitle>
            <dd className="mt-1 text-[13px] leading-6 text-content-2">
              {report.final_asset_state.status ?? 'Status tidak tersedia'}
            </dd>
          </div>
        </dl>

        {report.final_asset_state.work_order_status === 'completed' && (
          <p className="mt-5 border-t border-hair pt-4 text-xs leading-5 text-faint">
            Histori maintenance tersimpan di sistem dan siap dipakai untuk tindak lanjut.
          </p>
        )}
      </Card>
    </>
  )
}
