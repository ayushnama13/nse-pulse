import { useMemo, useState, type CSSProperties } from 'react'
import { GlassEmpty } from '@/components/Glass'
import { Card, Select, Space, Table, Statistic, Alert } from 'antd'
import { useShell } from '@/store'
import { useSnapshots, useCompare } from '@/api/queries'
import { fmt, fmt2, fmtSigned } from '@/lib/format'
import { topRanks } from '@/lib/analytics'
import { palette } from '@/theme'
import type { CompareRow, SnapshotMeta } from '@/api/types'

function groupByDate(snaps: SnapshotMeta[]): Record<string, SnapshotMeta[]> {
  const out: Record<string, SnapshotMeta[]> = {}
  for (const s of snaps) {
    const d = s.timestamp.slice(0, 10)
    ;(out[d] ??= []).push(s)
  }
  return out
}

export function CompareTab() {
  const symbol = useShell((s) => s.symbol)
  const { data: snaps } = useSnapshots(symbol)
  const byDate = useMemo(() => groupByDate(snaps ?? []), [snaps])
  const dates = useMemo(() => Object.keys(byDate).sort(), [byDate])

  const [dateA, setDateA] = useState<string>()
  const [tsA, setTsA] = useState<string>()
  const [dateB, setDateB] = useState<string>()
  const [tsB, setTsB] = useState<string>()

  const { data, isLoading, error } = useCompare(symbol, tsA, tsB)

  const timeOpts = (d?: string) => (d ? (byDate[d] ?? []).map((s) => ({ value: s.timestamp, label: s.time })) : [])
  const sameOrBad = tsA && tsB && tsA === tsB

  // ATM = the row strike CLOSEST to the A/B average (avg is usually not a real strike).
  const atm = useMemo(() => {
    if (!data?.rows?.length) return null
    const target = ((data.a.atmStrike ?? 0) + (data.b.atmStrike ?? 0)) / 2
    if (!target) return null
    return data.rows.reduce((best, r) => (Math.abs(r.strike - target) < Math.abs(best - target) ? r.strike : best), data.rows[0].strike)
  }, [data])

  // Top-5 per OI/ΔOI column (legacy parity) — gold tint on ranked cells.
  const ranks = useMemo(() => {
    const rows = data?.rows ?? []
    return {
      ceOIA: topRanks(rows, 'ceOIA', 5),
      ceOIB: topRanks(rows, 'ceOIB', 5),
      ceOIDelta: topRanks(rows, 'ceOIDelta', 5, true),
      peOIA: topRanks(rows, 'peOIA', 5),
      peOIB: topRanks(rows, 'peOIB', 5),
      peOIDelta: topRanks(rows, 'peOIDelta', 5, true),
    }
  }, [data])

  const cellStyle = (key: keyof typeof ranks, strike: number): CSSProperties | undefined =>
    ranks[key].has(strike) ? { background: 'rgba(34,211,238,0.12)', fontWeight: 600 } : undefined

  const oiCol = (title: string, key: keyof typeof ranks) => ({
    title,
    dataIndex: key,
    className: 'mono',
    render: (v: number, r: CompareRow) => <span style={cellStyle(key, r.strike)}>{fmt(v)}</span>,
  })
  const deltaCol = (title: string, key: 'ceOIDelta' | 'peOIDelta') => ({
    title,
    dataIndex: key,
    className: 'mono',
    render: (v: number, r: CompareRow) => (
      <span style={{ color: v > 0 ? palette.bull : v < 0 ? palette.bear : undefined, ...cellStyle(key, r.strike) }}>{fmtSigned(v)}</span>
    ),
  })

  const columns = [
    { title: 'Strike', dataIndex: 'strike', className: 'mono', fixed: 'left' as const, width: 90 },
    oiCol('CE A', 'ceOIA'),
    oiCol('CE B', 'ceOIB'),
    deltaCol('CE Δ', 'ceOIDelta'),
    oiCol('PE A', 'peOIA'),
    oiCol('PE B', 'peOIB'),
    deltaCol('PE Δ', 'peOIDelta'),
  ]

  const totals = useMemo(() => {
    const rows = data?.rows ?? []
    const ce = rows.reduce((a, r) => a + r.ceOIDelta, 0)
    const pe = rows.reduce((a, r) => a + r.peOIDelta, 0)
    return { ce, pe, net: pe - ce }
  }, [data])

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Card size="small" title="Compare two snapshots">
        <Space wrap>
          <Select placeholder="Date A" style={{ width: 130 }} value={dateA} onChange={(v) => { setDateA(v); setTsA(undefined) }} options={dates.map((d) => ({ value: d, label: d }))} />
          <Select placeholder="Time A" style={{ width: 110 }} value={tsA} onChange={setTsA} options={timeOpts(dateA)} disabled={!dateA} />
          <span className="muted">→</span>
          <Select placeholder="Date B" style={{ width: 130 }} value={dateB} onChange={(v) => { setDateB(v); setTsB(undefined) }} options={dates.map((d) => ({ value: d, label: d }))} />
          <Select placeholder="Time B" style={{ width: 110 }} value={tsB} onChange={setTsB} options={timeOpts(dateB)} disabled={!dateB} />
        </Space>
        {sameOrBad && <Alert style={{ marginTop: 8 }} type="info" message="A and B are the same snapshot." showIcon />}
      </Card>

      {!tsA || !tsB ? (
        <Card size="small"><GlassEmpty description="Pick two snapshots to compare" /></Card>
      ) : error ? (
        <Alert type="error" message={String((error as Error).message)} showIcon />
      ) : isLoading || !data ? (
        <Card size="small"><GlassEmpty description="Loading…" /></Card>
      ) : (
        <>
          <Card size="small">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px,1fr))', gap: 12 }}>
              <Statistic title="Spot Move" value={fmtSigned(data.spotMove)} valueStyle={{ color: data.spotMove >= 0 ? palette.bull : palette.bear, fontFamily: 'IBM Plex Mono' }} />
              <Statistic title="PCR Shift" value={fmt2(data.pcrShift)} valueStyle={{ fontFamily: 'IBM Plex Mono' }} />
              <Statistic title="Max Pain Shift" value={fmtSigned(data.maxPainShift)} valueStyle={{ fontFamily: 'IBM Plex Mono' }} />
              <Statistic title="Total CE ΔOI" value={fmtSigned(totals.ce)} valueStyle={{ color: palette.ce, fontFamily: 'IBM Plex Mono' }} />
              <Statistic title="Total PE ΔOI" value={fmtSigned(totals.pe)} valueStyle={{ color: palette.pe, fontFamily: 'IBM Plex Mono' }} />
              <Statistic title={totals.net > 0 ? 'PE > CE (lean bullish)' : totals.net < 0 ? 'CE > PE (lean bearish)' : 'flat'} value={fmtSigned(totals.net)} valueStyle={{ color: totals.net >= 0 ? palette.bull : palette.bear, fontFamily: 'IBM Plex Mono' }} />
            </div>
            <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>{data.a.time} → {data.b.time}</div>
          </Card>
          <Card size="small" styles={{ body: { padding: 8 } }}>
            <Table<CompareRow & { key: number }>
              size="small"
              pagination={false}
              scroll={{ y: 'calc(100vh - 460px)', x: true }}
              dataSource={(data.rows ?? []).filter((r) => r.ceOIA || r.ceOIB || r.peOIA || r.peOIB).map((r) => ({ ...r, key: r.strike }))}
              columns={columns}
              rowClassName={(r) => (atm != null && r.strike === atm ? 'atm-row' : '')}
            />
          </Card>
        </>
      )}
    </Space>
  )
}
