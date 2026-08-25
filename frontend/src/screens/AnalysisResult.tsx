import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { ArrowRight, Download, FileText, GitCompare, ShieldAlert, Wrench } from 'lucide-react'
import { AppShell } from '../shell/AppShell'
import { api, errorCopy } from '../api/client'
import { useRequest } from '../lib/useRequest'
import { findings, healthSegments, healthSources, inputCoverage } from '../lib/health'
import { formatDuration, formatPercent } from '../lib/format'
import { cn } from '../lib/cn'
import {
  TONE_TEXT,
  healthLabel,
  healthTone,
  priorityLabel,
  priorityTone,
  severityLabel,
  severityTone,
} from '../lib/severity'
import { Card, CardTitle, DeterministicNote, SectionTitle } from '../ui/Card'
import { Badge, StatusDot } from '../ui/Badge'
import { Button, LinkButton } from '../ui/Button'
import { Donut, DonutLegend } from '../ui/Donut'
import { Bars, ConfidenceBar } from '../ui/Bars'
import { Table, Td, Th, Tr } from '../ui/Table'
import { ErrorState, MissingInput } from '../ui/States'
import { Skeleton } from '../ui/Skeleton'
import type { AnalysisDetail, AnalysisResult } from '../api/types'

export function AnalysisResultScreen() {
  const { id = '' } = useParams()
  const { data, error, loading, reload } = useRequest(() => api.analysis(id), [id])

  if (loading) {
    return (
      <AppShell title="Hasil analisis" subtitle="Memuat…">
        <div className="grid grid-cols-12 gap-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="col-span-12 h-[320px] rounded-card md:col-span-6 xl:col-span-3" />
          ))}
          <Skeleton className="col-span-12 h-56 rounded-card" />
        </div>
      </AppShell>
    )
  }

  if (error || !data) {
    return (
      <AppShell title="Hasil analisis">
        <Card>
          <ErrorState
            error={error}
            onRetry={reload}
            action={
              <LinkButton to="/analyze" size="sm" variant="primary">Analisis baru</LinkButton>
            }
          />
        </Card>
      </AppShell>
    )
  }

  return <Result detail={data} onReload={reload} />
}

