import { useState } from 'react'
import { Button, Col, Input, InputNumber, Row as ARow, Select, Space, Statistic, Tag, Upload, message } from 'antd'
import { DataTable, Q, Section } from '@/components/DataTable'
import { openTicker } from '@/lib/eq'
import { rDelete, rPost, rUpload, useAlerts, usePortfolio, useRMutation, useWatchlists } from '@/api/research'

export function PortfolioTab() {
  const q = usePortfolio()
  const imp = useRMutation((f: File) => rUpload('/portfolio/import', f))
  return (
    <>
      <Upload accept=".csv" showUploadList={false}
        beforeUpload={(f) => { imp.mutate(f, { onSuccess: (r: any) => message.success(`Imported ${r.imported} rows`), onError: (e) => message.error(String(e)) }); return false }}>
        <Button loading={imp.isPending} style={{ marginBottom: 12 }}>Import broker CSV</Button>
      </Upload>
      <Q q={q}>
        {(d: any) => (
          <>
            <Section title="Summary">
              <ARow gutter={16}>
                <Col><Statistic title="Realized P&L" value={d.realized_pnl ?? 0} precision={2} /></Col>
                <Col><Statistic title="Unrealized P&L" value={d.unrealized_pnl ?? 0} precision={2} /></Col>
                <Col><Statistic title="XIRR" value={d.xirr != null ? d.xirr * 100 : undefined} suffix="%" precision={2} /></Col>
              </ARow>
            </Section>
            <Section title="Holdings"><DataTable rows={d.holdings} link={{ symbol: openTicker }} /></Section>
            <Section title="Sector exposure"><DataTable rows={d.sector_exposure} /></Section>
          </>
        )}
      </Q>
    </>
  )
}

export function AlertsTab() {
  const q = useAlerts()
  const [name, setName] = useState('')
  const [type, setType] = useState<string>()
  const [payload, setPayload] = useState('{}')
  const [cool, setCool] = useState(60)
  const add = useRMutation(() => rPost('/alerts', { name, trigger_type: type, payload: JSON.parse(payload), cooldown_minutes: cool }))
  const del = useRMutation((n: string) => rDelete(`/alerts/${encodeURIComponent(n)}`))
  const run = useRMutation(() => rPost('/alerts/run'))
  return (
    <Q q={q}>
      {(d: any) => (
        <>
          <Section title="New rule">
            <Space wrap>
              <Input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} style={{ width: 160 }} />
              <Select placeholder="Trigger type" value={type} onChange={setType} style={{ width: 200 }} options={d.trigger_types.map((t: string) => ({ value: t, label: t }))} />
              <Input placeholder='Payload JSON' value={payload} onChange={(e) => setPayload(e.target.value)} style={{ width: 300, fontFamily: 'monospace' }} />
              <InputNumber min={1} value={cool} onChange={(v) => setCool(v ?? 60)} addonAfter="min cooldown" />
              <Button type="primary" disabled={!name || !type}
                onClick={() => add.mutate(undefined, { onSuccess: () => message.success('Added'), onError: (e) => message.error(String(e)) })}>Add</Button>
              <Button loading={run.isPending} onClick={() => run.mutate(undefined, { onSuccess: (r: any) => message.info(`Fired: ${JSON.stringify(r.fired)}`) })}>Run now</Button>
            </Space>
          </Section>
          <Section title="Rules">
            <DataTable rows={d.rules} />
            <Space wrap style={{ marginTop: 8 }}>
              {(d.rules ?? []).map((r: any) => <Tag key={r.name} closable onClose={() => del.mutate(r.name)}>{r.name}</Tag>)}
            </Space>
          </Section>
        </>
      )}
    </Q>
  )
}

export function WatchlistsTab() {
  const q = useWatchlists()
  const [name, setName] = useState('default')
  const [sym, setSym] = useState('')
  const add = useRMutation((_?: void) => rPost('/watchlists', { name, symbol: sym }))
  const del = useRMutation((v: { n: string; s: string }) => rDelete(`/watchlists/${encodeURIComponent(v.n)}/${encodeURIComponent(v.s)}`))
  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Input value={name} onChange={(e) => setName(e.target.value)} style={{ width: 160 }} placeholder="Watchlist" />
        <Input value={sym} onChange={(e) => setSym(e.target.value)} style={{ width: 160 }} placeholder="Symbol" onPressEnter={() => { add.mutate(undefined); setSym('') }} />
        <Button type="primary" disabled={!sym} onClick={() => { add.mutate(undefined); setSym('') }}>Add</Button>
      </Space>
      <Q q={q}>
        {(d: any) => Object.entries<string[]>(d.watchlists).map(([n, syms]) => (
          <Section key={n} title={n}>
            <Space wrap>
              {syms.map((s) => <Tag key={s} closable onClose={() => del.mutate({ n, s })}><a onClick={() => openTicker(s)}>{s}</a></Tag>)}
            </Space>
          </Section>
        ))}
      </Q>
    </>
  )
}
