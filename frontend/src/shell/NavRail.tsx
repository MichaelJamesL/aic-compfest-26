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
export function NavRail() {
  return (
    <nav className="sticky top-0 flex h-screen w-16 shrink-0 flex-col justify-between overflow-y-auto bg-rail p-2 lg:w-[232px] lg:p-5">
      <div>
        <div className="flex h-10 items-center justify-center gap-2.5 lg:justify-start lg:px-1">
          <span className="grid size-5 shrink-0 place-items-center rounded-full bg-rail-content">
            <span className="size-1.5 rounded-full bg-rail" />
          </span>
          <span className="hidden text-[15px] font-semibold -tracking-[0.01em] text-rail-content lg:inline">
            Coordinator
          </span>
        </div>

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
