import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { vi } from 'vitest'

type Handler = unknown | ((init: RequestInit | undefined) => unknown)

export interface RouteStub {
  /** Matched as a substring of the request URL, longest pattern first. */
  [pathFragment: string]: Handler
}

export const calls: { url: string; method: string; body: unknown }[] = []

/**
 * Stub `fetch` per URL fragment. Anything unmatched returns the backend's real
 * 404 envelope, so a screen asking for something we forgot fails loudly.
 */
export function stubRoutes(routes: RouteStub, options: { status?: number } = {}) {
  calls.length = 0
  const patterns = Object.keys(routes).sort((a, b) => b.length - a.length)

  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      let body: unknown = null
      if (typeof init?.body === 'string') {
        try {
          body = JSON.parse(init.body)
        } catch {
          body = init.body
        }
      }
      calls.push({ url, method, body })

      const match = patterns.find((pattern) => url.includes(pattern))
      if (!match) {
        return {
          ok: false,
          status: 404,
          headers: new Headers(),
          json: async () => ({
            error: { code: 'NOT_FOUND', message: 'not_found', details: [], request_id: 'req-0' },
          }),
        }
      }

      const handler = routes[match]
      const payload = typeof handler === 'function' ? (handler as (i?: RequestInit) => unknown)(init) : handler
      const status = options.status ?? 200
      return {
        ok: status < 400,
        status,
        headers: new Headers(),
        json: async () => payload,
      }
    }),
  )
}

export const CAPABILITIES = {
  tier: 'starter',
  capabilities: {
    assets: true,
    documents: true,
    analysis: true,
    work_orders: true,
    mock_plc: true,
    ai_engine: false,
  },
}

export function renderRoute(path: string, pattern: string, element: ReactElement) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={pattern} element={element} />
        <Route path="*" element={<div>navigated away</div>} />
      </Routes>
    </MemoryRouter>,
  )
}
