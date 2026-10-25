import { useMemo, useState } from 'react'
import { GlassEmpty, GlassLoader } from '@/components/Glass'
import { Card, Segmented, Space, Checkbox, Select } from 'antd'
import { EChart } from '@/charts/EChart'
import type { EChartsOption } from '@/charts/echarts'
import { baseGrid, useChartChrome } from '@/charts/common'
import { useShell } from '@/store'
import { useOIChange, useOIHistory, useIntradayFlow, useStrikeDetail, useDailyAggregate } from '@/api/queries'
import { nearestATM } from '@/lib/analytics'
import { fmtSigned } from '@/lib/format'
import { palette } from '@/theme'

const STRIKE_PALETTE = ['#22d3ee', '#5b9bff', '#3ecf8e', '#a78bfa', '#fbbf24', '#2dd4bf', '#ff7e67', '#a78bfa']

const WINDOWS = [
  { label: '5m', value: 5 },
  { label: '15m', value: 15 },
  { label: '30m', value: 30 },
  { label: '1h', value: 60 },
  { label: '2h', value: 120 },
  { label: 'Day', value: 1000 },
]

function OIChangeCard() {
  const C = useChartChrome()
  const snap = useShell((s) => s.snap)
  const symbol = useShell((s) => s.symbol)
  const [win, setWin] = useState(120)
  const { data, isLoading } = useOIChange(symbol, win)
  const atm = nearestATM(snap?.chain ?? [], snap?.spot)

  const option = useMemo<EChartsOption>(() => {
    const rows = data?.rows ?? []
    // ATM ±20 strikes by index (legacy renderOIChange slice) — index-based so
    // it works for any strike step (NIFTY 50, BANKNIFTY 100, …).
    const sliced =
      atm != null
        ? [...rows]
            .sort((a, b) => Math.abs(a.strike - atm) - Math.abs(b.strike - atm))
            .slice(0, 41)
            .sort((a, b) => a.strike - b.strike)
        : rows
    const cats = sliced.map((r) => String(r.strike))
    return {
      grid: baseGrid,
      tooltip: C.tooltipBase,
      legend: { data: ['CE ΔOI', 'PE ΔOI'], textStyle: C.legendText, top: 0 },
      xAxis: C.categoryAxis(cats),
      yAxis: C.valueAxis(),
      series: [
        { name: 'CE ΔOI', type: 'bar', data: sliced.map((r) => r.ceChg), itemStyle: { color: palette.ce } },
        { name: 'PE ΔOI', type: 'bar', data: sliced.map((r) => r.peChg), itemStyle: { color: palette.pe } },
      ],
    }
  }, [data, atm, C])

  return (
    <Card
      size="small"
      title="OI Change by Strike"
      extra={<Segmented size="small" options={WINDOWS} value={win} onChange={(v) => setWin(v as number)} />}
    >
      {isLoading ? (
        <GlassLoader />
      ) : data?.available === false ? (
        <GlassEmpty description="Need ≥2 snapshots in the window" />
      ) : (
        <>
          {data?.summary && (
            <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
              {data.summary.fromTime} → {data.summary.toTime} · ΣCE {fmtSigned(data.summary.totalCeChange)} · ΣPE{' '}
              {fmtSigned(data.summary.totalPeChange)}
            </div>
          )}
          <EChart option={option} height={300} />
        </>
      )}
    </Card>
  )
}

