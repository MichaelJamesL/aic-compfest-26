import { Link, useParams } from 'react-router'
import { ArrowLeft, Download, RefreshCw } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { VERDICT } from '../lib/severity'
import { Card, CardTitle, SectionTitle } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { ErrorState } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'
import type { MaintenanceReport } from '../api/types'

/**
 * Verdict + evidence, then the final report. A `not_resolved` verdict offers a
 * re-run that is visibly manual — an automatic one would be a feedback loop,
 * which the scope rules forbid. SCREENS.md §6.
 */
export function ReportScreen() {
  const { id = '' } = useParams()
  const { data, error, loading, reload } = useRequest(
    () => api.workOrders().then((list) => list.find((order) => order.id === id) ?? null),
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
        <ErrorState error={error ?? new Error('not found')} onRetry={reload} />
      </AppShell>
    )
  }

  // GET /work-orders/{id}/report does not exist yet, so there is never a report
  // to show. Say that plainly rather than rendering an empty shell.
  const report: MaintenanceReport | null = null

  return (
    <AppShell title="Verifikasi & laporan" subtitle={data.title}>
      <Link
        to={`/work-orders/${data.id}`}
        className="mb-3 inline-flex items-center gap-1.5 text-[13px] text-faint hover:text-white"
      >
        <ArrowLeft size={14} /> Kembali ke work order
      </Link>

      {report ? <Verdict report={report} /> : <NotYetVerified />}
    </AppShell>
  )
}

function NotYetVerified() {
  return (
    <>
      <Card>
        <SectionTitle>Belum diverifikasi</SectionTitle>
        <p className="mt-3 max-w-prose text-[13px] leading-6 text-dim">
          Verifikasi berjalan setelah teknisi mengirim hasil pekerjaan. AI membandingkan
          hasil itu dengan SOP dan kondisi mesin, lalu mengeluarkan verdict beserta
          buktinya — bukan menyatakan selesai sendiri.
        </p>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          {(['resolved', 'partial', 'not_resolved'] as const).map((verdict) => (
            <div key={verdict} className="rounded-control border border-hair p-4">
              <Badge tone={VERDICT[verdict].tone}>{VERDICT[verdict].label}</Badge>
              <p className="mt-2.5 text-xs leading-5 text-faint">
                {verdict === 'resolved' && 'Bukti mendukung bahwa masalah kondisi mesin hilang.'}
                {verdict === 'partial' && 'Sebagian tindakan terbukti, sisanya butuh tindak lanjut.'}
                {verdict === 'not_resolved' && 'Bukti tidak mendukung; diagnosis ulang bisa diminta.'}
              </p>
            </div>
          ))}
        </div>
      </Card>

      <p className="mt-3 text-xs leading-5 text-faint">
        Verifikasi belum bisa dijalankan: backend belum punya route
        <span className="text-dim"> POST /work-orders/{'{id}'}/verify</span>, dan engine belum
        punya <span className="text-dim">MaintenanceEngine.verify()</span>. Lihat
        docs/requirements/AI_ENGINE.md §1.
      </p>
    </>
  )
}

function Verdict({ report }: { report: MaintenanceReport }) {
  const state = VERDICT[report.verification.verdict]
  const unresolved = report.verification.verdict !== 'resolved'

  return (
    <>
      <Card tint={state.tint} className={state.tint === 'dark' ? 'border border-crit' : undefined}>
        <h3 className="text-sm font-medium">Hasil verifikasi</h3>
        <p className="mt-2 text-[22px] leading-7 font-semibold -tracking-[0.015em]">
          {state.label}
        </p>
        <p className="mt-3 max-w-prose text-[13px] leading-6">{report.verification.summary}</p>

        <div className="mt-5 border-t border-ink/10 pt-4">
          <p className="text-xs font-medium">Bukti</p>
          <ul className="mt-2 space-y-1.5">
            {report.verification.evidence.map((item) => (
              <li key={item} className="text-[13px] leading-6">
                {item}
              </li>
            ))}
          </ul>
        </div>
      </Card>

      {unresolved && report.verification.follow_up.length > 0 && (
        <Card className="mt-3">
          <SectionTitle>Tindak lanjut</SectionTitle>
          <ul className="mt-4 space-y-2">
            {report.verification.follow_up.map((item) => (
              <li key={item} className="text-[13px] text-dim">
                {item}
              </li>
            ))}
          </ul>
          <div className="mt-5">
            <Button icon={<RefreshCw size={14} />} size="sm">
              Jalankan diagnosis ulang
            </Button>
            <p className="mt-2 text-xs text-faint">
              Dijalankan atas permintaan pengguna, bukan otomatis.
            </p>
          </div>
        </Card>
      )}

      <Card className="mt-3">
        <div className="flex flex-wrap items-center gap-3">
          <SectionTitle>Laporan akhir</SectionTitle>
          <Button size="sm" className="ml-auto" icon={<Download size={14} />}>
            Ekspor
          </Button>
        </div>
        <dl className="mt-4 space-y-4">
          <div>
            <CardTitle muted>Masalah</CardTitle>
            <dd className="mt-1 text-[13px] leading-6 text-dim">{report.problem}</dd>
          </div>
          <div>
            <CardTitle muted>Tindakan</CardTitle>
            <dd className="mt-1 text-[13px] leading-6 text-dim">{report.action}</dd>
          </div>
          <div>
            <CardTitle muted>Kondisi akhir mesin</CardTitle>
            <dd className="mt-1 text-[13px] leading-6 text-dim">{report.final_state}</dd>
          </div>
        </dl>

        {report.written_back && (
          <p className="mt-5 border-t border-hair pt-4 text-xs leading-5 text-faint">
            Work order yang selesai ditulis kembali sebagai dokumen histori maintenance di
            knowledge base, dan akan dibaca analisis berikutnya.
          </p>
        )}
      </Card>
    </>
  )
}
