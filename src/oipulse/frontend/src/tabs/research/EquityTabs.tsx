import { useState } from 'react'
import { Button, Col, Input, InputNumber, Row as ARow, Select, Space, Statistic, Tag, message } from 'antd'
import { EChart } from '@/charts/EChart'
import { DataTable, Q, Section } from '@/components/DataTable'
import { openTicker, useEq } from '@/lib/eq'
import {
  rDelete, rPost, useDataQuality, useDeals, useEodChain, useFiiDii, useIndices, useMarket, useNews,
  useRMutation, useSavedScreens, useTicker,
} from '@/api/research'

const tick = (s: string) => openTicker(s)

export function MarketTab() {
  const q = useMarket()
  return (
    <Q q={q}>
      {(d: any) =>
        !d.breadth ? (
          <DataTable rows={[]} />
        ) : (
          <>
            <Section title={`Market breadth — ${d.date}`}>
              <ARow gutter={16}>
                <Col><Statistic title="Advances" value={d.breadth.advances} valueStyle={{ color: 'var(--bull, #26a69a)' }} /></Col>
                <Col><Statistic title="Declines" value={d.breadth.declines} valueStyle={{ color: 'var(--bear, #ef5350)' }} /></Col>
                <Col><Statistic title="Unchanged" value={d.breadth.unchanged} /></Col>
                <Col><Statistic title="Total" value={d.breadth.total} /></Col>
              </ARow>
            </Section>
            <ARow gutter={12}>
              <Col xs={24} lg={12}><Section title="Top gainers"><DataTable rows={d.gainers} link={{ symbol: tick }} pageSize={10} /></Section></Col>
              <Col xs={24} lg={12}><Section title="Top losers"><DataTable rows={d.losers} link={{ symbol: tick }} pageSize={10} /></Section></Col>
            </ARow>
            <Section title="Volume leaders"><DataTable rows={d.volume} link={{ symbol: tick }} pageSize={10} /></Section>
            <Section title="Anomaly flags"><DataTable rows={d.anomalies} link={{ symbol: tick }} /></Section>
          </>
        )
      }
    </Q>
  )
}

export function TickerTab() {
  const sym = useEq((s) => s.symbol)
  const set = useEq((s) => s.set)
  const [input, setInput] = useState(sym)
  const [days, setDays] = useState(365)
  const q = useTicker(sym, days)
  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Input.Search value={input} onChange={(e) => setInput(e.target.value)} onSearch={(v) => set(v.trim())} enterButton="Load" style={{ width: 260 }} placeholder="Symbol e.g. RELIANCE" />
        <Select value={days} onChange={setDays} options={[90, 180, 365, 730, 1825].map((v) => ({ value: v, label: `${v}d` }))} />
      </Space>
      <Q q={q}>
        {(d: any) => {
          const dates = d.ohlc.map((r: any) => String(r.date).slice(0, 10))
          const option = {
            tooltip: { trigger: 'axis' }, grid: { left: 56, right: 24, top: 24, bottom: 56 },
            xAxis: { type: 'category', data: dates },
            yAxis: { scale: true },
            dataZoom: [{ type: 'inside' }, { type: 'slider' }],
            series: [{ type: 'candlestick', data: d.ohlc.map((r: any) => [r.open, r.close, r.low, r.high]) }],
          }
          return (
            <>
              <Section title={d.symbol}><EChart option={option as any} height={380} /></Section>
              <Section title="Features (latest 30)"><DataTable rows={d.features.slice(-30).reverse()} /></Section>
              <Section title="Corporate actions"><DataTable rows={d.corporate_actions} /></Section>
              <Section title="News"><DataTable rows={d.news} /></Section>
            </>
          )
        }}
      </Q>
    </>
  )
}

export function IndicesTab() {
  const [name, setName] = useState<string>()
  const [days, setDays] = useState(365)
  const q = useIndices(name, days)
  return (
    <Q q={q}>
      {(d: any) => {
        const dates = d.history.map((r: any) => String(r.date).slice(0, 10))
        const option = {
          tooltip: { trigger: 'axis' }, grid: { left: 56, right: 24, top: 24, bottom: 56 },
          xAxis: { type: 'category', data: dates }, yAxis: { scale: true },
          dataZoom: [{ type: 'inside' }, { type: 'slider' }],
          series: [{ type: 'line', showSymbol: false, data: d.history.map((r: any) => r.close) }],
        }
        return (
          <>
            <Space style={{ marginBottom: 12 }}>
              <Select showSearch placeholder="Choose index" value={name} onChange={setName} style={{ width: 260 }} options={d.indices.map((v: string) => ({ value: v, label: v }))} />
              <Select value={days} onChange={setDays} options={[90, 365, 1825].map((v) => ({ value: v, label: `${v}d` }))} />
            </Space>
            {name && <Section title={name}><EChart option={option as any} height={360} /></Section>}
            <Section title="Index features"><DataTable rows={d.features.slice(-60).reverse()} /></Section>
          </>
        )
      }}
    </Q>
  )
}

