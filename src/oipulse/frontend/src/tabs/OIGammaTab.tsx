import { useMemo, useState } from 'react'
import { GlassEmpty } from '@/components/Glass'
import { Card, Segmented, Space } from 'antd'
import { EChart } from '@/charts/EChart'
import type { EChartsOption } from '@/charts/echarts'
import { baseGrid, useChartChrome } from '@/charts/common'
import { useShell } from '@/store'
import { nearestATM, sliceAroundATM as sliceATM } from '@/lib/analytics'
import { fmt } from '@/lib/format'
import { palette } from '@/theme'
import type { ChainRow } from '@/api/types'

const MODES = [
  { label: 'OI', value: 'oi' },
  { label: 'Value ₹', value: 'value' },
  { label: 'ΔOI', value: 'chg' },
  { label: 'ΔOI×₹', value: 'chgvalue' },
]
type Mode = 'oi' | 'value' | 'chg' | 'chgvalue'

function OIByStrikeCard() {
  const C = useChartChrome()
  const snap = useShell((s) => s.snap)
  const [mode, setMode] = useState<Mode>('oi')
  const atm = nearestATM(snap?.chain ?? [], snap?.spot)
  const lot = snap?.lotSize ?? 1

  const option = useMemo<EChartsOption>(() => {
    const rows = sliceATM(snap?.chain ?? [], atm, 12)
    const cats = rows.map((r) => String(r.strike))
    const valOf = (r: ChainRow, side: 'ce' | 'pe') => {
      const oi = side === 'ce' ? r.ceOI : r.peOI
      const chg = side === 'ce' ? r.ceChg : r.peChg
      const ltp = side === 'ce' ? r.ceLTP : r.peLTP
      switch (mode) {
        case 'oi':
          return oi
        case 'value':
          return oi * ltp * lot
        case 'chg':
          return chg
        case 'chgvalue':
          return chg * ltp * lot
      }
    }
    const spotCat = atm != null ? cats.reduce((c, s) => (Math.abs(Number(s) - (snap?.spot ?? 0)) < Math.abs(Number(c) - (snap?.spot ?? 0)) ? s : c), cats[0]) : undefined
    const mpCat = cats.reduce((c, s) => (Math.abs(Number(s) - (snap?.maxPain ?? 0)) < Math.abs(Number(c) - (snap?.maxPain ?? 0)) ? s : c), cats[0])
    return {
      grid: baseGrid,
      tooltip: C.tooltipBase,
      legend: { data: ['CE', 'PE'], textStyle: C.legendText, top: 0 },
      xAxis: C.categoryAxis(cats),
      yAxis: C.valueAxis(),
      series: [
        {
          name: 'CE',
          type: 'bar',
          data: rows.map((r) => valOf(r, 'ce')),
          itemStyle: { color: palette.ce },
          markLine: {
            symbol: 'none',
            silent: true,
            lineStyle: { color: palette.gold, type: 'dashed' },
            data: [
              ...(spotCat ? [{ xAxis: spotCat, label: { formatter: 'Spot', color: palette.gold, fontSize: 9 } }] : []),
              ...(mpCat ? [{ xAxis: mpCat, label: { formatter: 'MP', color: palette.violet, fontSize: 9 } }] : []),
            ],
          },
        },
        { name: 'PE', type: 'bar', data: rows.map((r) => valOf(r, 'pe')), itemStyle: { color: palette.pe } },
      ],
    }
  }, [snap, atm, mode, lot, C])

  return (
    <Card
      size="small"
      title="Open Interest by Strike"
      extra={<Segmented size="small" options={MODES} value={mode} onChange={(v) => setMode(v as Mode)} />}
    >
      <EChart option={option} height={320} />
    </Card>
  )
}

function GammaCard() {
  const C = useChartChrome()
  const snap = useShell((s) => s.snap)
  const atm = nearestATM(snap?.chain ?? [], snap?.spot)

  const option = useMemo<EChartsOption>(() => {
    const gex = sliceATM(snap?.gex ?? [], atm, 14)
    const cats = gex.map((g) => String(g.strike))
    const flip = snap?.gammaFlip ?? null
    const flipCat = flip != null && cats.length ? cats.reduce((c, s) => (Math.abs(Number(s) - flip) < Math.abs(Number(c) - flip) ? s : c), cats[0]) : undefined
    return {
      grid: baseGrid,
      tooltip: C.tooltipBase,
      xAxis: C.categoryAxis(cats),
      yAxis: C.valueAxis('GEX'),
      series: [
        {
          name: 'GEX',
          type: 'bar',
          data: gex.map((g) => ({ value: g.gex, itemStyle: { color: g.gex >= 0 ? palette.bull : palette.bear } })),
          markLine: flipCat
            ? {
                symbol: 'none',
                silent: true,
                lineStyle: { color: palette.amber, type: 'dashed', width: 1.5 },
                data: [{ xAxis: flipCat, label: { formatter: 'γ-flip', color: palette.amber, fontSize: 9 } }],
              }
            : undefined,
        },
      ],
    }
  }, [snap, atm, C])

  return (
    <Card size="small" title={`Gamma Exposure · flip ${snap?.gammaFlip ? fmt(snap.gammaFlip) : '—'}`}>
      <EChart option={option} height={300} />
    </Card>
  )
}

export function OIGammaTab() {
  const snap = useShell((s) => s.snap)
  if (!snap) return <Card size="small"><GlassEmpty description="Waiting for data…" /></Card>
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <OIByStrikeCard />
      <GammaCard />
    </Space>
  )
}