function MultiStrikeCard() {
  const C = useChartChrome()
  const snap = useShell((s) => s.snap)
  const symbol = useShell((s) => s.symbol)
  const atm = nearestATM(snap?.chain ?? [], snap?.spot)

  const topStrikes = useMemo(() => {
    const rows = [...(snap?.chain ?? [])].sort((a, b) => b.ceOI + b.peOI - (a.ceOI + a.peOI)).slice(0, 14)
    return rows.map((r) => r.strike).sort((a, b) => a - b)
  }, [snap])

  const [selected, setSelected] = useState<number[]>([])
  const [winMin, setWinMin] = useState<number | undefined>(undefined)
  const active = selected.length ? selected : topStrikes.slice(0, 6)
  const { data } = useOIHistory(symbol, { strikes: active.join(','), windowMin: winMin })

  const option = useMemo<EChartsOption>(() => {
    const series = data?.series ?? []
    const times = series.map((p) => p.time)
    const lines = active.flatMap((strike, i) => {
      const color = STRIKE_PALETTE[i % STRIKE_PALETTE.length]
      return [
        {
          name: `${strike} CE`,
          type: 'line' as const,
          data: series.map((p) => p.strikes[String(strike)]?.ceOI ?? null),
          showSymbol: false,
          lineStyle: { color, width: 1.5 },
          itemStyle: { color },
          yAxisIndex: 1,
        },
        {
          name: `${strike} PE`,
          type: 'line' as const,
          data: series.map((p) => p.strikes[String(strike)]?.peOI ?? null),
          showSymbol: false,
          lineStyle: { color, width: 1.5, type: 'dashed' as const },
          itemStyle: { color },
          yAxisIndex: 1,
        },
      ]
    })
    return {
      grid: { ...baseGrid, bottom: 48 },
      tooltip: C.tooltipBase,
      dataZoom: C.dataZoomInside,
      xAxis: { ...C.categoryAxis(times), boundaryGap: false },
      yAxis: [
        C.valueAxis('Spot', { position: 'left' }),
        C.valueAxis('OI', { position: 'right', splitLine: { show: false } }),
      ],
      series: [
        {
          name: 'Spot',
          type: 'line',
          data: series.map((p) => p.spot),
          showSymbol: false,
          lineStyle: { color: palette.fg4, width: 1 },
          itemStyle: { color: palette.fg4 },
          yAxisIndex: 0,
        },
        ...lines,
      ],
    }
  }, [data, active, C])

  return (
    <Card
      size="small"
      title="Multi-Strike OI"
      extra={
        <Segmented
          size="small"
          options={[
            { label: '1h', value: 60 },
            { label: '2h', value: 120 },
            { label: '4h', value: 240 },
            { label: 'All', value: 0 },
          ]}
          value={winMin ?? 0}
          onChange={(v) => setWinMin((v as number) || undefined)}
        />
      }
    >
      <Checkbox.Group
        value={active}
        onChange={(v) => setSelected(v as number[])}
        style={{ marginBottom: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}
      >
        {topStrikes.map((s) => (
          <Checkbox key={s} value={s} style={{ color: s === atm ? palette.gold : undefined }}>
            {s}
          </Checkbox>
        ))}
      </Checkbox.Group>
      <EChart option={option} height={320} />
    </Card>
  )
}

function CumulativeCard() {
  const C = useChartChrome()
  const symbol = useShell((s) => s.symbol)
  const { data } = useIntradayFlow(symbol, 500)
  const option = useMemo<EChartsOption>(() => {
    const s = data?.series ?? []
    const times = s.map((p) => p.time)
    return {
      grid: { ...baseGrid, bottom: 48 },
      tooltip: C.tooltipBase,
      legend: { data: ['CE ΣΔ', 'PE ΣΔ', 'PE−CE'], textStyle: C.legendText, top: 0 },
      dataZoom: C.dataZoomInside,
      xAxis: { ...C.categoryAxis(times), boundaryGap: false },
      yAxis: C.valueAxis(),
      series: [
        { name: 'CE ΣΔ', type: 'line', areaStyle: { opacity: 0.08 }, showSymbol: false, data: s.map((p) => p.totalCeChg), itemStyle: { color: palette.ce }, lineStyle: { color: palette.ce } },
        { name: 'PE ΣΔ', type: 'line', areaStyle: { opacity: 0.08 }, showSymbol: false, data: s.map((p) => p.totalPeChg), itemStyle: { color: palette.pe }, lineStyle: { color: palette.pe } },
        { name: 'PE−CE', type: 'line', showSymbol: false, data: s.map((p) => p.netChg), itemStyle: { color: palette.violet }, lineStyle: { color: palette.violet, type: 'dashed' } },
      ],
    }
  }, [data, C])
  return (
    <Card size="small" title="Cumulative ΔOI Tracker">
      <EChart option={option} height={300} />
    </Card>
  )
}

function ComboCard() {
  const C = useChartChrome()
  const snap = useShell((s) => s.snap)
  const symbol = useShell((s) => s.symbol)
  const atm = nearestATM(snap?.chain ?? [], snap?.spot)
  const strikes = useMemo(() => (snap?.chain ?? []).map((r) => r.strike), [snap])
  const [strike, setStrike] = useState<number | null>(null)
  const [side, setSide] = useState<'ce' | 'pe'>('ce')
  const active = strike ?? atm
  const { data } = useStrikeDetail(symbol, active)

  const option = useMemo<EChartsOption>(() => {
    const s = data?.series ?? []
    const times = s.map((p) => p.time)
    const ltp = s.map((p) => (side === 'ce' ? p.ceLTP : p.peLTP))
    const oi = s.map((p) => (side === 'ce' ? p.ceOI : p.peOI))
    return {
      grid: { ...baseGrid, bottom: 48 },
      tooltip: C.tooltipBase,
      dataZoom: C.dataZoomInside,
      xAxis: { ...C.categoryAxis(times), boundaryGap: false },
      yAxis: [C.valueAxis('LTP'), C.valueAxis('OI', { position: 'right', splitLine: { show: false } })],
      series: [
        { name: 'LTP', type: 'line', showSymbol: false, data: ltp, yAxisIndex: 0, itemStyle: { color: palette.violet }, lineStyle: { color: palette.violet } },
        { name: 'OI', type: 'line', showSymbol: false, data: oi, yAxisIndex: 1, itemStyle: { color: palette.info }, lineStyle: { color: palette.info } },
      ],
    }
  }, [data, side, C])

  return (
    <Card
      size="small"
      title={`Single-Strike Combo · ${active ?? '—'}`}
      extra={
        <Space>
          <Segmented size="small" options={[{ label: 'CE', value: 'ce' }, { label: 'PE', value: 'pe' }]} value={side} onChange={(v) => setSide(v as 'ce' | 'pe')} />
          <Select
            size="small"
            style={{ width: 110 }}
            value={active ?? undefined}
            onChange={(v) => setStrike(v)}
            options={strikes.map((s) => ({ value: s, label: String(s) }))}
            showSearch
          />
        </Space>
      }
    >
      <EChart option={option} height={300} />
    </Card>
  )
}

function DailyOICard() {
  const C = useChartChrome()
  const symbol = useShell((s) => s.symbol)
  const { data } = useDailyAggregate(symbol, 30)
  const option = useMemo<EChartsOption>(() => {
    const days = data?.days ?? []
    return {
      grid: { ...baseGrid, bottom: 44 },
      tooltip: C.tooltipBase,
      legend: { data: ['CE OI', 'PE OI', 'PCR'], textStyle: C.legendText, top: 0 },
      xAxis: { type: 'category', data: days.map((d) => d.date.slice(5)), axisLine: C.axisLine, axisLabel: { ...C.axisLabel, rotate: 45 } },
      yAxis: [C.valueAxis('OI'), C.valueAxis('PCR', { position: 'right', splitLine: { show: false }, max: 2 })],
      series: [
        { name: 'CE OI', type: 'bar', data: days.map((d) => d.totalCEOI), itemStyle: { color: palette.ce } },
        { name: 'PE OI', type: 'bar', data: days.map((d) => d.totalPEOI), itemStyle: { color: palette.pe } },
        { name: 'PCR', type: 'line', yAxisIndex: 1, showSymbol: false, data: days.map((d) => d.pcr), itemStyle: { color: palette.gold }, lineStyle: { color: palette.gold } },
      ],
    }
  }, [data, C])
  return (
    <Card size="small" title="Daily OI vs Time">
      <EChart option={option} height={300} />
    </Card>
  )
}

export function TrendsTab() {
  const snap = useShell((s) => s.snap)
  if (!snap) return <Card size="small"><GlassEmpty description="Waiting for data…" /></Card>
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <OIChangeCard />
      <MultiStrikeCard />
      <CumulativeCard />
      <ComboCard />
      <DailyOICard />
    </Space>
  )
}
