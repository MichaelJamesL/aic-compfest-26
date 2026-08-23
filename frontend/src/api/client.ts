import type {
  AnalysisDetail,
  AnalysisInput,
  AnalysisRun,
  AnalysisSummary,
  ApiErrorBody,
  Asset,
  AssetInput,
  BusinessContext,
  Capabilities,
  DocumentOut,
  Reading,
  WorkOrder,
  MaintenanceReport,
  QCBatch,
  TechnicianResult,
  Verification,
} from './types'

const BASE = ''

/** Demo identity. Not authentication — see docs/API.md. */
export const ROLES = [
  { user: 'demo-engineer', label: 'Engineer' },
  { user: 'demo-manager', label: 'Coordinator' },
  { user: 'demo-technician', label: 'Teknisi' },
  { user: 'demo-viewer', label: 'Viewer' },
] as const

export type RoleUser = (typeof ROLES)[number]['user']

const IDENTITY_KEY = 'aic.identity'
let memoryIdentity: { user: RoleUser; factory: string } = {
  user: 'demo-engineer',
  factory: 'demo-factory',
}

export function getIdentity(): { user: RoleUser; factory: string } {
  try {
    const raw = localStorage.getItem(IDENTITY_KEY)
    if (raw) {
      const parsed: unknown = JSON.parse(raw)
      if (typeof parsed === 'object' && parsed !== null && 'user' in parsed && 'factory' in parsed && typeof parsed.user === 'string' && ROLES.some((role) => role.user === parsed.user) && typeof parsed.factory === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(parsed.factory)) {
        memoryIdentity = { user: parsed.user as RoleUser, factory: parsed.factory }
        return memoryIdentity
      }
    }
  } catch {
    /* private mode or unavailable storage: use the session identity */
  }
  return memoryIdentity
}

export function setIdentity(user: RoleUser) {
  const next = { ...getIdentity(), user }
  try {
    localStorage.setItem(IDENTITY_KEY, JSON.stringify(next))
  } catch {
    /* not fatal: retain the identity in memory for this session */
  }
  memoryIdentity = next
  return next
}

export class ApiError extends Error {
  code: string
  details: { field: string; reason: string }[]
  requestId: string
  status: number

  constructor(status: number, body: ApiErrorBody['error']) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.details = body.details ?? []
    this.requestId = body.request_id
  }
}

/** `message` from the server is a token, never user copy. Map it here. */
const MESSAGES: Record<string, string> = {
  asset_not_found: 'Mesin tidak ditemukan.',
  analysis_not_found: 'Analisis tidak ditemukan.',
  analysis_not_ready: 'Analisis belum selesai atau gagal.',
  work_order_not_found: 'Work order tidak ditemukan.',
  document_not_found: 'Dokumen tidak ditemukan.',
  file_too_large: 'Ukuran berkas melebihi 10 MB.',
  non_text_file: 'Berkas bukan teks dan belum didukung.',
  empty_filename: 'Berkas tidak punya nama.',
  AI_ENGINE_UNAVAILABLE: 'Mesin analisis tidak tersedia.',
  ANALYSIS_FAILED: 'Mesin analisis gagal memproses permintaan.',
  too_many_qc_images: 'Batch QC melebihi batas jumlah gambar.',
  unsupported_qc_image: 'Gunakan gambar PNG atau JPEG untuk batch QC.',
  qc_image_too_large: 'Ukuran salah satu gambar QC melebihi 5 MB.',
  invalid_qc_image_signature: 'Salah satu berkas bukan gambar PNG atau JPEG yang valid.',
  qc_batch_too_large: 'Ukuran total batch QC melebihi 50 MB.',
  qc_batch_not_found: 'Batch QC tidak ditemukan.',
  verification_failed: 'Verifikasi belum berhasil dijalankan.',
  technician_result_required: 'Hasil pekerjaan teknisi belum dikirim.',
}

