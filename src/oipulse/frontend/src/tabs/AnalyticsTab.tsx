import { useMemo } from 'react'
import { GlassEmpty } from '@/components/Glass'
import { Card, Space, Tag, Table } from 'antd'
import { EChart } from '@/charts/EChart'
import type { EChartsOption } from '@/charts/echarts'
import { baseGrid, useChartChrome } from '@/charts/common'
import { useShell } from '@/store'
import { useOIHistory, useStraddleHistory, useRegimeCalendar, useVix } from '@/api/queries'
import { classifyRegime, nearestATM, strengthOf, zScores, classifyBuildup } from '@/lib/analytics'
import { fmt, fmt2, fmtSigned } from '@/lib/format'
import { palette } from '@/theme'

function SynopsisCard() {
  const snap = useShell((s) => s.snap)
  const wpcr = useShell((s) => s.wpcr)
  const { data: vixEnv } = useVix()
  const vix = useMemo(() => {
    const env = vixEnv as Record<string, unknown> | undefined
    if (!env || env.available === false) return null
    const vd = (env.data ?? env) as Record<string, unknown>
    for (const k of ['last', 'lastValue', 'LTP', 'indexClose']) {
      const v = vd?.[k]
      if (typeof v === 'number') return v
      if (typeof v === 'string' && !Number.isNaN(Number(v))) return Number(v)
    }
    return null
  }, [vixEnv])
  const reg = useMemo(
    () =>
      classifyRegime({
        pcr: snap?.pcr ?? 0,
        volPcr: snap?.volPcr ?? 0,
        wpcr,
        spot: snap?.spot ?? null,
        gammaFlip: snap?.gammaFlip ?? null,
        chain: snap?.chain ?? [],
      }),
    [snap, wpcr],
  )
  const pcrCls = (v: number) => (v > 1.2 ? palette.bull : v < 0.8 ? palette.bear : palette.gold)
  const cells: { lab: string; val: string; color?: string }[] = [
    { lab: 'OI PCR', val: fmt2(snap?.pcr), color: pcrCls(snap?.pcr ?? 1) },
    { lab: 'Vol PCR', val: fmt2(snap?.volPcr), color: pcrCls(snap?.volPcr ?? 1) },
    { lab: 'WPCR', val: fmt2(wpcr), color: pcrCls(wpcr) },
    { lab: 'Max Pain', val: fmt(snap?.maxPain) },
    { lab: 'γ Flip', val: snap?.gammaFlip ? fmt(snap.gammaFlip) : '—', color: palette.amber },
    { lab: 'Total CE OI', val: fmt(snap?.totalCEOI), color: palette.ce },
    { lab: 'Total PE OI', val: fmt(snap?.totalPEOI), color: palette.pe },
    { lab: 'ATM Straddle', val: fmt2(snap?.atmStraddle) },
    {
      lab: 'OI Crossover',
      val: (snap?.totalPEOI ?? 0) > (snap?.totalCEOI ?? 0) ? 'PE > CE' : 'CE > PE',
      color: (snap?.totalPEOI ?? 0) > (snap?.totalCEOI ?? 0) ? palette.bull : palette.bear,
    },
    {
      lab: 'India VIX',
      val: vix != null ? fmt2(vix) : '—',
      color: vix == null ? undefined : vix < 12 ? palette.bull : vix > 20 ? palette.bear : palette.gold,
    },
  ]
  return (
    <Card
      size="small"
      title="F&O Synopsis"
      extra={<Tag color={reg.cls === 'bull' ? 'green' : reg.cls === 'bear' ? 'red' : reg.cls === 'warn' ? 'gold' : 'default'}>● {reg.regime}</Tag>}
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px,1fr))', gap: 8 }}>
        {cells.map((c) => (
          <div key={c.lab} style={{ background: 'var(--bg-1)', borderRadius: 8, padding: '8px 10px' }}>
            <div className="muted" style={{ fontSize: 10, textTransform: 'uppercase' }}>{c.lab}</div>
            <div className="mono" style={{ fontSize: 17, color: c.color ?? 'var(--fg)' }}>{c.val}</div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function PCRGaugeCard() {
  const C = useChartChrome()
  const snap = useShell((s) => s.snap)
  const pcr = snap?.pcr ?? 0
  const option = useMemo<EChartsOption>(
    () => ({
      series: [
        {
          type: 'gauge',
          min: 0,
          max: 2,
          radius: '95%',
          center: ['50%', '62%'],
          startAngle: 200,
          endAngle: -20,
          progress: { show: true, width: 14, itemStyle: { color: pcr > 1.2 ? palette.bull : pcr < 0.8 ? palette.bear : palette.gold } },
          axisLine: { lineStyle: { width: 14, color: [[1, C.trackColor]] } },
          axisLabel: { color: C.labelColor, fontSize: 9, distance: 14 },
          axisTick: { show: false },
          splitLine: { distance: 2, length: 8, lineStyle: { color: C.lineColor } },
          pointer: { itemStyle: { color: palette.gold } },
          anchor: { show: false },
          detail: { valueAnimation: true, fontSize: 22, fontFamily: 'IBM Plex Mono', color: C.fgColor, offsetCenter: [0, '32%'], formatter: (v: number) => v.toFixed(2) },
          data: [{ value: pcr }],
        },
      ],
    }),
    [pcr, C],
  )
  return (
    <Card size="small" title="PCR Gauge">
      <EChart option={option} height={220} />
    </Card>
  )
}

function SpotTrendCard() {
  const C = useChartChrome()
  const symbol = useShell((s) => s.symbol)
  const { data } = useStraddleHistory(symbol)
  const option = useMemo<EChartsOption>(() => {
    const s = data?.series ?? []
    return {
      grid: { ...baseGrid, bottom: 36 },
      tooltip: C.tooltipBase,
      xAxis: { ...C.categoryAxis(s.map((p) => p.time)), boundaryGap: false },
      yAxis: C.valueAxis('Spot', { scale: true }),
      series: [{ type: 'line', showSymbol: false, data: s.map((p) => p.spot), areaStyle: { color: { type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(34,211,238,0.26)' }, { offset: 1, color: 'rgba(34,211,238,0)' }] } }, itemStyle: { color: palette.gold }, lineStyle: { color: palette.gold } }],
    }
  }, [data, C])
  return (
    <Card size="small" title="Spot Price Trend">
      <EChart option={option} height={240} />
    </Card>
  )
}

function BuildupOverTimeCard() {
  const C = useChartChrome()
  const symbol = useShell((s) => s.symbol)
  const { data } = useOIHistory(symbol, { top: 6 })
  const palette6 = ['#22d3ee', '#5b9bff', '#3ecf8e', '#a78bfa', '#fbbf24', '#ff7e67']
  const option = useMemo<EChartsOption>(() => {
    const series = data?.series ?? []
    const strikes = data?.strikes ?? []
    const times = series.map((p) => p.time)
    return {
      grid: { ...baseGrid, bottom: 40 },
      tooltip: C.tooltipBase,
      legend: { textStyle: C.legendText, top: 0, type: 'scroll' },
      xAxis: { ...C.categoryAxis(times), boundaryGap: false },
      yAxis: C.valueAxis('OI'),
      series: strikes.map((st, i) => ({
        name: String(st),
        type: 'line' as const,
        showSymbol: false,
        data: series.map((p) => (p.strikes[String(st)]?.ceOI ?? 0) + (p.strikes[String(st)]?.peOI ?? 0)),
        itemStyle: { color: palette6[i % 6] },
        lineStyle: { color: palette6[i % 6] },
      })),
    }
  }, [data, C])
  return (
    <Card size="small" title="OI Build-up Over Time (top 6)">
      <EChart option={option} height={280} />
    </Card>
  )
}

function SpurtsCard() {
  const snap = useShell((s) => s.snap)
  const spurts = useMemo(() => {
    const out: { strike: number; side: 'CE' | 'PE'; chg: number }[] = []
    for (const r of snap?.chain ?? []) {
      if (Math.abs(r.ceChg) > 50000) out.push({ strike: r.strike, side: 'CE', chg: r.ceChg })
      if (Math.abs(r.peChg) > 50000) out.push({ strike: r.strike, side: 'PE', chg: r.peChg })
    }
    return out.sort((a, b) => Math.abs(b.chg) - Math.abs(a.chg)).slice(0, 24)
  }, [snap])
  return (
    <Card size="small" title="OI Spurts (|ΔOI| > 50K)">
      {spurts.length ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {spurts.map((s, i) => {
            const tag = strengthOf(Math.abs(s.chg))
            return (
              <Tag key={i} color={s.chg > 0 ? 'green' : 'red'} style={tag === 'STRONG' ? { fontWeight: 700 } : undefined}>
                {s.strike} {s.side} {fmtSigned(s.chg)} · {tag}
              </Tag>
            )
          })}
        </div>
      ) : (
        <GlassEmpty description="No spurts" />
      )}
    </Card>
  )
}

function BuildupTableCard() {
  const snap = useShell((s) => s.snap)
  const atm = nearestATM(snap?.chain ?? [], snap?.spot)
  const rows = useMemo(() => {
    const r = (snap?.chain ?? []).filter((x) => atm == null || Math.abs(x.strike - atm) <= 500)
    return r.map((x) => ({
      key: x.strike,
      strike: x.strike,
      ce: classifyBuildup('ce', x.ceChg),
      ceChg: x.ceChg,
      pe: classifyBuildup('pe', x.peChg),
      peChg: x.peChg,
    }))
  }, [snap, atm])
  return (
    <Card size="small" title="Position Buildup (ATM ±500)">
      <Table
        size="small"
        pagination={false}
        scroll={{ y: 280 }}
        dataSource={rows}
        columns={[
          { title: 'Strike', dataIndex: 'strike', className: 'mono' },
          { title: 'CE', dataIndex: 'ce', render: (v: string) => <span style={{ color: v.includes('Buildup') ? palette.bear : palette.bull }}>{v}</span> },
          { title: 'CE ΔOI', dataIndex: 'ceChg', className: 'mono', render: (v: number) => fmtSigned(v) },
          { title: 'PE', dataIndex: 'pe', render: (v: string) => <span style={{ color: v.includes('Buildup') ? palette.bear : palette.bull }}>{v}</span> },
          { title: 'PE ΔOI', dataIndex: 'peChg', className: 'mono', render: (v: number) => fmtSigned(v) },
        ]}
      />
    </Card>
  )
}

function ScannerCard() {
  const snap = useShell((s) => s.snap)
  const rows = useMemo(() => {
    const out: { key: string; strike: number; side: string; chg: number }[] = []
    for (const r of snap?.chain ?? []) {
      if (Math.abs(r.ceChg) > 10000) out.push({ key: r.strike + 'ce', strike: r.strike, side: 'CE', chg: r.ceChg })
      if (Math.abs(r.peChg) > 10000) out.push({ key: r.strike + 'pe', strike: r.strike, side: 'PE', chg: r.peChg })
    }
    return out.sort((a, b) => Math.abs(b.chg) - Math.abs(a.chg)).slice(0, 14)
  }, [snap])
  return (
    <Card size="small" title="Activity Scanner (top 14)">
      <Table
        size="small"
        pagination={false}
        dataSource={rows}
        columns={[
          { title: 'Strike', dataIndex: 'strike', className: 'mono' },
          { title: 'Side', dataIndex: 'side' },
          { title: 'ΔOI', dataIndex: 'chg', className: 'mono', render: (v: number) => <span style={{ color: v > 0 ? palette.bull : palette.bear }}>{fmtSigned(v)}</span> },
        ]}
      />
    </Card>
  )
}

function ZScoreCard() {
  const snap = useShell((s) => s.snap)
  const rows = useMemo(() => {
    const ce = zScores(snap?.chain ?? [], 'ce').map((x) => ({ ...x, side: 'CE' }))
    const pe = zScores(snap?.chain ?? [], 'pe').map((x) => ({ ...x, side: 'PE' }))
    return [...ce, ...pe].sort((a, b) => Math.abs(b.z) - Math.abs(a.z)).slice(0, 10).map((x, i) => ({ key: i, ...x }))
  }, [snap])
  return (
    <Card size="small" title="OI Z-Score (|z| ≥ 2)">
      {rows.length ? (
        <Table
          size="small"
          pagination={false}
          dataSource={rows}
          columns={[
            { title: 'Strike', dataIndex: 'strike', className: 'mono' },
            { title: 'Side', dataIndex: 'side' },
            { title: 'z', dataIndex: 'z', className: 'mono', render: (v: number) => fmt2(v) },
          ]}
        />
      ) : (
        <GlassEmpty description="No outliers" />
      )}
    </Card>
  )
}

function TrapCard() {
  const snap = useShell((s) => s.snap)
  const rows = useMemo(() => {
    const out: { key: string; strike: number; side: string; chg: number; ltp: number }[] = []
    for (const r of snap?.chain ?? []) {
      if (Math.abs(r.ceChg) > 30000 && r.ceChg < 0 && r.ceLTP > 0) out.push({ key: r.strike + 'ce', strike: r.strike, side: 'CE', chg: r.ceChg, ltp: r.ceLTP })
      if (Math.abs(r.peChg) > 30000 && r.peChg < 0 && r.peLTP > 0) out.push({ key: r.strike + 'pe', strike: r.strike, side: 'PE', chg: r.peChg, ltp: r.peLTP })
    }
    return out.sort((a, b) => a.chg - b.chg).slice(0, 6)
  }, [snap])
  return (
    <Card size="small" title="Trap Indicator">
      {rows.length ? (
        <Space direction="vertical" style={{ width: '100%' }}>
          {rows.map((r) => (
            <div key={r.key} style={{ display: 'flex', justifyContent: 'space-between', background: 'var(--bg-1)', padding: '6px 10px', borderRadius: 6 }}>
              <span className="mono">{r.strike} {r.side}</span>
              <span className="mono" style={{ color: palette.bear }}>{fmtSigned(r.chg)} · ₹{fmt2(r.ltp)}</span>
            </div>
          ))}
        </Space>
      ) : (
        <GlassEmpty description="No traps" />
      )}
    </Card>
  )
}

function RegimeHeatmapCard() {
  const C = useChartChrome()
  const symbol = useShell((s) => s.symbol)
  const { data } = useRegimeCalendar(symbol, 30)
  const option = useMemo<EChartsOption>(() => {
    const days = data?.days ?? []
    const buckets = data?.buckets ?? []
    const clsToVal: Record<string, number> = { bear: 0, warn: 1, neutral: 2, bull: 3 }
    const cells: [number, number, number][] = []
    days.forEach((d, y) => {
      d.cells.forEach((c, x) => {
        if (c.cls && c.cls !== 'empty') cells.push([x, y, clsToVal[c.cls] ?? 2])
      })
    })
    return {
      grid: { left: 80, right: 16, top: 8, bottom: 30 },
      tooltip: {
        ...C.tooltipBase,
        trigger: 'item',
        // ECharts callback params are loosely typed; narrow locally.
        formatter: (p: unknown) => {
          const val = (p as { value: [number, number, number] }).value
          const [x, y] = val
          const cell = days[y]?.cells[x]
          return `${days[y]?.date} ${buckets[x]}<br/>${cell?.regime ?? '—'}`
        },
      },
      xAxis: { type: 'category', data: buckets, axisLine: C.axisLine, axisLabel: C.axisLabel, splitArea: { show: true } },
      yAxis: { type: 'category', data: days.map((d) => d.date.slice(5)), axisLine: C.axisLine, axisLabel: { ...C.axisLabel, fontSize: 9 } },
      visualMap: {
        show: false,
        min: 0,
        max: 3,
        inRange: { color: [palette.bear, palette.amber, palette.violet, palette.bull] },
      },
      series: [{ type: 'heatmap', data: cells, itemStyle: { borderColor: C.heatmapBorder, borderWidth: 1 } }],
    }
  }, [data, C])
  return (
    <Card size="small" title="Regime Calendar (30d × intraday)">
      <EChart option={option} height={Math.max(260, (data?.days.length ?? 8) * 16 + 60)} />
    </Card>
  )
}

export function AnalyticsTab() {
  const snap = useShell((s) => s.snap)
  if (!snap) return <Card size="small"><GlassEmpty description="Waiting for data…" /></Card>
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <SynopsisCard />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px,1fr))', gap: 12 }}>
        <PCRGaugeCard />
        <SpotTrendCard />
      </div>
      <BuildupOverTimeCard />
      <SpurtsCard />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px,1fr))', gap: 12 }}>
        <ScannerCard />
        <ZScoreCard />
        <TrapCard />
      </div>
      <BuildupTableCard />
      <RegimeHeatmapCard />
    </Space>
  )
}
