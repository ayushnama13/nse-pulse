import { useEffect, useRef } from 'react'
import { echarts, type EChartsOption } from './echarts'

/**
 * Generic ECharts React wrapper. Owns the instance lifecycle + ResizeObserver
 * so every chart in the app gets crosshair/zoom/tooltip from a single place
 * (the per-chart `option` decides which). `notMerge` defaults to true so option
 * changes fully replace rather than deep-merge (predictable for dynamic data).
 */
export function EChart({
  option,
  height = 320,
  className,
  notMerge = true,
  onReady,
}: {
  option: EChartsOption
  height?: number | string
  className?: string
  notMerge?: boolean
  onReady?: (chart: echarts.ECharts) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current, undefined, { renderer: 'canvas' })
    chartRef.current = chart
    onReady?.(chart)
    const ro = new ResizeObserver(() => chart.resize())
    ro.observe(ref.current)
    return () => {
      ro.disconnect()
      chart.dispose()
      chartRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, notMerge)
  }, [option, notMerge])

  return <div ref={ref} className={className} style={{ width: '100%', height }} />
}