export function errorCopy(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Tidak bisa menghubungi server. Periksa apakah backend berjalan di :8000.'
  }
  const msg = error.message
  if (MESSAGES[msg]) return MESSAGES[msg]
  if (msg.startsWith('unsupported_extension:')) {
    return `Jenis berkas ${msg.split(':')[1]} belum didukung.`
  }
  if (msg.startsWith('invalid_transition:')) {
    const [from, to] = msg.split(':')[1].split('->')
    return `Status tidak bisa berpindah dari ${from} ke ${to}.`
  }
  if (error.code === 'VALIDATION_ERROR' && error.details.length) {
    return error.details.map((d) => d.reason).join('; ')
  }
  return msg
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const identity = getIdentity()
  const headers = new Headers(init.headers)
  headers.set('X-Demo-User', identity.user)
  headers.set('X-Factory-ID', identity.factory)
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(BASE + path, { ...init, headers })
  if (!response.ok) {
    let body: ApiErrorBody | null = null
    try {
      body = await response.json()
    } catch {
      /* not our envelope — fall through */
    }
    throw new ApiError(
      response.status,
      body?.error ?? {
        code: 'UNKNOWN',
        message: `HTTP ${response.status}`,
        details: [],
        request_id: response.headers.get('X-Request-ID') ?? '—',
      },
    )
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

async function requestFile(path: string): Promise<Blob> {
  const identity = getIdentity()
  const response = await fetch(BASE + path, { headers: { 'X-Demo-User': identity.user, 'X-Factory-ID': identity.factory } })
  if (!response.ok) {
    let body: ApiErrorBody | null = null
    try { body = await response.json() } catch { /* preserve the normal API error fallback */ }
    throw new ApiError(response.status, body?.error ?? { code: 'UNKNOWN', message: `HTTP ${response.status}`, details: [], request_id: response.headers.get('X-Request-ID') ?? '—' })
  }
  return response.blob()
}

function json(body: unknown): RequestInit {
  return { method: 'POST', body: JSON.stringify(body) }
}

export const api = {
  capabilities: () => request<Capabilities>('/config/capabilities'),

  assets: () => request<Asset[]>('/api/v1/assets'),
  asset: (id: string) => request<Asset>(`/api/v1/assets/${id}`),
  createAsset: (body: AssetInput) => request<Asset>('/api/v1/assets', json(body)),
  importAssets: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ imported: number; errors: { row: number; reason: string }[] }>(
      '/api/v1/assets/import',
      { method: 'POST', body: form },
    )
  },

  documents: () => request<DocumentOut[]>('/api/v1/knowledge/documents'),
  uploadDocument: (file: File, kind: DocumentOut['kind'] = 'sop', assetId?: string) => {
    const form = new FormData()
    form.append('file', file)
    const query = new URLSearchParams({ kind })
    if (assetId) query.set('asset_id', assetId)
    return request<DocumentOut>(`/api/v1/knowledge/documents?${query}`, {
      method: 'POST',
      body: form,
    })
  },
  reindexDocument: (id: string) =>
    request<DocumentOut>(`/api/v1/knowledge/documents/${id}/reindex`, { method: 'POST' }),
  importMaintenanceHistory: (file: File) => {
    const form = new FormData(); form.append('file', file)
    return request<{ imported: number; errors: { row: number; reason: string }[] }>('/api/v1/maintenance-records/import', { method: 'POST', body: form })
  },

  readings: (assetId: string) => request<Reading[]>(`/api/v1/assets/${assetId}/readings`),
  addReading: (assetId: string, body: Omit<Reading, 'id'>) =>
    request<{ id: string; quality: string }>(`/api/v1/assets/${assetId}/readings`, json(body)),
  importReadings: (assetId: string, file: File) => {
    const form = new FormData(); form.append('file', file)
    return request<{ count: number; errors: { row: number; reason: string }[] }>(`/api/v1/assets/${assetId}/readings/import`, { method: 'POST', body: form })
  },

  setCondition: (assetId: string, condition: string) =>
    request<unknown>(`/api/v1/assets/${assetId}/condition`, {
      method: 'PUT',
      body: JSON.stringify({ condition }),
    }),

  /** Full replace, not a patch — always send every field. API.md gotcha 2. */
  setBusinessContext: (assetId: string, body: BusinessContext) =>
    request<BusinessContext>(`/api/v1/assets/${assetId}/business-context`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  uploadQCBatch: (assetId: string, files: File[]) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    return request<QCBatch>(`/api/v1/assets/${assetId}/qc-batches`, {
      method: 'POST',
      body: form,
    })
  },

  analyze: (assetId: string, body: AnalysisInput) =>
    request<AnalysisRun>(`/api/v1/assets/${assetId}/analyses`, json(body)),
  analysis: (id: string) => request<AnalysisDetail>(`/api/v1/analyses/${id}`),
  /**
   * Runs for one asset. Used only by the comparison screen, which demonstrates
   * a claim the proposal makes — not by a history page, which is out of scope
   * (docs/DEFECTS.md#analysis-history-out-of-scope).
   */
  assetAnalyses: (assetId: string) =>
    request<AnalysisSummary[]>(`/api/v1/assets/${assetId}/analyses`),
  ask: (assetId: string, question: string) =>
    request<{ answer: string }>(`/api/v1/assets/${assetId}/ask`, json({ question })),

  createWorkOrder: (analysisId: string) =>
    request<WorkOrder>(`/api/v1/analyses/${analysisId}/work-orders`, { method: 'POST' }),
  workOrders: () => request<WorkOrder[]>('/api/v1/work-orders'),
  transition: (id: string, action: string) =>
    request<WorkOrder>(`/api/v1/work-orders/${id}/${action}`, { method: 'POST' }),
  /** Rejection carries a reason; the next analysis reads it. */
  rejectWorkOrder: (id: string, reason: string) =>
    request<WorkOrder>(`/api/v1/work-orders/${id}/reject`, json({ reason })),
  submitTechnicianResult: (id: string, body: TechnicianResult) =>
    request<{ id: string; status: string; result: TechnicianResult; result_submitted_at: string }>(
      `/api/v1/work-orders/${id}/result`, json(body),
    ),
  verifyWorkOrder: (id: string) =>
    request<{ id: string; status: string; verification: Verification; verified_at: string }>(
      `/api/v1/work-orders/${id}/verify`, { method: 'POST' },
    ),
  workOrderReport: (id: string) => request<MaintenanceReport>(`/api/v1/work-orders/${id}/report`),
  exportWorkOrder: (id: string, format: 'json' | 'csv' = 'json') => requestFile(`/api/v1/work-orders/${id}/export?format=${format}`),
}
