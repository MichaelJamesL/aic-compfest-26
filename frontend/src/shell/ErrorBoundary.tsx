import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

/**
 * Without this, one component throwing gives the user a blank white page —
 * `StatusCard` reading an unexpected response once took down the entire shell.
 * During a seven-minute recording that cannot be cut, a blank page ends the
 * take. A designed failure screen does not.
 */
interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Keep the stack in the console: during a demo the terminal is on screen.
    console.error('Unhandled UI error:', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="flex min-h-screen items-center justify-center bg-rail p-6">
        <div className="w-full max-w-lg rounded-panel bg-surface p-8">
          <div className="flex items-start gap-3">
            <AlertTriangle size={20} className="mt-0.5 shrink-0 text-crit" />
            <div>
              <h1 className="text-[22px] leading-7 font-semibold -tracking-[0.015em] text-content">
                Ada yang gagal dimuat
              </h1>
              <p className="mt-2 text-[13px] leading-6 text-content-2">
                Tampilan ini berhenti sebelum selesai digambar. Data yang sudah tersimpan
                tidak terpengaruh — memuat ulang halaman biasanya cukup.
              </p>
            </div>
          </div>

          <pre className="mt-5 max-h-32 overflow-auto rounded-control bg-surface-card p-3 text-[11.5px] leading-5 text-content-3">
            {error.message || String(error)}
          </pre>

          <div className="mt-5 flex flex-wrap gap-2">
            <button
              onClick={() => window.location.reload()}
              className="inline-flex h-10 items-center rounded-control bg-content px-[18px] text-sm font-medium text-surface-card"
            >
              Muat ulang
            </button>
            <button
              onClick={() => {
                window.location.href = '/analyze'
              }}
              className="inline-flex h-10 items-center rounded-control border border-line-strong px-[18px] text-sm font-medium text-content"
            >
              Kembali ke Analisis
            </button>
          </div>
        </div>
      </div>
    )
  }
}
