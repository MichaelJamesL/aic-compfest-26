/**
 * Wire types for the backend. Mirrors docs/API.md — that document is the
 * source of truth and every shape there was captured from a running server.
 * If you need a shape that is not here, add it to API.md first.
 */

export type Criticality = 'low' | 'medium' | 'high' | 'critical'
export type Priority = 'low' | 'medium' | 'high' | 'critical'
export type Severity = 'low' | 'medium' | 'high' | 'critical'

export type WorkOrderStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'scheduled'
  | 'in_progress'
  | 'blocked'
  | 'completed'
  | 'cancelled'
  | 'rejected'

export type IngestionStatus = 'pending' | 'ready' | 'failed'
export type EngineMode = 'ai_engine' | 'offline_stub' | 'unavailable' | 'error'

export interface Capabilities {
  tier: string
  capabilities: {
    assets: boolean
    documents: boolean
    analysis: boolean
    work_orders: boolean
    mock_plc: boolean
    ai_engine: boolean
  }
}

export interface Asset {
  id: string
  factory_id: string
  name: string
  asset_type: string
  criticality: Criticality
  location: string | null
  status: string
  /** Read this, not `specs_json`. API.md gotcha 1: both keys are returned. */
  specs: Record<string, unknown>
}

export interface AssetInput {
  name: string
  asset_type?: string
  criticality?: Criticality
  location?: string | null
  specs_json?: Record<string, unknown>
  external_id?: string | null
}

/** What fitting the per-machine anomaly baseline returns. */
export interface BaselineFit {
  asset_id: string
  /** Tag → how many historical points it was fitted on. Empty when history was too thin. */
  tags: Record<string, number>
  points_used: number
  readings_available: number
}

/** A visual model that exists. Keyed by product, shared by machines of that type. */
export interface ModelBank {
  product: string
  size_bytes: number
  trained_at: string
}

/** What training a PatchCore bank from reference images returns. */
export interface ModelFit {
  asset_id: string
  product: string
  bank_path: string
  images_used: number
  /** How many reference images the fitted model itself calls anomalous. */
  flagged_in_training: number
}

export interface DocumentOut {
  id: string
  title: string
  kind: 'sop' | 'manual' | 'log' | 'qc_standard' | 'maintenance_history'
  filename: string
  size_bytes: number
  ingestion_status: IngestionStatus
  ingestion_error: string | null
}

export interface Reading {
  id: string
  tag: string
  value: number
  unit: string
  recorded_at: string
  source: string
  external_id: string | null
}

/** Mirrors ai-engine/src/schemas.py. Factory-wide, not per analysis. */
export type DayOfWeek =
  | 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday'

export interface TimeInterval {
  /** "HH:MM" or "HH:MM:SS" — what <input type="time"> emits. */
  start: string
  end: string
}

export interface SparePart {
  id: string
  name: string
  stock: number
  unit: string
  min_stock: number | null
  eta: string | null
  /** Machines this part fits. An analysis only ever sees its own machine's parts. */
  asset_ids: string[]
}

export interface TechnicianSchedule {
  name: string
  role: string
  specialty: string | null
  work_time: Partial<Record<DayOfWeek, TimeInterval>>
  occupied_time: Partial<Record<DayOfWeek, TimeInterval[]>>
}

export interface BusinessContext {
  production_schedule: { work_time: Partial<Record<DayOfWeek, TimeInterval>> } | null
  inventory: SparePart[]
  technicians: TechnicianSchedule[]
}

export interface QCBatch {
  id: string
  asset_id: string
  factory_id: string
  count: number
  defect_count: number
  defect_rate: number
  images: {
    id: string
    filename: string
    mime_type: string
    size_bytes: number
    defect_class: string | null
    class_confidence: number | null
  }[]
  created_at: string
}

export interface Anomaly {
  tag: string
  observed: number
  expected_range: [number, number]
  severity: Severity
  method: string
}

export interface DefectFinding {
  image: string
  subject: 'asset' | 'product'
  score: number
  threshold: number
  label: 'ok' | 'defect'
  severity: Severity
  region: [number, number, number, number] | null
  heatmap_path: string | null
  method: string
  /** From the fine-tuned classifier; null when none was available. */
  defect_class?: string | null
  class_confidence?: number | null
}

export interface RootCause {
  cause: string
  confidence: number
  evidence: string[]
}

export interface WorkOrderDetails {
  title: string
  steps: string[]
  parts: string[]
  est_duration_h: number | null
  required_skills: string[]
  safety_notes: string[]
  /** Set by POST /work-orders/{id}/reject. */
  rejection_reason?: string
  /** Reports that were rejected, kept in order. The current one is not here. */
  result_attempts?: {
    result: TechnicianResult
    verification: Verification | null
    submitted_at: string | null
    verified_at: string | null
  }[]
}

