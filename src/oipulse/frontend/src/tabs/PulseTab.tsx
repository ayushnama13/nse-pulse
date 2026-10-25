import { useEffect, useMemo, useRef, useState } from 'react'
import { GlassEmpty, GlassLoader } from '@/components/Glass'
import {
  createChart,
  ColorType,
  LineStyle,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts'
import { Card, Select, Segmented, Slider, Space } from 'antd'
import { useShell } from '@/store'
import { useIntradayFlow } from '@/api/queries'
import { rebasePulse, tsToMinFrom915, minToHHMM, type PulseRefMode } from '@/lib/analytics'
import { palette } from '@/theme'

const REF_MODES = [
  { label: 'Prev Close', value: 'prev' },
  { label: 'Day Start', value: 'day' },
  { label: 'Window Start', value: 'window' },
]

const SLIDER_MARKS = {
  0: '09:15',
  75: '10:30',
  150: '11:45',
  225: '13:00',
  300: '14:15',
  375: '15:30',
}

// lightweight-charts renders epoch as UTC; shift by IST offset so the axis
// shows local session times (09:15…15:30), matching the legacy labels.
const IST_OFFSET_SEC = 19800
const toUTC = (ts: string) => (Math.floor(new Date(ts).getTime() / 1000) + IST_OFFSET_SEC) as UTCTimestamp

// Chart chrome per theme (series hues stay constant; only text/grid flip).
const LWC_CHROME = {
  dark: { text: palette.fg3, grid: palette.line, border: palette.line },
  light: { text: '#5c6478', grid: '#e1e5ed', border: '#e1e5ed' },
}

export function PulseTab() {
  const symbol = useShell((s) => s.symbol)
  const theme = useShell((s) => s.theme)
  const { data, isLoading } = useIntradayFlow(symbol, 500)
  const series = useMemo(() => data?.series ?? [], [data])

  const dates = useMemo(() => {
    const set = new Set(series.map((p) => p.timestamp.slice(0, 10)))
    return [...set].sort((a, b) => (a < b ? 1 : -1))
  }, [series])

  const [date, setDate] = useState<string | undefined>()
  const [mode, setMode] = useState<PulseRefMode>('prev')
  const [win, setWin] = useState<[number, number]>([0, 375])

  const activeDate = date && dates.includes(date) ? date : dates[0]

  const day = useMemo(
    () =>
      series
        .filter((p) => p.timestamp.slice(0, 10) === activeDate)
        .sort((a, b) => (a.timestamp < b.timestamp ? -1 : 1)),
    [series, activeDate],
  )

  const rebased = useMemo(() => rebasePulse(day, win[0], win[1], mode), [day, win, mode])

  // ── chart lifecycle ──
  const elRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const spotRef = useRef<ISeriesApi<'Area'> | null>(null)
  const ceRef = useRef<ISeriesApi<'Line'> | null>(null)
  const peRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    if (!elRef.current) return
    const ch = LWC_CHROME[theme]
    const chart = createChart(elRef.current, {
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: ch.text, fontFamily: "'IBM Plex Mono', monospace" },
      grid: { vertLines: { color: ch.grid }, horzLines: { color: ch.grid } },
      rightPriceScale: { borderColor: ch.border },
      leftPriceScale: { borderColor: ch.border, visible: true },
      timeScale: { borderColor: ch.border, timeVisible: true, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
      autoSize: true,
    })
    chartRef.current = chart
    spotRef.current = chart.addAreaSeries({
      priceScaleId: 'left',
      lineColor: palette.gold,
      topColor: 'rgba(34,211,238,0.18)',
      bottomColor: 'rgba(34,211,238,0.01)',
      lineWidth: 2,
      priceLineVisible: false,
    })
    ceRef.current = chart.addLineSeries({ priceScaleId: 'right', color: palette.ce, lineWidth: 2, priceLineVisible: false })
    peRef.current = chart.addLineSeries({
      priceScaleId: 'right',
      color: palette.pe,
      lineWidth: 2,
      priceLineVisible: false,
      lineStyle: LineStyle.Solid,
    })
    return () => {
      chart.remove()
      chartRef.current = null
    }
    // re-created on theme toggle so the chrome colors apply
  }, [theme])

  useEffect(() => {
    if (!chartRef.current || !rebased.points.length) {
      spotRef.current?.setData([])
      ceRef.current?.setData([])
      peRef.current?.setData([])
      return
    }
    const pts = rebased.points
    spotRef.current?.setData(pts.map((p) => ({ time: toUTC(p.timestamp), value: p.spot })))
    ceRef.current?.setData(pts.map((p, i) => ({ time: toUTC(p.timestamp), value: rebased.ce[i] })))
    peRef.current?.setData(pts.map((p, i) => ({ time: toUTC(p.timestamp), value: rebased.pe[i] })))
    chartRef.current.timeScale().fitContent()
    // theme dep: series refs are recreated when the chart re-inits on toggle
  }, [rebased, theme])

  if (isLoading) return <Card size="small"><div style={{ textAlign: 'center', padding: 60 }}><GlassLoader /></div></Card>
  if (!dates.length)
    return (
      <Card size="small">
        <GlassEmpty description="No intraday-flow history yet. Capture some snapshots during the window." />
      </Card>
    )

  return (
    <Card
      size="small"
      title={
        <Space size={4}>
          <span style={{ color: palette.gold }}>●</span> Spot
          <span style={{ color: palette.ce, marginLeft: 8 }}>●</span> CE Δ
          <span style={{ color: palette.pe, marginLeft: 8 }}>●</span> PE Δ
        </Space>
      }
      extra={
        <Space wrap>
          <Select
            size="small"
            value={activeDate}
            onChange={setDate}
            options={dates.map((d) => ({ value: d, label: d }))}
            style={{ width: 140 }}
          />
          <Segmented size="small" options={REF_MODES} value={mode} onChange={(v) => setMode(v as PulseRefMode)} />
        </Space>
      }
    >
      <div ref={elRef} style={{ width: '100%', height: 380 }} />
      <div style={{ padding: '8px 12px 0' }}>
        <Slider
          range
          min={0}
          max={375}
          marks={SLIDER_MARKS}
          value={win}
          onChange={(v) => setWin(v as [number, number])}
          tooltip={{ formatter: (v) => (v == null ? '' : minToHHMM(v)) }}
        />
        <div className="muted" style={{ textAlign: 'center', fontSize: 12 }}>
          {minToHHMM(win[0])} → {minToHHMM(win[1])} · {rebased.points.length} points
          {day.length ? ` · day spans ${minToHHMM(tsToMinFrom915(day[0].timestamp))}–${minToHHMM(tsToMinFrom915(day[day.length - 1].timestamp))}` : ''}
        </div>
      </div>
    </Card>
  )
}
