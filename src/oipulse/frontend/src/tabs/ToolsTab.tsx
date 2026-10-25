import type { ComponentType } from 'react'
import { BarChart3, CalendarDays, Database, GitCompare, LineChart, ShieldCheck, Table2, type LucideProps } from 'lucide-react'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useShell } from '@/store'
import { TAB_LABELS } from '@/nav'

const TOOLS: { tab: string; icon: ComponentType<LucideProps>; desc: string }[] = [
  { tab: 'compare', icon: GitCompare, desc: 'Diff two option-chain snapshots side by side.' },
  { tab: 'calendar', icon: CalendarDays, desc: 'Compare OI and IV across upcoming expiries.' },
  { tab: 'payoff', icon: LineChart, desc: 'Build multi-leg strategies and view the payoff curve.' },
  { tab: 'eodchain', icon: Table2, desc: 'End-of-day option chain from the exchange archives.' },
  { tab: 'dq', icon: Database, desc: 'Row counts per table and scraper run history.' },
  { tab: 'fhealth', icon: ShieldCheck, desc: 'Coverage and freshness of fundamentals data.' },
  { tab: 'fsql', icon: BarChart3, desc: 'Run read-only SQL against the fundamentals database.' },
]

export function ToolsTab() {
  const setTab = useShell((s) => s.setTab)
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Tools</h1>
        <p className="text-sm text-muted-foreground">Less frequently used analysis and data pages.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {TOOLS.map(({ tab, icon: Icon, desc }) => (
          <Card key={tab} role="button" onClick={() => setTab(tab)} className="cursor-pointer gap-2 py-4 transition-colors hover:bg-accent">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><Icon className="size-4" /> {TAB_LABELS[tab]}</CardTitle>
              <CardDescription>{desc}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </div>
  )
}
