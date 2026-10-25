import { Card, Space, Progress, Table, Alert } from 'antd'
import { GlassEmpty, GlassLoader } from '@/components/Glass'
import { useVix, useFiiDii, useParticipantOi } from '@/api/queries'
import { fmt2 } from '@/lib/format'
import { palette } from '@/theme'

// nse-library passthroughs vary in shape; read defensively like the legacy UI.
function pick(obj: unknown, keys: string[]): number {
  if (!obj || typeof obj !== 'object') return 0
  const o = obj as Record<string, unknown>
  for (const k of keys) {
    const v = o[k]
    if (typeof v === 'number') return v
    if (typeof v === 'string' && v.trim() && !Number.isNaN(Number(v))) return Number(v)
  }
  return 0
}

function VixCard() {
  const { data, isLoading } = useVix()
  if (isLoading) return <Card size="small" title="India VIX"><GlassLoader /></Card>
  const env = data as Record<string, unknown> | undefined
  if (env && env.available === false) return <Card size="small" title="India VIX"><Alert type="warning" message="VIX feed unavailable from NSE." showIcon /></Card>
  const vd = (env?.data ?? env) as Record<string, unknown> | undefined
  const v = pick(vd, ['last', 'lastValue', 'LTP', 'indexClose'])
  const chg = pick(vd, ['change', 'variation'])
  const pct = pick(vd, ['percentChange', 'pChange'])
  const hi = pick(vd, ['dayHigh', 'high'])
  const lo = pick(vd, ['dayLow', 'low'])
  const regime = v < 12 ? { t: 'Calm', c: palette.bull } : v > 20 ? { t: 'Fear', c: palette.bear } : { t: 'Normal', c: palette.gold }
  return (
    <Card size="small" title="India VIX">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <span className="mono" style={{ fontSize: 28, color: regime.c }}>{fmt2(v)}</span>
        <span className="mono" style={{ color: chg >= 0 ? palette.bear : palette.bull }}>
          {chg >= 0 ? '+' : ''}{fmt2(chg)} ({fmt2(pct)}%)
        </span>
        <span style={{ color: regime.c, fontWeight: 600 }}>{regime.t}</span>
      </div>
      <Progress percent={Math.min(100, (v / 30) * 100)} showInfo={false} strokeColor={regime.c} trailColor="var(--bg-3)" style={{ marginTop: 8 }} />
      <div className="muted" style={{ fontSize: 11, display: 'flex', justifyContent: 'space-between' }}>
        <span>Low {fmt2(lo)}</span>
        <span>0 — 30</span>
        <span>High {fmt2(hi)}</span>
      </div>
    </Card>
  )
}

function FiiDiiCard() {
  const { data, isLoading } = useFiiDii()
  if (isLoading) return <Card size="small" title="FII / DII Cash"><GlassLoader /></Card>
  const env = data as Record<string, unknown> | undefined
  if (env && env.available === false) return <Card size="small" title="FII / DII Cash"><Alert type="warning" message="FII/DII feed removed by NSE." showIcon /></Card>
  const arr = (env?.data ?? env) as unknown[] | undefined
  if (!Array.isArray(arr) || !arr.length) return <Card size="small" title="FII / DII Cash"><GlassEmpty description="No data" /></Card>
  const maxNet = Math.max(...arr.map((d) => Math.abs(pick(d, ['buyValue', 'buy']) - pick(d, ['sellValue', 'sell']))), 1)
  return (
    <Card size="small" title="FII / DII Cash Activity">
      <Space direction="vertical" style={{ width: '100%' }}>
        {arr.map((d, i) => {
          const cat = (d as Record<string, unknown>).category ?? (d as Record<string, unknown>).clientType ?? `Row ${i + 1}`
          const buy = pick(d, ['buyValue', 'buy'])
          const sell = pick(d, ['sellValue', 'sell'])
          const net = buy - sell
          return (
            <div key={i}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span>{String(cat)}</span>
                <span className="mono" style={{ color: net >= 0 ? palette.bull : palette.bear }}>{net >= 0 ? '+' : ''}{fmt2(net)}</span>
              </div>
              <Progress percent={(Math.abs(net) / maxNet) * 100} showInfo={false} strokeColor={net >= 0 ? palette.bull : palette.bear} trailColor="var(--bg-3)" size="small" />
            </div>
          )
        })}
      </Space>
    </Card>
  )
}

function ParticipantCard() {
  const { data, isLoading } = useParticipantOi()
  if (isLoading) return <Card size="small" title="Participant-Wise OI"><GlassLoader /></Card>
  const env = data as Record<string, unknown> | undefined
  if (env && env.available === false) return <Card size="small" title="Participant-Wise OI"><Alert type="warning" message="Participant OI feed removed by NSE." showIcon /></Card>
  const arr = (env?.data ?? env) as Record<string, unknown>[] | undefined
  if (!Array.isArray(arr) || !arr.length) return <Card size="small" title="Participant-Wise OI"><GlassEmpty description="No data" /></Card>
  const pretty = (k: string) =>
    k
      .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
      .replace(/[_-]+/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())
  const cols = Object.keys(arr[0]).slice(0, 8).map((k) => ({ title: pretty(k), dataIndex: k, className: 'mono' }))
  return (
    <Card size="small" title="Participant-Wise OI">
      <Table size="small" pagination={false} scroll={{ x: true }} dataSource={arr.map((r, i) => ({ key: i, ...r }))} columns={cols} />
    </Card>
  )
}

export function MacroTab() {
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px,1fr))', gap: 12 }}>
        <VixCard />
        <FiiDiiCard />
      </div>
      <ParticipantCard />
    </Space>
  )
}
