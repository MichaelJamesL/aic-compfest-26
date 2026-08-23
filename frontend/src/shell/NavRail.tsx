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
 * The light variants sit directly on the rail — darkest opaque pixel `#769F8B`
 * measures 6.39:1 against `--rail`, so the plate the dark lockup needed is
 * gone. The dark files stay for light surfaces and the favicons.
 */
function Brand() {
  return (
    <div className="px-1">
      <img
        src="/logo-text-white.png"
        alt="Siena"
        width={1452}
        height={359}
        className="hidden h-auto w-full max-w-[168px] lg:block"
      />
      <img
        src="/logo-white.png"
        alt="Siena"
        width={372}
        height={359}
        className="mx-auto h-auto w-full max-w-8 lg:hidden"
      />
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
