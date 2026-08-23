import { useCallback, useEffect, useRef, useState } from 'react'

interface State<T> {
  data: T | null
  error: unknown
  loading: boolean
}

/**
 * Seven screens and no cache-invalidation problem worth a library.
 * If that stops being true, reach for TanStack Query — not before.
 */
export function useRequest<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: true })
  const alive = useRef(true)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, deps)

  const reload = useCallback(() => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    run().then(
      (data) => alive.current && setState({ data, error: null, loading: false }),
      (error) => alive.current && setState({ data: null, error, loading: false }),
    )
  }, [run])

  useEffect(() => {
    alive.current = true
    reload()
    return () => {
      alive.current = false
    }
  }, [reload])

  return { ...state, reload, setData: (data: T) => setState({ data, error: null, loading: false }) }
}
