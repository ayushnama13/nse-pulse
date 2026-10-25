import { useMemo, useState } from 'react'
import { GlassEmpty, GlassLoader } from '@/components/Glass'
import { Card, Segmented, Table } from 'antd'
import { useShell } from '@/store'
import { useCalendar } from '@/api/queries'
import { fmt, fmt2 } from '@/lib/format'
import { palette } from '@/theme'
import type { CalendarRow } from '@/api/types'

const COUNTS = [
  { label: '3', value: 3 },
  { label: '4', value: 4 },
  { label: '6', value: 6 },
  { label: '8', value: 8 },
  { label: '12', value: 12 },
]

export function CalendarTab() {
  const symbol = useShell((s) => s.symbol)
  const [n, setN] = useState(6)
  const { data, isLoading } = useCalendar(symbol, n)

  // IV term-structure colour scale: green (low) → red (high) across rows.
  const ivBounds = useMemo(() => {
    const ivs = (data?.expiries ?? []).map((r) => r.atmIv).filter((x) => x > 0)
    if (!ivs.length) return { min: 0, max: 1 }
    return { min: Math.min(...ivs), max: Math.max(...ivs) }
  }, [data])

  const ivColor = (iv: number) => {
    const t = ivBounds.max > ivBounds.min ? (iv - ivBounds.min) / (ivBounds.max - ivBounds.min) : 0.5
    const r = Math.round(45 + t * 200)
    const g = Math.round(212 - t * 140)
    return `rgb(${r},${g},120)`
  }

  const columns = [
    { title: 'Expiry', dataIndex: 'expiry', className: 'mono' },
    { title: 'DTE', dataIndex: 'dte', className: 'mono', render: (v: number) => fmt2(v) },
    { title: 'ATM', dataIndex: 'atmStrike', className: 'mono', render: (v: number) => fmt(v) },
    { title: 'Straddle', dataIndex: 'atmStraddle', className: 'mono', render: (v: number) => fmt2(v) },
    { title: 'ATM IV', dataIndex: 'atmIv', className: 'mono', render: (v: number) => <span style={{ color: ivColor(v) }}>{fmt2(v)}</span> },
    { title: 'PCR', dataIndex: 'pcr', className: 'mono', render: (v: number) => <span style={{ color: v > 1.2 ? palette.bull : v < 0.8 ? palette.bear : palette.fg }}>{fmt2(v)}</span> },
    { title: 'Max Pain', dataIndex: 'maxPain', className: 'mono', render: (v: number) => fmt(v) },
    { title: 'CE OI', dataIndex: 'totalCEOI', className: 'mono', render: (v: number) => fmt(v) },
    { title: 'PE OI', dataIndex: 'totalPEOI', className: 'mono', render: (v: number) => fmt(v) },
  ]

  return (
    <Card
      size="small"
      title="Expiry Calendar"
      extra={<Segmented size="small" options={COUNTS} value={n} onChange={(v) => setN(v as number)} />}
    >
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}><GlassLoader /></div>
      ) : !data?.expiries?.length ? (
        <GlassEmpty description="No calendar data" />
      ) : (
        <Table<CalendarRow & { key: string }>
          size="small"
          pagination={false}
          dataSource={data.expiries.map((r) => ({ ...r, key: r.expiry }))}
          columns={columns}
        />
      )}
    </Card>
  )
}
