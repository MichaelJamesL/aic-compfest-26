import { useEffect, useState, type ReactNode } from 'react'
import { NavRail } from './NavRail'
import { Header } from './Header'

/**
 * shell (white, full-bleed) → rail + panel (black, r-panel, inset 12).
 * The two-tone shell is the theme; there is no toggle. The white chrome fills
 * the window rather than floating on a page, so there is no outer gutter and
 * no shell shadow. VISUAL_LANGUAGE.md §1.
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
    <div className="flex min-h-screen bg-shell">
      <NavRail />
      <div className="min-w-0 flex-1 p-3 pl-0">
        <div className="min-h-[calc(100vh-1.5rem)] rounded-panel bg-panel">
          <Header title={title} subtitle={subtitle} stuck={stuck} />
          <main className="px-4 pb-4">{children}</main>
        </div>
      </div>
    </div>
  )
}
