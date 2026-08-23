import { NavLink } from 'react-router'
import { ClipboardList, FlaskConical, FolderUp } from 'lucide-react'
import { cn } from '../lib/cn'
import { StatusCard, StatusDotCompact } from './StatusCard'

/** Three items. Not four, not seven. SCREENS.md §0. */
const ITEMS = [
  { to: '/setup', label: 'Setup', icon: FolderUp },
  { to: '/analyze', label: 'Analisis', icon: FlaskConical },
  { to: '/work-orders', label: 'Work order', icon: ClipboardList },
]

/**
 * Dark rail against the light work surface. Sticky and full-height, so it does
 * not scroll away on a long results page.
 *
 * Below 1024 it collapses to a 64px icon-only strip — it is never removed.
 * Navigation and the engine-mode signal must survive every viewport.
 */
/**
 * The mark is a sage-to-near-black gradient drawn for light backgrounds: on the
 * #111111 rail its right end measures 1.03:1, so "SIENA" reads as "SIE". Rather
 * than recolour someone's logo, it sits on the light plate it was designed for.
 */
function Brand() {
  return (
    <div>
      <div className="rounded-control bg-surface-card p-2.5 lg:px-3 lg:py-2.5">
        <img
          src="/logo-text.png"
          alt="Siena"
          width={1452}
          height={359}
          className="hidden h-auto w-full lg:block"
        />
        <img
          src="/logo.png"
          alt="Siena"
          width={372}
          height={359}
          className="mx-auto h-auto w-full max-w-7 lg:hidden"
        />
      </div>
      <p className="mt-3 hidden text-[11.5px] leading-4 text-rail-content-3 lg:block">
        Intelligence, grounded in industry
      </p>
    </div>
  )
}

export function NavRail() {
  return (
    <nav className="sticky top-0 flex h-screen w-16 shrink-0 flex-col justify-between overflow-y-auto bg-rail p-2 lg:w-[232px] lg:p-5">
      <div>
        <Brand />

        <ul className="mt-6 space-y-1 lg:mt-8">
          {ITEMS.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                title={label}
                className={({ isActive }) =>
                  cn(
                    'flex h-10 items-center justify-center gap-3 rounded-control text-sm font-medium',
                    'transition-colors duration-100 lg:justify-start lg:px-3.5',
                    isActive
                      ? 'bg-rail-content text-rail'
                      : 'text-rail-content-2 hover:bg-white/5 hover:text-rail-content',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon size={18} className={cn('shrink-0', !isActive && 'text-rail-content-3')} />
                    <span className="hidden lg:inline">{label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>

      <div className="hidden lg:block">
        <StatusCard />
      </div>
      <div className="lg:hidden">
        <StatusDotCompact />
      </div>
    </nav>
  )
}
