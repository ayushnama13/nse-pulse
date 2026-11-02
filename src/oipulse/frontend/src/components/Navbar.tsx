import { useEffect, useState } from 'react'
import {
  BarChart3, Database, Keyboard, Moon, Rows3, Search, ShieldCheck, Sun, UserRound, ChevronDown,
} from 'lucide-react'
import { useShell } from '@/store'
import { MENUS, TAB_LABELS, sectionOf, type Menu } from '@/nav'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

function LivePill() {
  const live = useShell((s) => s.live)
  const t = useShell((s) => s.snap?.time)
  const color = live === 'live' ? 'bg-profit' : live === 'stale' ? 'bg-amber-500' : 'bg-loss'
  return (
    <span className="hidden items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground lg:inline-flex" title={t ? `Last snapshot ${t}` : undefined}>
      <span className={cn('size-2 rounded-full', color, live === 'live' && 'animate-pulse')} />
      <span className="font-medium uppercase">{live}</span>
    </span>
  )
}

export function Navbar({ onSearch, onHelp }: { onSearch: () => void; onHelp: () => void }) {
  const tab = useShell((s) => s.tab)
  const setTab = useShell((s) => s.setTab)
  const theme = useShell((s) => s.theme)
  const toggleTheme = useShell((s) => s.toggleTheme)
  const toggleDensity = useShell((s) => s.toggleDensity)
  const current = sectionOf(tab)
  const [clock, setClock] = useState('')

  useEffect(() => {
    const tick = () =>
      setClock(new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false, hour: '2-digit', minute: '2-digit' }) + ' IST')
    tick()
    const id = setInterval(tick, 15000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-12 max-w-[1680px] items-center gap-3 px-4">
        <button className="mr-2 flex items-center gap-2 font-semibold tracking-tight text-foreground hover:opacity-80 transition-opacity" onClick={() => setTab('dashboard')}>
          <BarChart3 className="size-4 text-primary" />
          <span className="hidden sm:inline text-sm font-bold">NSE Pulse</span>
        </button>

        <nav className="hidden flex-1 items-center gap-1 md:flex">
          {MENUS.map((m: Menu) => {
            const active = current === m.key
            if (m.link) {
              return (
                <Button
                  key={m.key}
                  variant={active ? 'secondary' : 'ghost'}
                  size="sm"
                  className={cn('h-8 px-3 text-xs font-medium', !active && 'text-muted-foreground hover:text-foreground')}
                  onClick={() => setTab(m.link!)}
                >
                  {m.label}
                </Button>
              )
            }
            return (
              <DropdownMenu key={m.key}>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant={active ? 'secondary' : 'ghost'}
                    size="sm"
                    className={cn('h-8 gap-1 px-3 text-xs font-medium', !active && 'text-muted-foreground hover:text-foreground')}
                  >
                    {m.label}
                    <ChevronDown className="size-3 opacity-60" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-72 p-1">
                  {m.items && m.items.map((it) => (
                    <DropdownMenuItem
                      key={it.key}
                      onSelect={() => setTab(it.key)}
                      className="flex flex-col items-start gap-0.5 py-2 cursor-pointer"
                    >
                      <span className="font-medium text-foreground">{it.label}</span>
                      <span className="text-[11px] text-muted-foreground leading-tight">{it.description}</span>
                    </DropdownMenuItem>
                  ))}
                  {m.groups && m.groups.map((g, idx) => (
                    <div key={g.title || idx}>
                      {idx > 0 && <DropdownMenuSeparator className="my-1" />}
                      {g.title && <DropdownMenuLabel className="px-2 py-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">{g.title}</DropdownMenuLabel>}
                      {g.items.map((it) => (
                        <DropdownMenuItem
                          key={it.key}
                          onSelect={() => setTab(it.key)}
                          className="flex flex-col items-start gap-0.5 py-2 cursor-pointer"
                        >
                          <span className="font-medium text-foreground">{it.label}</span>
                          <span className="text-[11px] text-muted-foreground leading-tight">{it.description}</span>
                        </DropdownMenuItem>
                      ))}
                    </div>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )
          })}
        </nav>

        <div className="flex-1 md:hidden" />

        <div className="flex items-center gap-2">
          <LivePill />
          <span className="hidden font-mono text-xs text-muted-foreground lg:inline">{clock}</span>

          <Button variant="outline" size="sm" className="h-8 gap-1.5 px-2.5 text-xs text-muted-foreground" onClick={onSearch}>
            <Search className="size-3.5" />
            <span className="hidden sm:inline">Search</span>
            <kbd className="hidden rounded border px-1 font-mono text-[9px] sm:inline">Ctrl K</kbd>
          </Button>

          <Button variant="ghost" size="icon" className="size-8" onClick={toggleTheme} title="Toggle theme">
            {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="size-8" title="Profile & System"><UserRound className="size-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="text-xs font-mono uppercase tracking-wider text-muted-foreground">System</DropdownMenuLabel>
              <DropdownMenuItem onSelect={() => setTab('dq')} className="cursor-pointer"><Database className="size-4 mr-2 text-muted-foreground" /> {TAB_LABELS.dq}</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setTab('fhealth')} className="cursor-pointer"><ShieldCheck className="size-4 mr-2 text-muted-foreground" /> {TAB_LABELS.fhealth}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={toggleDensity} className="cursor-pointer"><Rows3 className="size-4 mr-2 text-muted-foreground" /> Toggle density</DropdownMenuItem>
              <DropdownMenuItem onSelect={onHelp} className="cursor-pointer"><Keyboard className="size-4 mr-2 text-muted-foreground" /> Keyboard shortcuts</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}

/** Mobile bottom nav showing the 6 menus with popup sheet for items. */
export function MobileBottomNav() {
  const setTab = useShell((s) => s.setTab)
  const tab = useShell((s) => s.tab)
  const current = sectionOf(tab)
  const [activeMenuKey, setActiveMenuKey] = useState<string | null>(null)

  const activeMenu = MENUS.find((m) => m.key === activeMenuKey)

  return (
    <>
      <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t bg-background md:hidden">
        {MENUS.map((m: Menu) => {
          const isSelected = current === m.key
          return (
            <button
              key={m.key}
              onClick={() => {
                if (m.link) {
                  setActiveMenuKey(null)
                  setTab(m.link)
                } else {
                  setActiveMenuKey(activeMenuKey === m.key ? null : m.key)
                }
              }}
              className={cn(
                'flex flex-1 flex-col items-center justify-center py-2 text-[10px] transition-colors',
                isSelected ? 'text-primary font-semibold' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <span className="truncate max-w-[54px]">{m.label}</span>
            </button>
          )
        })}
      </nav>

      {activeMenu && activeMenu.items && (
        <div className="fixed inset-x-0 bottom-12 z-50 max-h-80 overflow-y-auto border-t bg-popover p-3 shadow-lg md:hidden">
          <div className="mb-2 flex items-center justify-between font-medium text-xs text-muted-foreground">
            <span>{activeMenu.label}</span>
            <button onClick={() => setActiveMenuKey(null)} className="text-xs hover:text-foreground">Close</button>
          </div>
          <div className="flex flex-col gap-1">
            {activeMenu.items.map((it) => (
              <button
                key={it.key}
                onClick={() => {
                  setTab(it.key)
                  setActiveMenuKey(null)
                }}
                className="flex flex-col items-start rounded px-2 py-1.5 text-left hover:bg-muted"
              >
                <span className="text-sm font-medium">{it.label}</span>
                <span className="text-[11px] text-muted-foreground">{it.description}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {activeMenu && activeMenu.groups && (
        <div className="fixed inset-x-0 bottom-12 z-50 max-h-96 overflow-y-auto border-t bg-popover p-3 shadow-lg md:hidden">
          <div className="mb-2 flex items-center justify-between font-medium text-xs text-muted-foreground">
            <span>{activeMenu.label}</span>
            <button onClick={() => setActiveMenuKey(null)} className="text-xs hover:text-foreground">Close</button>
          </div>
          <div className="flex flex-col gap-3">
            {activeMenu.groups.map((g, idx) => (
              <div key={idx} className="flex flex-col gap-1">
                {g.title && <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground px-1">{g.title}</div>}
                {g.items.map((it) => (
                  <button
                    key={it.key}
                    onClick={() => {
                      setTab(it.key)
                      setActiveMenuKey(null)
                    }}
                    className="flex flex-col items-start rounded px-2 py-1.5 text-left hover:bg-muted"
                  >
                    <span className="text-sm font-medium">{it.label}</span>
                    <span className="text-[11px] text-muted-foreground">{it.description}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
