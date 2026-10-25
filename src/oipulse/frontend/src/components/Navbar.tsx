import { useEffect, useState, type ComponentType } from 'react'
import {
  Activity, BarChart3, Briefcase, Database, Filter, LayoutDashboard, LineChart, Moon, Keyboard,
  Rows3, Search, ShieldCheck, Sun, UserRound, Wrench, Building2, type LucideProps,
} from 'lucide-react'
import { useShell } from '@/store'
import { SECTIONS, TAB_LABELS, sectionOf, type SectionKey } from '@/nav'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

export const SECTION_ICONS: Record<SectionKey, ComponentType<LucideProps>> = {
  dashboard: LayoutDashboard,
  options: Activity,
  equities: LineChart,
  fundamentals: Building2,
  screener: Filter,
  portfolio: Briefcase,
  tools: Wrench,
}

function LivePill() {
  const live = useShell((s) => s.live)
  const t = useShell((s) => s.snap?.time)
  const color = live === 'live' ? 'bg-profit' : live === 'stale' ? 'bg-amber-500' : 'bg-loss'
  return (
    <span className="hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs text-muted-foreground lg:inline-flex" title={t ? `Last snapshot ${t}` : undefined}>
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
      <div className="mx-auto flex h-14 max-w-[1680px] items-center gap-2 px-4">
        <button className="mr-3 flex items-center gap-2 font-semibold tracking-tight" onClick={() => setTab('dashboard')}>
          <BarChart3 className="size-5" />
          <span className="hidden sm:inline">NSE Pulse</span>
        </button>

        <nav className="hidden flex-1 items-center gap-1 md:flex">
          {SECTIONS.map((s) => {
            const Icon = SECTION_ICONS[s.key]
            const active = current === s.key
            return (
              <Button
                key={s.key}
                variant={active ? 'secondary' : 'ghost'}
                size="sm"
                className={cn('gap-1.5', !active && 'text-muted-foreground')}
                onClick={() => setTab(s.tabs[0])}
                title={s.label}
              >
                <Icon />
                <span className="hidden xl:inline">{s.label}</span>
              </Button>
            )
          })}
        </nav>
        <div className="flex-1 md:hidden" />

        <LivePill />
        <span className="hidden font-mono text-xs text-muted-foreground lg:inline">{clock}</span>

        <Button variant="outline" size="sm" className="gap-2 text-muted-foreground" onClick={onSearch}>
          <Search />
          <span className="hidden sm:inline">Search</span>
          <kbd className="hidden rounded border px-1 font-mono text-[10px] sm:inline">Ctrl K</kbd>
        </Button>
        <Button variant="ghost" size="icon" onClick={toggleTheme} title="Toggle theme">
          {theme === 'dark' ? <Sun /> : <Moon />}
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" title="Menu"><UserRound /></Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>System</DropdownMenuLabel>
            <DropdownMenuItem onSelect={() => setTab('dq')}><Database /> {TAB_LABELS.dq}</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setTab('fhealth')}><ShieldCheck /> {TAB_LABELS.fhealth}</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={toggleDensity}><Rows3 /> Toggle density</DropdownMenuItem>
            <DropdownMenuItem onSelect={onHelp}><Keyboard /> Keyboard shortcuts</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}

/** Fixed bottom bar for phones: one icon per section. */
export function MobileBottomNav() {
  const tab = useShell((s) => s.tab)
  const setTab = useShell((s) => s.setTab)
  const current = sectionOf(tab)
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t bg-background md:hidden">
      {SECTIONS.map((s) => {
        const Icon = SECTION_ICONS[s.key]
        return (
          <button
            key={s.key}
            onClick={() => setTab(s.tabs[0])}
            className={cn('flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px]', current === s.key ? 'text-foreground' : 'text-muted-foreground')}
          >
            <Icon className="size-5" />
            {s.label.split(' ')[0]}
          </button>
        )
      })}
    </nav>
  )
}
