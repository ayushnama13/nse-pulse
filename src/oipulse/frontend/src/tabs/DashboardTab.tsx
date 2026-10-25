import type { ReactNode } from 'react'
import { ArrowDownRight, ArrowUpRight, ExternalLink } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useFiiDii, useMarket, useMeta, useNews } from '@/api/research'
import { useShell } from '@/store'
import { openTicker } from '@/lib/eq'
import { cn } from '@/lib/utils'

const f2 = (n: number | null | undefined) => (n == null ? '—' : n.toLocaleString('en-IN', { maximumFractionDigits: 2 }))
const signed = (n: number | null | undefined) => (n == null ? '—' : `${n > 0 ? '+' : ''}${f2(n)}`)
const tone = (n: number | null | undefined) => (n == null || n === 0 ? '' : n > 0 ? 'text-profit' : 'text-loss')

function Tile({ label, value, sub, subClass }: { label: string; value: ReactNode; sub?: ReactNode; subClass?: string }) {
  return (
    <Card className="gap-1 py-4">
      <CardHeader className="pb-0"><CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle></CardHeader>
      <CardContent>
        <div className="font-mono text-2xl font-semibold tabular-nums">{value}</div>
        {sub != null && <div className={cn('mt-0.5 font-mono text-xs text-muted-foreground', subClass)}>{sub}</div>}
      </CardContent>
    </Card>
  )
}

function MoverList({ title, rows, up }: { title: string; rows: any[]; up: boolean }) {
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="pb-0">
        <CardTitle className="flex items-center gap-1.5 text-sm">
          {up ? <ArrowUpRight className="size-4 text-profit" /> : <ArrowDownRight className="size-4 text-loss" />}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-0.5">
        {rows.slice(0, 8).map((r) => (
          <button key={r.symbol} onClick={() => openTicker(r.symbol)} className="flex w-full items-center justify-between rounded px-2 py-1 text-sm hover:bg-accent">
            <span className="font-medium">{r.symbol}</span>
            <span className="flex gap-4 font-mono tabular-nums">
              <span className="text-muted-foreground">{f2(r.close)}</span>
              <span className={cn('w-16 text-right', tone(r.chg_pct))}>{signed(r.chg_pct)}%</span>
            </span>
          </button>
        ))}
        {!rows.length && <p className="px-2 text-sm text-muted-foreground">No data yet</p>}
      </CardContent>
    </Card>
  )
}

export function DashboardTab() {
  const meta = useMeta().data
  const market = useMarket().data
  const flows = useFiiDii(10).data
  const news = useNews().data
  const snap = useShell((s) => s.snap)
  const symbol = useShell((s) => s.symbol)

  const b = market?.breadth
  const pctUp = b?.total ? (b.advances / b.total) * 100 : 0
  const latestFlow = (cat: string) => {
    const rows = (flows?.daily ?? []).filter((r: any) => r.category === cat && r.segment === 'CASH')
    return rows[rows.length - 1]
  }
  const fii = latestFlow('FII')
  const dii = latestFlow('DII')

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Market snapshot</h1>
        {meta?.latest_date && <Badge variant="outline">EOD data as of {meta.latest_date}</Badge>}
        {meta && <Badge variant="secondary">{meta.trading_days} trading days loaded</Badge>}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label={`${symbol} spot (live)`} value={snap?.spot != null ? f2(snap.spot) : '—'} sub={snap ? `PCR ${f2(snap.pcr)}` : 'waiting for feed'} />
        <Tile
          label="Breadth"
          value={b ? `${b.advances} / ${b.declines}` : '—'}
          sub={b ? `${pctUp.toFixed(0)}% advancing of ${b.total}` : undefined}
          subClass={pctUp >= 50 ? 'text-profit' : 'text-loss'}
        />
        <Tile label="FII net (cash, ₹ Cr)" value={<span className={tone(fii?.net_value)}>{signed(fii?.net_value)}</span>} sub={fii ? String(fii.date).slice(0, 10) : undefined} />
        <Tile label="DII net (cash, ₹ Cr)" value={<span className={tone(dii?.net_value)}>{signed(dii?.net_value)}</span>} sub={dii ? String(dii.date).slice(0, 10) : undefined} />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <MoverList title="Top gainers" rows={market?.gainers ?? []} up />
        <MoverList title="Top losers" rows={market?.losers ?? []} up={false} />
      </div>

      <Card className="gap-2 py-4">
        <CardHeader className="pb-0"><CardTitle className="text-sm">Latest news</CardTitle></CardHeader>
        <CardContent className="space-y-1">
          {(news?.news ?? []).slice(0, 8).map((n: any) => (
            <a key={n.id} href={n.link} style={{ color: "inherit" }} target="_blank" rel="noreferrer" className="flex items-start text-foreground justify-between gap-3 rounded px-2 py-1.5 text-sm hover:bg-accent">
              <span>{n.title}</span>
              <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                {String(n.source).split('_')[0]} <ExternalLink className="size-3" />
              </span>
            </a>
          ))}
          {!news?.news?.length && <p className="px-2 text-sm text-muted-foreground">No news loaded</p>}
        </CardContent>
      </Card>
    </div>
  )
}
