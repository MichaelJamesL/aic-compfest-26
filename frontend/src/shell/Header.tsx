import { useEffect, useRef, useState } from 'react'
import { Bell, ChevronDown, Search, Settings } from 'lucide-react'
import { ROLES, getIdentity, setIdentity, type RoleUser } from '../api/client'
import { cn } from '../lib/cn'

/**
 * The demo needs to move between coordinator and technician, so the role
 * switcher lives in the avatar chip — styled as the reference's chevron, not
 * as a form control. SCREENS.md §0.
 */
function RoleSwitcher() {
  const [user, setUser] = useState<RoleUser>(() => getIdentity().user)
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const active = ROLES.find((role) => role.user === user) ?? ROLES[0]

  return (
    <div className="relative" ref={box}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 items-center gap-2 rounded-full border border-hair pr-3 pl-1 text-[13px] text-dim transition-colors duration-100 hover:text-white"
      >
        <span className="grid size-7 place-items-center rounded-full bg-raised text-[11px] font-semibold text-white">
          {active.label.slice(0, 2).toUpperCase()}
        </span>
        {active.label}
        <ChevronDown size={14} />
      </button>

      {open && (
        <ul className="glass-dark absolute top-full right-0 z-30 mt-2 w-44 rounded-control p-1">
          {ROLES.map((role) => (
            <li key={role.user}>
              <button
                onClick={() => {
                  setIdentity(role.user)
                  setUser(role.user)
                  setOpen(false)
                  // Identity scopes every request; refetch everything on screen.
                  window.location.reload()
                }}
                className={cn(
                  'flex h-9 w-full items-center rounded-lg px-3 text-[13px]',
                  role.user === user ? 'bg-raised text-white' : 'text-dim hover:text-white',
                )}
              >
                {role.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function Header({
  title,
  subtitle,
  stuck,
}: {
  title: string
  subtitle?: string
  stuck: boolean
}) {
  return (
    <header
      className={cn(
        'sticky top-0 z-20 flex items-center gap-4 rounded-t-panel px-5 py-4',
        stuck ? 'glass-dark rounded-b-none' : 'border border-transparent',
      )}
    >
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[22px] leading-7 font-semibold -tracking-[0.015em] text-white">
          {title}
        </h1>
        {subtitle && <p className="mt-0.5 truncate text-xs text-faint">{subtitle}</p>}
      </div>

      {/* The ring lives on the pill, not the bare input inside it. */}
      <label className="hidden h-9 max-w-[280px] flex-1 items-center gap-2 rounded-full bg-card px-4 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-white/60 lg:flex">
        <Search size={15} className="shrink-0 text-faint" />
        <input
          type="search"
          placeholder="Cari mesin atau work order…"
          className="w-full bg-transparent text-[13px] text-white placeholder:text-faint focus:outline-none"
          aria-label="Cari mesin atau work order"
        />
      </label>

      <div className="flex items-center gap-1">
        <button
          aria-label="Pengaturan"
          className="grid size-9 place-items-center rounded-full text-faint transition-colors duration-100 hover:text-white"
        >
          <Settings size={17} />
        </button>
        <button
          aria-label="Notifikasi"
          className="grid size-9 place-items-center rounded-full text-faint transition-colors duration-100 hover:text-white"
        >
          <Bell size={17} />
        </button>
        <RoleSwitcher />
      </div>
    </header>
  )
}
