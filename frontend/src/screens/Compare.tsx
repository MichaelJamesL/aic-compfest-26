import { Link, useParams, useSearchParams } from 'react-router'
import { Activity, ArrowLeft, FileText, Gauge } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { inputCoverage } from '../lib/health'
import { formatDateTime } from '../lib/format'
import { healthLabel, priorityLabel, priorityTone } from '../lib/severity'
import { Card, SectionTitle } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Select } from '../ui/Field'
import { MetricCard } from '../ui/MetricCard'
import { EmptyState, ErrorState, MissingInput } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'
import type { AnalysisDetail, AnalysisSummary } from '../api/types'

/**
 * The graceful-degradation beat: the same asset run twice, minimal input on the
 * left, full input on the right. Same section order down both sides so the eye
 * compares by row. FINAL_IDEA.md §11 / SCREENS.md §7.
 */
export function CompareScreen() {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  // Comparing a run with itself proves nothing; treat it as no selection.
  const requested = params.get('with') ?? ''
  const other = requested === id ? '' : requested

  const left = useRequest(() => api.analysis(id), [id])
  const right = useRequest(() => (other ? api.analysis(other) : Promise.resolve(null)), [other])

  // The other runs for this asset, so the second column can be picked rather
  // than typed into the URL. This is the comparison beat, not a history page.
  const assetId = left.data?.request_snapshot?.asset.id
  const runs = useRequest(
    () => (assetId ? api.assetAnalyses(assetId) : Promise.resolve([])),
    [assetId],
  )

  if (left.loading || right.loading) {
    return (
      <AppShell title="Perbandingan run">
        <div className="grid grid-cols-2 gap-3">
          <Skeleton className="h-96 rounded-card" />
          <Skeleton className="h-96 rounded-card" />
        </div>
      </AppShell>
    )
  }

  if (left.error || !left.data) {
    return (
      <AppShell title="Perbandingan run">
        <ErrorState error={left.error} onRetry={left.reload} />
      </AppShell>
    )
  }

  const asset = left.data.request_snapshot?.asset.name ?? 'Mesin'

  return (
    <AppShell title="Perbandingan run" subtitle={asset}>
      <Link
        to={`/analysis/${id}`}
        className="mb-3 inline-flex items-center gap-1.5 text-[13px] text-faint hover:text-white"
      >
        <ArrowLeft size={14} /> Kembali ke hasil analisis
      </Link>

      <Card tint="mint" className="mb-3">
        <p className="text-[13px] leading-6">
          Sistem tetap menghasilkan analisis dengan input apa pun yang tersedia; makin
          lengkap input, makin dalam keputusannya.
        </p>
      </Card>

      <RunPicker
        currentId={id}
        selectedId={other}
        runs={(runs.data ?? []).filter((run) => run.id !== id)}
        loading={runs.loading}
        onSelect={(next) => setParams(next ? { with: next } : {})}
      />

      {!right.data ? (
        <Card>
          <EmptyState
            action={
              <Link to="/analyze">
                <Button variant="primary">Jalankan analisis kedua</Button>
              </Link>
            }
          >
            Belum ada run kedua untuk dibandingkan. Jalankan aset yang sama dua kali — sekali
            hanya dengan dokumen dan kondisi manual, sekali dengan seluruh input — lalu pilih
            run keduanya di atas.
          </EmptyState>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <Column detail={left.data} label="Run A" />
          <Column detail={right.data} label="Run B" />
        </div>
      )}
    </AppShell>
  )
}

