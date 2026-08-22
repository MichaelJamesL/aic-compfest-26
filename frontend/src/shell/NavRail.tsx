import { NavLink } from 'react-router'
import { ClipboardList, FlaskConical, FolderUp } from 'lucide-react'
import { cn } from '../lib/cn'
import { StatusCard } from './StatusCard'

/** Three items. Not four, not seven. SCREENS.md §0. */
const ITEMS = [
  { to: '/setup', label: 'Setup', icon: FolderUp },
  { to: '/analyze', label: 'Analisis', icon: FlaskConical },
  { to: '/work-orders', label: 'Work order', icon: ClipboardList },
]

export function NavRail() {
  return (
    <nav className="flex w-[232px] shrink-0 flex-col justify-between p-5">
      <div>
        <div className="flex items-center gap-2.5 px-1">
          <span className="grid size-5 place-items-center rounded-full bg-ink">
            <span className="size-1.5 rounded-full bg-shell" />
          </span>
          <span className="text-[15px] font-semibold -tracking-[0.01em]">Coordinator</span>
        </div>

        <ul className="mt-8 space-y-1">
          {ITEMS.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex h-10 items-center gap-3 rounded-control px-3.5 text-sm font-medium',
                    'transition-colors duration-100',
                    isActive
                      ? 'bg-ink text-shell'
                      : 'text-ink-dim hover:bg-ink/5 hover:text-ink',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon size={18} className={isActive ? '' : 'text-ink-faint'} />
                    {label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>

      <StatusCard />
    </nav>
  )
}
