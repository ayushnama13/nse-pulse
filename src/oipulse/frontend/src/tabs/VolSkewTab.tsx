import { useMemo } from 'react'
import { GlassEmpty } from '@/components/Glass'
import { Card, Space, Tag } from 'antd'
import { EChart } from '@/charts/EChart'
import type { EChartsOption } from '@/charts/echarts'
import { baseGrid, useChartChrome } from '@/charts/common'
import { useShell } from '@/store'
import { useStraddleHistory } from '@/api/queries'
import { nearestATM, sliceAroundATM } from '@/lib/analytics'
import { fmt2 } from '@/lib/format'
import { palette } from '@/theme'

function IVSkewCard() {
  const C = useChartChrome()
  const snap = useShell((s) => s.snap)
  const atm = nearestATM(snap?.chain ?? [], snap?.spot)
  const rows = useMemo(() => sliceAroundATM(snap?.chain ?? [], atm, 14), [snap, atm])

  const skew = useMemo(() => {
    if (atm == null) return { val: 0, label: 'Flat', cls: 'neutral' as const }
    const below = rows.filter((r) => r.strike < atm && r.peIV > 0).map((r) => r.peIV)
    const above = rows.filter((r) => r.strike > atm && r.ceIV > 0).map((r) => r.ceIV)
    const mean = (a: number[]) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0)
    const v = mean(below) - mean(above)
    if (v > 1) return { val: v, label: 'PUT skew (bearish hedging)', cls: 'bear' as const }
    if (v < -1) return { val: v, label: 'CALL skew (squeeze risk)', cls: 'bull' as const }
    return { val: v, label: 'Flat', cls: 'neutral' as const }
  }, [rows, atm, C])

  const option = useMemo<EChartsOption>(() => {
    const cats = rows.map((r) => String(r.strike))
    return {
      grid: baseGrid,
      tooltip: C.tooltipBase,
      legend: { data: ['CE IV', 'PE IV'], textStyle: C.legendText, top: 0 },
      xAxis: C.categoryAxis(cats),
      yAxis: C.valueAxis('IV %'),
      series: [
        { name: 'CE IV', type: 'line', showSymbol: false, data: rows.map((r) => r.ceIV || null), itemStyle: { color: palette.ce }, lineStyle: { color: palette.ce } },
        { name: 'PE IV', type: 'line', showSymbol: false, data: rows.map((r) => r.peIV || null), itemStyle: { color: palette.pe }, lineStyle: { color: palette.pe } },
      ],
    }
  }, [rows, C])

  return (
    <Card size="small" title="IV Skew" extra={<Tag color={skew.cls === 'bull' ? 'green' : skew.cls === 'bear' ? 'red' : 'gold'}>{skew.label} · {fmt2(skew.val)}</Tag>}>
      <EChart option={option} height={300} />
    </Card>
  )
}