/** Pending — see API.md "contract changes". decide.py does not exist yet. */
export interface ScheduleWindow {
  start: string
  end: string
  expected_cost: number | null
  rationale?: string
  lost_because?: string
}

export interface Schedule {
  chosen: ScheduleWindow
  runner_up: ScheduleWindow | null
  blockers: string[]
}

/** One production phase's QC tally, as the engine computed it. */
export interface PhaseQC {
  phase: string
  asset_id: string
  product: string
  inspected: number
  defects: number
  defect_rate: number
  findings: DefectFinding[]
}

export interface FailureModeLink {
  defect_class: string
  images: number
  failure_modes: string[]
  /** Tags whose rule held. Empty means the candidates are proposals only. */
  corroborated_by: string[]
  priority_delta: number
  recommended_action: string
  source: string
}

export interface AnalysisResult {
  health_score: number
  health_summary: string
  anomalies: Anomaly[]
  defects: DefectFinding[]
  qc_by_phase?: PhaseQC[]
  failure_modes?: FailureModeLink[]
  root_causes: RootCause[]
  recommendation: string
  priority: Priority
  recommended_window: string | null
  explanation: string
  blockers: string[]
  work_order: WorkOrderDetails | null
  tier: string | null
  model: string | null
  sources: string[]
  schedule?: Schedule | null
}

export interface AnalysisRun {
  id: string
  /** HTTP is 201 even when this is "failed". API.md gotcha 5. */
  status: 'succeeded' | 'failed'
  result: AnalysisResult | null
  engine_mode: EngineMode | null
  error_code: string | null
  error_message: string | null
  health_score: number | null
  priority: Priority | null
}

export interface AnalysisDetail {
  id: string
  status: 'succeeded' | 'failed'
  result: AnalysisResult | null
  request_snapshot: RequestSnapshot | null
  error: string | null
  engine_mode: EngineMode | null
  error_code: string | null
}

export interface RequestSnapshot {
  asset: { id: string; name: string; type: string; criticality: string }
  readings: Reading[]
  history: { id: string; performed_at: string; action: string; findings: string }[]
  condition: string | null
  /** The snapshot also carries the per-machine operator report the run used. */
  business: BusinessContext & { operator_report?: string | null }
  tier: string
  trigger: string
  qc_batch_id?: string | null
  images?: string[]
}

/** Row shape of GET /assets/{id}/analyses — the raw table row, per API.md. */
export interface AnalysisSummary {
  id: string
  status: 'succeeded' | 'failed'
  tier: string
  trigger: string
  created_at: string
  health_score: number | null
  priority: Priority | null
  engine_mode: EngineMode | null
}

export interface WorkOrder {
  id: string
  factory_id: string
  asset_id: string
  analysis_id: string
  title: string
  description: string
  priority: Priority
  status: WorkOrderStatus
  details_json: WorkOrderDetails
  /** Proposed when the work order is created; a coordinator may move it. */
  assigned_technician?: string | null
  scheduled_start?: string | null
  scheduled_end?: string | null
  /** "during_production" | "manual" | why nothing could be scheduled. */
  schedule_note?: string | null
  technician_result_json?: TechnicianResult | null
  result_submitted_at?: string | null
  verification_json?: Verification | null
  created_at: string
  updated_at: string
}

export interface TechnicianResult {
  work_done: string
  findings: string
  parts_used: string[]
  evidence: string[]
}

/** Pending — POST /work-orders/{id}/verify. One synchronous call, no loop. */
export type Verdict = 'resolved' | 'partial' | 'not_resolved'

export interface Verification {
  verdict: Verdict
  evidence: string[]
  follow_up: string[]
  ingestion?: { status: 'ready' | 'failed' | 'not_attempted'; error: string | null }
}

export interface MaintenanceReport {
  work_order_id: string
  asset_id: string
  problem: string
  action: string
  findings: string
  verdict: Verification
  final_asset_state: { status: string | null; work_order_status: WorkOrderStatus }
}

export interface AnalysisInput {
  tier?: 'starter' | 'standard' | 'professional'
  trigger?: string
  manual_condition?: string | null
  include_history?: boolean
  include_business_context?: boolean
  qc_batch_id?: string | null
}

export interface ApiErrorBody {
  error: {
    code: 'NOT_FOUND' | 'CONFLICT' | 'VALIDATION_ERROR' | string
    message: string
    details: { field: string; reason: string }[]
    request_id: string
  }
}