function RunPicker({
  currentId,
  selectedId,
  runs,
  loading,
  onSelect,
}: {
  currentId: string
  selectedId: string
  runs: AnalysisSummary[]
  loading: boolean
  onSelect: (id: string) => void
}) {
  if (loading) return <Skeleton className="mb-3 h-[76px] rounded-card" />

  return (
    <Card className="mb-3">
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <p className="text-[13px] font-medium text-dim">Run A</p>
          <p className="mt-1.5 text-[13px] text-faint">
            Analisis {currentId.slice(0, 8)} — run yang sedang dibuka
          </p>
        </div>
        <Select
          label="Run B"
          value={selectedId}
          onChange={(event) => onSelect(event.target.value)}
          disabled={runs.length === 0}
        >
          <option value="">
            {runs.length === 0 ? '— belum ada run lain pada mesin ini —' : '— pilih run —'}
          </option>
          {runs.map((run) => (
            <option key={run.id} value={run.id}>
              {formatDateTime(run.created_at)} · {run.tier} · skor{' '}
              {run.health_score ?? '—'}
              {run.status === 'failed' ? ' · gagal' : ''}
            </option>
          ))}
        </Select>
      </div>
    </Card>
  )
}

function Column({ detail, label }: { detail: AnalysisDetail; label: string }) {
  const result = detail.result
  const coverage = inputCoverage(detail.request_snapshot)
  const present = coverage.filter((item) => item.present)

  if (!result) {
    return (
      <Card>
        <SectionTitle>{label}</SectionTitle>
        <div className="mt-4">
          <MissingInput>Run ini gagal, tidak ada hasil untuk dibandingkan.</MissingInput>
        </div>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      <Card>
        <div className="flex items-center gap-3">
          <SectionTitle>{label}</SectionTitle>
          <Badge tone="neutral" className="ml-auto">
            {present.length}/{coverage.length} input
          </Badge>
        </div>
        <ul className="mt-4 flex flex-wrap gap-1.5">
          {coverage.map((item) => (
            <li
              key={item.key}
              className={
                item.present
                  ? 'rounded-lg bg-raised px-2 py-1 text-xs text-white'
                  : 'rounded-lg border border-hair px-2 py-1 text-xs text-faint'
              }
            >
              {item.label}
            </li>
          ))}
        </ul>
      </Card>

      <MetricCard
        icon={<Gauge size={16} />}
        title="Skor kesehatan"
        value={result.health_score}
        caption={healthLabel(result.health_score)}
        badge={<Badge tone={priorityTone(result.priority)}>{priorityLabel(result.priority)}</Badge>}
      />

      <MetricCard
        icon={<Activity size={16} />}
        title="Anomali terdeteksi"
        value={result.anomalies.length}
        caption={
          result.anomalies.length
            ? result.anomalies.map((anomaly) => anomaly.tag).join(', ')
            : 'Tidak ada di luar rentang normal'
        }
      />

      <MetricCard
        icon={<FileText size={16} />}
        title="Dokumen dikutip"
        value={result.sources.length}
        caption={result.sources.length ? result.sources.join(', ') : 'Tidak ada dokumen terindeks'}
      />

      <Card>
        <SectionTitle>Jendela maintenance</SectionTitle>
        <div className="mt-3">
          {result.schedule ? (
            <p className="text-[15px] font-medium">{result.schedule.chosen.start}</p>
          ) : result.recommended_window ? (
            <p className="text-[15px] font-medium">{result.recommended_window}</p>
          ) : (
            <MissingInput>
              Tidak ada jendela — jadwal produksi tidak tersedia pada run ini.
            </MissingInput>
          )}
        </div>
      </Card>

      <Card>
        <SectionTitle>Root cause</SectionTitle>
        <ul className="mt-3 space-y-2">
          {result.root_causes.map((cause) => (
            <li key={cause.cause} className="text-[13px] text-dim">
              {cause.cause}{' '}
              <span className="tnum text-faint">{Math.round(cause.confidence * 100)}%</span>
            </li>
          ))}
          {result.root_causes.length === 0 && (
            <li>
              <MissingInput>Tidak ada penyebab yang bisa disimpulkan.</MissingInput>
            </li>
          )}
        </ul>
      </Card>
    </div>
  )
}