function StraddleCard() {
  const C = useChartChrome()
  const symbol = useShell((s) => s.symbol)
  const { data } = useStraddleHistory(symbol)
  const option = useMemo<EChartsOption>(() => {
    const s = data?.series ?? []
    return {
      grid: { ...baseGrid, bottom: 48 },
      tooltip: C.tooltipBase,
      dataZoom: C.dataZoomInside,
      xAxis: { ...C.categoryAxis(s.map((p) => p.time)), boundaryGap: false },
      yAxis: C.valueAxis('Premium ₹'),
      series: [
        {
          name: 'ATM Straddle',
          type: 'line',
          showSymbol: false,
          areaStyle: { color: { type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(34,211,238,0.26)' }, { offset: 1, color: 'rgba(34,211,238,0)' }] } },
          data: s.map((p) => p.straddle),
          itemStyle: { color: palette.gold },
          lineStyle: { color: palette.gold },
        },
      ],
    }
  }, [data, C])
  return (
    <Card size="small" title="ATM Straddle Premium">
      <EChart option={option} height={280} />
    </Card>
  )
}

function PCRCompareCard() {
  const C = useChartChrome()
  const symbol = useShell((s) => s.symbol)
  const { data } = useStraddleHistory(symbol)
  const option = useMemo<EChartsOption>(() => {
    const s = data?.series ?? []
    return {
      grid: { ...baseGrid, bottom: 48 },
      tooltip: C.tooltipBase,
      legend: { data: ['OI PCR', 'Vol PCR', 'WPCR'], textStyle: C.legendText, top: 0 },
      dataZoom: C.dataZoomInside,
      xAxis: { ...C.categoryAxis(s.map((p) => p.time)), boundaryGap: false },
      yAxis: C.valueAxis('PCR'),
      series: [
        { name: 'OI PCR', type: 'line', showSymbol: false, data: s.map((p) => p.pcr), itemStyle: { color: palette.gold }, lineStyle: { color: palette.gold } },
        { name: 'Vol PCR', type: 'line', showSymbol: false, data: s.map((p) => p.volPcr), itemStyle: { color: palette.ce }, lineStyle: { color: palette.ce } },
        { name: 'WPCR', type: 'line', showSymbol: false, data: s.map((p) => p.wpcr), itemStyle: { color: palette.violet }, lineStyle: { color: palette.violet } },
      ],
    }
  }, [data, C])
  return (
    <Card size="small" title="OI PCR vs Vol PCR vs WPCR">
      <EChart option={option} height={280} />
    </Card>
  )
}

function PremiumSkewCard() {
  const C = useChartChrome()
  const snap = useShell((s) => s.snap)
  const atm = nearestATM(snap?.chain ?? [], snap?.spot)
  const rows = useMemo(() => sliceAroundATM(snap?.chain ?? [], atm, 14), [snap, atm])
  const option = useMemo<EChartsOption>(() => {
    const cats = rows.map((r) => String(r.strike))
    return {
      grid: baseGrid,
      tooltip: C.tooltipBase,
      legend: { data: ['CE LTP', 'PE LTP'], textStyle: C.legendText, top: 0 },
      xAxis: C.categoryAxis(cats),
      yAxis: C.valueAxis('LTP ₹'),
      series: [
        { name: 'CE LTP', type: 'line', showSymbol: false, data: rows.map((r) => r.ceLTP || null), itemStyle: { color: palette.ce }, lineStyle: { color: palette.ce } },
        { name: 'PE LTP', type: 'line', showSymbol: false, data: rows.map((r) => r.peLTP || null), itemStyle: { color: palette.pe }, lineStyle: { color: palette.pe } },
      ],
    }
  }, [rows, C])
  return (
    <Card size="small" title="Premium Skew (CE vs PE LTP)">
      <EChart option={option} height={280} />
    </Card>
  )
}

function LadderCard() {
  const C = useChartChrome()
  const snap = useShell((s) => s.snap)
  const atm = nearestATM(snap?.chain ?? [], snap?.spot)
  const rows = useMemo(() => sliceAroundATM(snap?.chain ?? [], atm, 5), [snap, atm])
  const option = useMemo<EChartsOption>(() => {
    const cats = rows.map((r) => String(r.strike))
    return {
      grid: baseGrid,
      tooltip: C.tooltipBase,
      legend: { data: ['CE', 'PE'], textStyle: C.legendText, top: 0 },
      xAxis: C.categoryAxis(cats),
      yAxis: C.valueAxis('Straddle ₹'),
      series: [
        { name: 'CE', type: 'bar', stack: 'x', data: rows.map((r) => r.ceLTP), itemStyle: { color: palette.ce } },
        { name: 'PE', type: 'bar', stack: 'x', data: rows.map((r) => r.peLTP), itemStyle: { color: palette.pe } },
      ],
    }
  }, [rows, C])
  return (
    <Card size="small" title="Straddle Ladder (ATM ±5)">
      <EChart option={option} height={260} />
    </Card>
  )
}

export function VolSkewTab() {
  const snap = useShell((s) => s.snap)
  if (!snap) return <Card size="small"><GlassEmpty description="Waiting for data…" /></Card>
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <IVSkewCard />
      <StraddleCard />
      <PCRCompareCard />
      <PremiumSkewCard />
      <LadderCard />
    </Space>
  )
}
