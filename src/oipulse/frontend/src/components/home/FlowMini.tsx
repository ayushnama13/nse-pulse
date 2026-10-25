import { useMemo } from 'react'
import { GlassEmpty } from '@/components/Glass'
import { Card } from 'antd'
import { EChart } from '@/charts/EChart'
import type { EChartsOption } from '@/charts/echarts'
import { baseGrid, useChartChrome } from '@/charts/common'
import { useShell } from '@/store'
import { useIntradayFlow } from '@/api/queries'
import { palette } from '@/theme'

/** Zone C — today's session: spot vs CE Δ vs PE Δ. The Pulse chart distilled
 *  to the current day with zero controls; "Open Pulse" for the full tool. */
export function FlowMini() {
  const C = useChartChrome()
  const symbol = useShell((s) => s.symbol)
  const setTab = useShell((s) => s.setTab)
  const { data } = useIntradayFlow(symbol, 500)

  const today = useMemo(() => {
    const series = data?.series ?? []
    if (!series.length) return []
    const last = series[series.length - 1].timestamp.slice(0, 10)
    return series.filter((p) => p.timestamp.slice(0, 10) === last)
  }, [data])

  const option = useMemo<EChartsOption>(() => {
    return {
      grid: { ...baseGrid, top: 30, bottom: 24 },
      tooltip: C.tooltipBase,
      legend: { data: ['Spot', 'CE Δ', 'PE Δ'], textStyle: C.legendText, top: 0 },
      xAxis: { ...C.categoryAxis(today.map((p) => p.time)), boundaryGap: false },
      yAxis: [
        C.valueAxis(undefined, { scale: true }),
        C.valueAxis(undefined, { position: 'right', splitLine: { show: false } }),
      ],
      series: [
        {
          name: 'Spot',
          type: 'line',
          showSymbol: false,
          data: today.map((p) => p.spot),
          areaStyle: { color: { type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(34,211,238,0.26)' }, { offset: 1, color: 'rgba(34,211,238,0)' }] } },
          itemStyle: { color: palette.gold },
          lineStyle: { color: palette.gold, width: 2 },
        },
        { name: 'CE Δ', type: 'line', yAxisIndex: 1, showSymbol: false, data: today.map((p) => p.totalCeChg), itemStyle: { color: palette.ce }, lineStyle: { color: palette.ce } },
        { name: 'PE Δ', type: 'line', yAxisIndex: 1, showSymbol: false, data: today.map((p) => p.totalPeChg), itemStyle: { color: palette.pe }, lineStyle: { color: palette.pe } },
      ],
    }
  }, [today, C])

  return (
    <Card
      size="small"
      title="Session flow · spot vs ΔOI"
      extra={
        <a onClick={() => setTab('pulse')} style={{ fontSize: 12 }}>
          Open Pulse →
        </a>
      }
    >
      {today.length ? <EChart option={option} height={240} /> : <GlassEmpty description="No snapshots captured today yet" />}
    </Card>
  )
}
