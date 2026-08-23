import { useCallback, useEffect, useRef, useState } from 'react'

export function useRequest<T>(request: () => Promise<T>, deps: readonly unknown[]) {
  const [data, setData] = useState<T | undefined>(undefined)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [reloadKey, setReloadKey] = useState(0)
  const requestRef = useRef(request)
  requestRef.current = request

  const reload = useCallback(() => setReloadKey((key) => key + 1), [])

  useEffect(() => {
    let current = true
    setLoading(true)
    setError(null)
    requestRef.current()
      .then((value) => {
        if (current) setData(value)
      })
      .catch((reason: unknown) => {
        if (current) setError(reason)
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => {
      current = false
    }
    // `request` is intentionally controlled by the caller's dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadKey])

  return { data, error, loading, reload, setData }
}