function Result({ detail, onReload }: { detail: AnalysisDetail; onReload: () => void }) {
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<unknown>(null)

  const assetName = detail.request_snapshot?.asset.name ?? 'Mesin'
  const stub = detail.engine_mode === 'offline_stub'

  // status is "failed" even though HTTP was 201. API.md gotcha 5.
  if (detail.status === 'failed' || !detail.result) {
    return (
      <AppShell title={assetName} subtitle="Analisis gagal">
        <Card className="flex flex-col items-start gap-4">
          <div className="flex items-start gap-3">
            <ShieldAlert size={18} className="mt-0.5 shrink-0 text-crit-text" />
            <div>
              <p className="text-sm">
                {detail.error_code === 'AI_ENGINE_UNAVAILABLE'
                  ? 'Mesin analisis tidak tersedia saat permintaan dijalankan.'
                  : 'Mesin analisis gagal memproses permintaan ini.'}
              </p>
              <p className="mt-1 text-xs text-content-3">
                {detail.error_code ?? 'UNKNOWN'} · Analysis ID {detail.id}
              </p>
            </div>
          </div>
          <Button onClick={onReload}>Muat ulang</Button>
        </Card>
      </AppShell>
    )
  }

  const result = detail.result
  const segments = healthSegments(result)
  const coverage = inputCoverage(detail.request_snapshot)

  async function createWorkOrder() {
    setCreating(true)
    setCreateError(null)
    try {
      const order = await api.createWorkOrder(detail.id)
      navigate(`/work-orders/${order.id}`)
    } catch (err) {
      setCreateError(err)
      setCreating(false)
    }
  }

  return (
    <AppShell title={assetName} subtitle={`Analisis ${detail.id.slice(0, 8)}`}>
      {stub && (
        <div className="mb-3 flex items-center gap-2 rounded-control bg-warn-fill px-4 py-2.5 text-[13px] text-warn-text">
          <ShieldAlert size={15} className="shrink-0" />
          Output berasal dari stub offline, bukan dari model.
        </div>
      )}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone={priorityTone(result.priority)}>
          Prioritas {priorityLabel(result.priority)}
        </Badge>
        <span className="text-xs text-content-3">
          {result.model ?? 'model tidak diketahui'} · tier {result.tier ?? '—'}
        </span>
        <div className="ml-auto flex gap-2">
          <LinkButton
            to={`/analysis/${detail.id}/compare`}
            size="sm"
            icon={<GitCompare size={14} />}
          >
            Bandingkan run
          </LinkButton>
          <Button size="sm" icon={<Download size={14} />} disabled title="Belum tersedia di backend">
            Ekspor
          </Button>
          <Button
            size="sm"
            variant="primary"
            icon={<Wrench size={14} />}
            onClick={createWorkOrder}
            disabled={creating}
          >
            {creating ? 'Membuat…' : 'Buat work order'}
          </Button>
        </div>
      </div>

      {createError != null && (
        <p className="mb-3 text-[13px] text-crit-text">{errorCopy(createError)}</p>
      )}

      {/* Band — the reference's card row, reused exactly. */}
      <div className="grid grid-cols-12 gap-3">
        <Card className="col-span-12 flex flex-col md:col-span-6 xl:col-span-3">
          <div className="flex flex-wrap items-baseline gap-2">
            <CardTitle>Skor kesehatan</CardTitle>
            {/* Which signals actually fed it — the score is not sensor-only once
                a QC batch has been inspected. */}
            <span className="text-xs text-content-3">({healthSources(result)})</span>
          </div>
          <div className="mt-4 flex justify-center">
            <Donut
              segments={segments}
              value={result.health_score}
              suffix="/100"
              caption={healthLabel(result.health_score)}
              captionClass={TONE_TEXT[healthTone(result.health_score)]}
            />
          </div>
          <DonutLegend segments={segments} />
          <div className="mt-4">
            <DeterministicNote />
          </div>
        </Card>

        <QcChainCard result={result} />
        <ScheduleCard result={result} />
        <SourcesCard result={result} coverage={coverage} />
      </div>

      {/* Root cause analysis */}
      <Card className="mt-3">
        <SectionTitle>Root cause analysis</SectionTitle>
        <ul className="mt-4 space-y-4">
          {[...result.root_causes]
            .sort((a, b) => b.confidence - a.confidence)
            .slice(0, 4)
            .map((cause) => (
              <li key={cause.cause} className="border-t border-line pt-4 first:border-0 first:pt-0">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-[15px] font-medium">{cause.cause}</p>
                  <ConfidenceBar value={cause.confidence} />
                </div>
                {cause.evidence.length > 0 && (
                  <ul className="mt-2.5 flex flex-wrap gap-1.5">
                    {cause.evidence.map((item) => (
                      <li
                        key={item}
                        className="rounded-lg bg-surface-raised px-2 py-1 text-xs text-content-2"
                      >
                        {item}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          {result.root_causes.length === 0 && (
            <li className="text-[13px] text-content-3">
              Tidak ada penyebab yang bisa disimpulkan dari input yang tersedia.
            </li>
          )}
        </ul>

        <div className="mt-5 border-t border-line pt-4">
          <CardTitle muted>Penjelasan</CardTitle>
          <p className="mt-2 max-w-prose text-[13px] leading-6 text-content-2">{result.explanation}</p>
        </div>
      </Card>

      {/* Detail row */}
      <div className="mt-3 grid grid-cols-12 gap-3">
        <Card className="col-span-12 xl:col-span-8">
          <SectionTitle>Anomali sensor</SectionTitle>
          {result.anomalies.length === 0 ? (
            <p className="mt-4 text-[13px] text-content-2">
              Tidak ada anomali di luar rentang normal.
            </p>
          ) : (
            <div className="mt-4">
              <Table>
                <thead>
                  <tr>
                    <Th>Tag</Th>
                    <Th align="right">Nilai teramati</Th>
                    <Th align="right">Rentang normal</Th>
                    <Th>Keparahan</Th>
                    <Th>Metode</Th>
                  </tr>
                </thead>
                <tbody>
                  {result.anomalies.map((anomaly) => (
                    <Tr key={anomaly.tag}>
                      <Td tone="primary">{anomaly.tag}</Td>
                      <Td align="right">{anomaly.observed}</Td>
                      <Td align="right">
                        {anomaly.expected_range[0]} – {anomaly.expected_range[1]}
                      </Td>
                      <Td>
                        <StatusDot tone={severityTone(anomaly.severity)}>
                          {severityLabel(anomaly.severity)}
                        </StatusDot>
                      </Td>
                      <Td tone="muted">{anomaly.method.toUpperCase()}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )}
          <div className="mt-4">
            <DeterministicNote>
              Rentang normal dari IQR fence per tag. Deterministik.
            </DeterministicNote>
          </div>
        </Card>

        <QcResultCard result={result} />
      </div>

      <WorkOrderDraft result={result} />

      {/* The autonomy boundary, made literal. */}
      <div className="sticky bottom-4 z-20 mt-3">
        <div className="glass-light flex flex-wrap items-center gap-3 rounded-card px-5 py-3.5">
          <p className="flex-1 text-[13px] text-content-2">
            AI mengusulkan dan menyiapkan; coordinator menyetujui.
          </p>
          <Button size="sm" variant="ghost" disabled title="Butuh work order aktif">
            Tolak
          </Button>
          <Button
            size="sm"
            variant="primary"
            icon={<ArrowRight size={14} />}
            onClick={createWorkOrder}
            disabled={creating}
          >
            Lanjut ke persetujuan
          </Button>
        </div>
      </div>
    </AppShell>
  )
}

/**
 * The differentiator. Never cut it — when the mechanism is missing, say so
 * rather than hiding the card. SCREENS.md §3 B.
 */
function QcChainCard({ result }: { result: AnalysisResult }) {
  const defects = findings(result).filter((d) => d.label === 'defect')

  return (
    <Card tint="sage" className="col-span-12 md:col-span-6 xl:col-span-3">
      <h3 className="text-sm font-medium">Rantai QC → mesin</h3>

      {defects.length > 0 ? (
        <div className="mt-4 space-y-2">
          <p className="tnum text-[30px] leading-[34px] font-semibold -tracking-[0.02em]">
            {defects.length}
          </p>
          <p className="text-[13px] leading-6 text-soft">
            citra menyimpang dari unit normal, dari {findings(result).length} yang diperiksa.
          </p>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <p className="text-[13px] leading-6 text-soft">
            Rantai ini bermula dari citra produk. Analisis ini tidak menyertakan batch citra QC,
            jadi tidak ada sinyal QC sama sekali.
          </p>
        </div>
      )}

    </Card>
  )
}

/** SCREENS.md §3 C — the runner-up is the point of this card. */
function ScheduleCard({ result }: { result: AnalysisResult }) {
  const schedule = result.schedule

  return (
    <Card tint="apricot" className="col-span-12 md:col-span-6 xl:col-span-3">
      <h3 className="text-sm font-medium">Jendela maintenance</h3>

      {schedule ? (
        <dl className="mt-4 space-y-3 text-[13px]">
          <div>
            <dt className="text-soft">Terpilih</dt>
            <dd className="text-[17px] leading-6 font-semibold">{schedule.chosen.start}</dd>
          </div>
          {schedule.runner_up && (
            <div>
              <dt className="text-soft">Runner-up</dt>
              <dd>{schedule.runner_up.start}</dd>
              <dd className="text-xs text-soft">kalah: {schedule.runner_up.lost_because}</dd>
            </div>
          )}
        </dl>
      ) : (
        <div className="mt-4 space-y-2">
          <p className="text-[17px] leading-6 font-semibold">
            {result.recommended_window ?? 'Belum ditentukan'}
          </p>
        </div>
      )}

      {result.blockers.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-t border-ink/10 pt-3">
          {result.blockers.map((blocker) => (
            <li key={blocker} className="flex items-start gap-2 text-[13px]">
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-burnt" aria-hidden />
              {blocker}
            </li>
          ))}
        </ul>
      )}

      <p className="mt-5 border-t border-ink/10 pt-3 text-xs leading-5 text-soft">
        Optimal = meminimalkan ekspektasi biaya downtime tak terencana dan scrap, dengan
        constraint jadwal produksi, ETA sparepart, ketersediaan teknisi, dan batasan
        keselamatan pada SOP.
      </p>
    </Card>
  )
}

function SourcesCard({
  result,
  coverage,
}: {
  result: AnalysisResult
  coverage: ReturnType<typeof inputCoverage>
}) {
  const missing = coverage.filter((item) => !item.present)

  return (
    <Card tint="clay" className="col-span-12 md:col-span-6 xl:col-span-3">
      <h3 className="text-sm font-medium">Sumber & keterbatasan</h3>

      <div className="mt-4">
        {result.sources.length > 0 ? (
          <ul className="space-y-1.5">
            {result.sources.map((source) => (
              <li key={source} className="flex items-start gap-2 text-[13px]">
                <FileText size={13} className="mt-1 shrink-0" />
                <span className="truncate">{source}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] leading-6 text-soft">
            Tidak ada dokumen terindeks; analisis tidak memiliki dasar dokumen yang bisa
            dikutip.
          </p>
        )}
      </div>

      <div className="mt-5 border-t border-ink/10 pt-3">
        <p className="text-xs font-medium">Input yang tidak tersedia</p>
        {missing.length === 0 ? (
          <p className="mt-1.5 text-xs text-soft">Seluruh input tersedia.</p>
        ) : (
          <ul className="mt-1.5 space-y-1">
            {missing.map((item) => (
              <li key={item.key} className="text-xs leading-5 text-soft">
                <span className="font-medium">{item.label}</span> — {item.cost}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  )
}

function QcResultCard({ result }: { result: AnalysisResult }) {
  const inspected = findings(result)
  const total = inspected.length
  const defective = inspected.filter((d) => d.label === 'defect').length

  return (
    <Card className="col-span-12 xl:col-span-4">
      <SectionTitle>Hasil QC</SectionTitle>
      {total === 0 ? (
        <div className="mt-4">
          <MissingInput>
            Belum ada citra QC pada analisis ini. Unggah batch citra untuk memakai hasil QC
            produk sebagai sinyal kondisi mesin.
          </MissingInput>
        </div>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap items-baseline gap-2">
            <p
              className={cn(
                'tnum text-[30px] leading-[34px] font-semibold -tracking-[0.02em]',
                defective > 0 && 'text-crit-text',
              )}
            >
              {formatPercent(defective / total)}
            </p>
            <span className="text-[13px] text-content-2">defect rate</span>
          </div>
          <p className="mt-1 text-xs text-content-3">
            {defective === total
              ? `Semua ${total} citra ditandai defect — tidak ada satu pun yang lolos.`
              : `${defective} dari ${total} citra ditandai defect`}
          </p>
          <div className="mt-5">
            <Bars
              bars={inspected.slice(0, 6).map((defect, i) => ({
                label: defect.defect_class ?? `#${i + 1}`,
                value: defect.score,
                highlighted: defect.label === 'defect',
              }))}
              format={(v) => v.toFixed(2)}
              height={110}
            />
          </div>
        </>
      )}
    </Card>
  )
}

function WorkOrderDraft({ result }: { result: AnalysisResult }) {
  const order = result.work_order
  if (!order) return null

  return (
    <Card className="mt-3">
      <div className="flex flex-wrap items-center gap-3">
        <SectionTitle>Draft work order</SectionTitle>
        <Badge tone="neutral">Belum disetujui</Badge>
      </div>
      <p className="mt-2 text-[15px] font-medium">{order.title}</p>

      <div className="mt-5 grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <CardTitle muted>Langkah</CardTitle>
          <ol className="mt-2.5 space-y-2">
            {order.steps.map((step, index) => (
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
              {order.parts.length ? order.parts.join(', ') : 'Tidak ada'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-content-3">Skill yang dibutuhkan</dt>
            <dd className="mt-1 text-[13px] text-content-2">
              {order.required_skills.length ? order.required_skills.join(', ') : '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-content-3">Estimasi durasi</dt>
            <dd className="tnum mt-1 text-[13px] text-content-2">
              {formatDuration(order.est_duration_h)}
            </dd>
          </div>
        </dl>
      </div>

      {order.safety_notes.length > 0 && (
        <div className="mt-5 rounded-control border border-crit/40 p-4">
          <p className="flex items-center gap-2 text-[13px] font-medium text-crit-text">
            <ShieldAlert size={14} /> Catatan keselamatan
          </p>
          <ul className="mt-2 space-y-1">
            {order.safety_notes.map((note) => (
              <li key={note} className="text-[13px] text-content-2">
                {note}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}
