import { useMemo, useState } from 'react'
import { GlassEmpty } from '@/components/Glass'
import { Card, Select, Segmented, InputNumber, Button, Space, Statistic } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { EChart } from '@/charts/EChart'
import type { EChartsOption } from '@/charts/echarts'
import { baseGrid, useChartChrome } from '@/charts/common'
import { useShell } from '@/store'
import { payoffCurve, payoffStats, type Leg } from '@/lib/payoff'
import { fmt, fmt2 } from '@/lib/format'
import { palette } from '@/theme'

interface LegUI {
  type: 'CE' | 'PE'
  action: 'BUY' | 'SELL'
  strike: number | null
  qty: number
  /** Premium locked when the leg was configured; null = follow live LTP. */
  premium: number | null
}

export function PayoffTab() {
  const C = useChartChrome()
  const snap = useShell((s) => s.snap)
  const chain = snap?.chain ?? []
  const spot = snap?.spot ?? 0
  const lot = snap?.lotSize ?? 1
  const strikes = useMemo(() => chain.map((r) => r.strike), [chain])

  const atmStrike = snap?.atmStrike ?? strikes[Math.floor(strikes.length / 2)] ?? null
  const [legs, setLegs] = useState<LegUI[]>([
    { type: 'CE', action: 'BUY', strike: null, qty: 1, premium: null },
    { type: 'PE', action: 'BUY', strike: null, qty: 1, premium: null },
  ])

  const premiumOf = (type: 'CE' | 'PE', strike: number | null): number => {
    if (strike == null) return 0
    const row = chain.find((r) => r.strike === strike)
    return row ? (type === 'CE' ? row.ceLTP : row.peLTP) : 0
  }

  const resolved: Leg[] = legs
    .map((l) => ({ ...l, strike: l.strike ?? atmStrike }))
    .filter((l): l is LegUI & { strike: number } => l.strike != null)
    .map((l) => ({ type: l.type, action: l.action, strike: l.strike, qty: l.qty, premium: l.premium ?? premiumOf(l.type, l.strike) }))

  const curve = useMemo(() => (spot ? payoffCurve(resolved, spot, lot) : { prices: [], pnl: [] }), [resolved, spot, lot])
  const stats = useMemo(() => payoffStats(curve), [curve])

  const option = useMemo<EChartsOption>(() => {
    // Profit/loss halves as two series split exactly at the breakevens.
    // (A piecewise visualMap did this before, but it crashes the minified
    // production ECharts bundle with "reading 'coord'" — two series are safe.)
    const pts: [number, number][] = curve.prices.map((p, i) => [p, curve.pnl[i]])
    const all: [number, number][] = [...pts, ...stats.breakevens.map((b) => [b, 0] as [number, number])].sort(
      (a, b) => a[0] - b[0],
    )
    const pos = all.map(([x, y]) => [x, y >= 0 ? y : null])
    const neg = all.map(([x, y]) => [x, y <= 0 ? y : null])
    const beMarks = stats.breakevens.map((b) => ({ xAxis: b, label: { formatter: `BE ${b.toFixed(0)}`, color: palette.gold, fontSize: 9 } }))
    return {
      grid: baseGrid,
      tooltip: {
        ...C.tooltipBase,
        formatter: (ps: unknown) => {
          const arr = ps as { value: [number, number | null] }[]
          const hit = arr.find((a) => a.value && a.value[1] != null) ?? arr[0]
          if (!hit?.value) return ''
          return `S ${fmt2(hit.value[0])}<br/>P&L ₹${fmt(hit.value[1] ?? 0)}`
        },
      },
      xAxis: { type: 'value', scale: true, axisLine: C.axisLine, axisLabel: { ...C.axisLabel, formatter: (v: number) => v.toFixed(0) } },
      yAxis: C.valueAxis('P&L ₹'),
      series: [
        {
          type: 'line',
          data: pos,
          showSymbol: false,
          lineStyle: { width: 2, color: palette.bull },
          itemStyle: { color: palette.bull },
          areaStyle: { opacity: 0.1, color: palette.bull },
          markLine: {
            symbol: 'none',
            silent: true,
            data: [
              { yAxis: 0, lineStyle: { color: palette.fg4 } },
              { xAxis: spot, lineStyle: { color: palette.violet, type: 'dashed' }, label: { formatter: 'Spot', color: palette.violet, fontSize: 9 } },
              ...beMarks.map((b) => ({ ...b, lineStyle: { color: palette.gold, type: 'dotted' as const } })),
            ],
          },
        },
        {
          type: 'line',
          data: neg,
          showSymbol: false,
          lineStyle: { width: 2, color: palette.bear },
          itemStyle: { color: palette.bear },
          areaStyle: { opacity: 0.1, color: palette.bear },
        },
      ],
    }
  }, [curve, stats, spot, C])

  const setLeg = (i: number, patch: Partial<LegUI>) => setLegs((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))

  if (!snap) return <Card size="small"><GlassEmpty description="Waiting for chain…" /></Card>

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Card size="small" title="Payoff Builder">
        <Space direction="vertical" style={{ width: '100%' }}>
          {legs.map((leg, i) => (
            <Space key={i} wrap>
              <Segmented size="small" options={['CE', 'PE']} value={leg.type} onChange={(v) => { const ty = v as 'CE' | 'PE'; setLeg(i, { type: ty, premium: premiumOf(ty, leg.strike ?? atmStrike) || null }) }} />
              <Segmented size="small" options={['BUY', 'SELL']} value={leg.action} onChange={(v) => setLeg(i, { action: v as 'BUY' | 'SELL' })} />
              <Select
                size="small"
                style={{ width: 110 }}
                placeholder="ATM"
                value={leg.strike ?? undefined}
                onChange={(v) => setLeg(i, { strike: v, premium: premiumOf(leg.type, v) || null })}
                options={strikes.map((s) => ({ value: s, label: String(s) }))}
                showSearch
              />
              <InputNumber size="small" min={1} max={50} value={leg.qty} onChange={(v) => setLeg(i, { qty: v ?? 1 })} addonAfter="lot" style={{ width: 110 }} />
              <InputNumber
                size="small"
                min={0}
                step={0.5}
                value={leg.premium ?? premiumOf(leg.type, leg.strike ?? atmStrike)}
                onChange={(v) => setLeg(i, { premium: v ?? null })}
                addonBefore="₹"
                style={{ width: 130 }}
              />
              {legs.length > 1 && <Button size="small" type="text" icon={<DeleteOutlined />} onClick={() => setLegs((ls) => ls.filter((_, idx) => idx !== i))} />}
            </Space>
          ))}
          <Button size="small" icon={<PlusOutlined />} onClick={() => setLegs((ls) => [...ls, { type: 'CE', action: 'BUY', strike: null, qty: 1, premium: null }])} disabled={legs.length >= 4}>
            Add leg
          </Button>
        </Space>
      </Card>

      <Card size="small">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px,1fr))', gap: 12, marginBottom: 8 }}>
          <Statistic title="Max Profit" value={stats.maxProfitUnbounded ? 'Unbounded' : `₹${fmt(stats.maxProfit)}`} valueStyle={{ color: palette.bull, fontFamily: 'IBM Plex Mono' }} />
          <Statistic title="Max Loss" value={stats.maxLossUnbounded ? 'Unbounded' : `₹${fmt(stats.maxLoss)}`} valueStyle={{ color: palette.bear, fontFamily: 'IBM Plex Mono' }} />
          <Statistic title="Break-even(s)" value={stats.breakevens.length ? stats.breakevens.map((b) => b.toFixed(0)).join(' · ') : '—'} valueStyle={{ fontFamily: 'IBM Plex Mono', fontSize: 16 }} />
        </div>
        <EChart option={option} height={340} />
        <div className="muted" style={{ fontSize: 11, textAlign: 'center' }}>±8% of spot · lot size {lot} · pure client-side, premium locks when a leg is set (editable); Unbounded = curve still rising/falling at ±8% edge</div>
      </Card>
    </Space>
  )
}
