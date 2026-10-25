import { Card, Button, Space, Tag } from 'antd'
import { GlassEmpty, GlassLoader } from '@/components/Glass'
import { ReloadOutlined } from '@ant-design/icons'
import { useMulti } from '@/api/queries'
import { fmt, fmt2 } from '@/lib/format'
import { palette } from '@/theme'
import type { MultiResult } from '@/api/types'

const SYMS = 'NIFTY,BANKNIFTY,FINNIFTY'

function topOf(r: MultiResult, key: 'ceOI' | 'peOI'): number {
  let strike = 0
  let best = -1
  for (const row of r.chain ?? []) {
    if ((row[key] ?? 0) > best) {
      best = row[key] ?? 0
      strike = row.strike
    }
  }
  return strike
}

function MiniCard({ r }: { r: MultiResult }) {
  if (r.ok === false) {
    return (
      <Card size="small" title={r.symbol}>
        <GlassEmpty description={r.error || 'fetch failed'} />
      </Card>
    )
  }
  const rows: [string, string][] = [
    ['Spot', fmt2(r.spot)],
    ['Max Pain', fmt(r.maxPain)],
    ['OI PCR', fmt2(r.pcr)],
    ['Vol PCR', fmt2(r.volPcr)],
    ['ATM Straddle', fmt2(r.atmStraddle)],
    ['Top Resistance', fmt(topOf(r, 'ceOI'))],
    ['Top Support', fmt(topOf(r, 'peOI'))],
    ['γ Flip', r.gammaFlip ? fmt(r.gammaFlip) : '—'],
  ]
  return (
    <Card size="small" title={<Space><span style={{ color: palette.gold }}>{r.symbol}</span><Tag>{r.currentExpiry}</Tag></Space>}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {rows.map(([k, v]) => (
          <div key={k} style={{ background: 'var(--bg-1)', padding: '6px 10px', borderRadius: 6 }}>
            <div className="muted" style={{ fontSize: 10 }}>{k}</div>
            <div className="mono" style={{ fontSize: 15 }}>{v}</div>
          </div>
        ))}
      </div>
    </Card>
  )
}

export function MultiTab() {
  const { data, isLoading, refetch, isFetching } = useMulti(SYMS)
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button size="small" icon={<ReloadOutlined />} loading={isFetching} onClick={() => refetch()}>
          Refresh
        </Button>
      </div>
      {isLoading ? (
        <Card size="small"><GlassLoader /></Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px,1fr))', gap: 12 }}>
          {(data?.results ?? []).map((r) => (
            <MiniCard key={r.symbol} r={r} />
          ))}
        </div>
      )}
    </Space>
  )
}
