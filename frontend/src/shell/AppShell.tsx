import { useEffect, useState, type ReactNode } from 'react'
import { NavRail } from './NavRail'
import { Header } from './Header'

/**
 * page → shell (white, r-shell, one shadow) → rail + panel (black, r-panel,
 * inset 12). The two-tone shell is the theme; there is no toggle.
 * VISUAL_LANGUAGE.md §1.
 */
export function AppShell({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) {
  const [stuck, setStuck] = useState(false)

  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="min-h-screen bg-page p-4 lg:p-6">
      <div className="mx-auto flex max-w-[1440px] rounded-shell bg-shell shadow-shell">
        <NavRail />
        <div className="min-w-0 flex-1 p-3 pl-0">
          <div className="min-h-[calc(100vh-3.5rem)] rounded-panel bg-panel">
            <Header title={title} subtitle={subtitle} stuck={stuck} />
            <main className="px-4 pb-4">{children}</main>
          </div>
        </div>
      </div>
    </div>
  )
}