export function FiiDiiTab() {
  const [days, setDays] = useState(90)
  const q = useFiiDii(days)
  return (
    <>
      <Select value={days} onChange={setDays} style={{ marginBottom: 12 }} options={[30, 90, 365].map((v) => ({ value: v, label: `${v}d` }))} />
      <Q q={q}>
        {(d: any) => {
          const cols = d.daily.length ? Object.keys(d.daily[0]).filter((k) => /net/i.test(k)) : []
          const option = {
            tooltip: { trigger: 'axis' }, legend: {}, grid: { left: 56, right: 24, top: 36, bottom: 40 },
            xAxis: { type: 'category', data: d.daily.map((r: any) => String(r.date).slice(0, 10)) }, yAxis: {},
            series: cols.map((c) => ({ name: c, type: 'bar', data: d.daily.map((r: any) => r[c]) })),
          }
          return (
            <>
              {cols.length > 0 && <Section title="Net flows"><EChart option={option as any} height={320} /></Section>}
              <Section title="Daily"><DataTable rows={[...d.daily].reverse()} /></Section>
              <Section title="F&O participant OI"><DataTable rows={d.fo_participant_oi} /></Section>
            </>
          )
        }}
      </Q>
    </>
  )
}

export function DealsTab() {
  const [symbol, setSymbol] = useState<string>()
  const [days, setDays] = useState(30)
  const q = useDeals(symbol, days)
  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Input.Search allowClear placeholder="Symbol (optional)" onSearch={(v) => setSymbol(v.trim() || undefined)} style={{ width: 240 }} />
        <InputNumber min={1} max={1000} value={days} onChange={(v) => setDays(v ?? 30)} addonAfter="days" />
      </Space>
      <Q q={q}>{(d: any) => <DataTable rows={d.deals} link={{ symbol: tick }} />}</Q>
    </>
  )
}

export function NewsTab() {
  const [symbol, setSymbol] = useState<string>()
  const q = useNews(symbol)
  return (
    <>
      <Input.Search allowClear placeholder="Symbol (optional)" onSearch={(v) => setSymbol(v.trim() || undefined)} style={{ width: 240, marginBottom: 12 }} />
      <Q q={q}>{(d: any) => <DataTable rows={d.news} link={{ symbol: tick }} />}</Q>
    </>
  )
}

export function EodChainTab() {
  const [symbol, setSymbol] = useState('NIFTY')
  const q = useEodChain(symbol)
  return (
    <>
      <Input.Search defaultValue={symbol} onSearch={(v) => setSymbol(v.trim().toUpperCase())} enterButton="Load" style={{ width: 260, marginBottom: 12 }} />
      <Q q={q}>
        {(d: any) => (
          <>
            <Section title="Chain summary"><DataTable rows={d.summary} /></Section>
            <Section title="Chain"><DataTable rows={d.chain} pageSize={50} /></Section>
            <Section title="Option features"><DataTable rows={d.features} pageSize={50} /></Section>
          </>
        )}
      </Q>
    </>
  )
}

export function DataQualityTab() {
  const q = useDataQuality()
  return (
    <Q q={q}>
      {(d: any) => (
        <>
          <Section title="Table row counts">
            <DataTable rows={Object.entries(d.table_counts).map(([table, rows]) => ({ table, rows }))} pageSize={50} />
          </Section>
          <Section title="Recent scraper runs"><DataTable rows={d.scraper_runs} /></Section>
        </>
      )}
    </Q>
  )
}

export function ScreenerTab() {
  const [expr, setExpr] = useState('close > 100 and volume > 100000')
  const [name, setName] = useState('')
  const saved = useSavedScreens()
  const run = useRMutation((e: string) => rPost('/screener/run', { expression: e }))
  const save = useRMutation(() => rPost('/screener/saved', { name, expression: expr }))
  const del = useRMutation((n: string) => rDelete(`/screener/saved/${encodeURIComponent(n)}`))
  const res: any = run.data
  return (
    <>
      <Section title="Screener expression">
        <Input.TextArea rows={3} value={expr} onChange={(e) => setExpr(e.target.value)} style={{ fontFamily: 'monospace' }} />
        <Space style={{ marginTop: 8 }} wrap>
          <Button type="primary" loading={run.isPending} onClick={() => run.mutate(expr)}>Run</Button>
          <Input placeholder="Save as…" value={name} onChange={(e) => setName(e.target.value)} style={{ width: 180 }} />
          <Button disabled={!name} onClick={() => save.mutate(undefined, { onSuccess: () => message.success('Saved'), onError: (e) => message.error(String(e)) })}>Save</Button>
        </Space>
        {run.error && <div style={{ color: 'var(--bear, #ef5350)', marginTop: 8 }}>{String((run.error as Error).message)}</div>}
      </Section>
      {res && <Section title={`${res.count} matches`}><DataTable rows={res.rows} link={{ symbol: tick }} /></Section>}
      <Section title="Saved screens">
        <Q q={saved}>
          {(d: any) => (
            <Space direction="vertical" style={{ width: '100%' }}>
              {(d.screens ?? []).map((s: any) => (
                <Space key={s.name}>
                  <Tag color="gold" style={{ cursor: 'pointer' }} onClick={() => setExpr(s.expression)}>{s.name}</Tag>
                  <code>{s.expression}</code>
                  <a onClick={() => del.mutate(s.name)}>delete</a>
                </Space>
              ))}
              {(d.screens ?? []).length === 0 && <span style={{ opacity: 0.6 }}>None saved.</span>}
            </Space>
          )}
        </Q>
      </Section>
    </>
  )
}
