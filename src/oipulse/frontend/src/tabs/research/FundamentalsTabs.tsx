import { useState, type ReactNode } from 'react'
import { Button, Descriptions, Input, InputNumber, Select, Space, Tag } from 'antd'
import { EChart } from '@/charts/EChart'
import { DataTable, Q, Section, cell } from '@/components/DataTable'
import { openCompany, useEq } from '@/lib/eq'
import { fSql, useFund, type Row } from '@/api/research'

const co = (s: string) => openCompany(s)
const isRows = (v: any): v is Row[] => Array.isArray(v) && v.length > 0 && typeof v[0] === 'object' && v[0] !== null
const isDict = (v: any): v is Row => v && typeof v === 'object' && !Array.isArray(v)

/** Render any JSON value: arrays of objects → table, dicts → descriptions, scalars → text. */
function Auto({ v }: { v: any }): ReactNode {
  if (isRows(v)) return <DataTable rows={v} link={{ symbol: co }} />
  if (isDict(v)) {
    return (
      <Descriptions size="small" bordered column={{ xs: 1, md: 2, xl: 3 }}>
        {Object.entries(v).filter(([, x]) => !isDict(x) && !Array.isArray(x)).map(([k, x]) => <Descriptions.Item key={k} label={k}>{cell(x)}</Descriptions.Item>)}
      </Descriptions>
    )
  }
  return <>{cell(v)}</>
}

function lineChart(x: string[], series: Record<string, (number | null)[]>, bar = false) {
  return {
    tooltip: { trigger: 'axis' }, legend: {}, grid: { left: 56, right: 24, top: 36, bottom: 40 },
    xAxis: { type: 'category', data: x }, yAxis: { scale: true },
    series: Object.entries(series).map(([name, data]) => ({ name, data, type: bar ? 'bar' : 'line', showSymbol: false })),
  } as any
}

export function FDashTab() {
  const q = useFund('/')
  return (
    <Q q={q}>
      {(d: any) => (
        <>
          <Section title="Counts"><Auto v={d.counts} /></Section>
          <Section title="Top by market cap"><Auto v={d.top_mcap} /></Section>
          <Section title="Top scored"><Auto v={d.top_scored} /></Section>
          <Section title="Sectors"><Auto v={d.sectors} /></Section>
          <Section title="Last scraper runs"><Auto v={d.last_runs} /></Section>
        </>
      )}
    </Q>
  )
}

export function FCompaniesTab() {
  const [text, setText] = useState('')
  const [sector, setSector] = useState('')
  const [page, setPage] = useState(1)
  const q = useFund('/companies', { q: text, sector, page })
  return (
    <>
      <Space style={{ marginBottom: 12 }} wrap>
        <Input.Search allowClear placeholder="Symbol / name" onSearch={(v) => { setText(v); setPage(1) }} style={{ width: 240 }} />
        <Q q={q}>
          {(d: any) => (
            <Select allowClear showSearch placeholder="Sector" style={{ width: 240 }} value={sector || undefined}
              onChange={(v) => { setSector(v ?? ''); setPage(1) }}
              options={(d.sectors ?? []).map((s: any) => { const v = typeof s === 'string' ? s : s.sector; return { value: v, label: v } })} />
          )}
        </Q>
      </Space>
      <Q q={q}>
        {(d: any) => (
          <>
            <DataTable rows={d.rows} link={{ symbol: co }} pageSize={100} />
            <Space style={{ marginTop: 8 }}>
              <Button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
              <span>Page {d.page} / {d.pages} · {d.total} companies</span>
              <Button disabled={page >= d.pages} onClick={() => setPage(page + 1)}>Next</Button>
            </Space>
          </>
        )}
      </Q>
    </>
  )
}

export function FCompanyTab() {
  const sym = useEq((s) => s.symbol)
  const set = useEq((s) => s.set)
  const q = useFund(`/company/${encodeURIComponent(sym)}`)
  return (
    <>
      <Input.Search defaultValue={sym} enterButton="Load" onSearch={(v) => set(v.trim())} style={{ width: 260, marginBottom: 12 }} />
      <Q q={q}>
        {(d: any) => {
          const pc = d.price_chart, rc = d.rev_chart, ra = d.ratio_chart, sh = d.sh_chart
          return (
            <>
              <Section title={d.company?.name ?? sym} extra={d.score?.composite_score != null && <Tag color="gold">score {cell(d.score.composite_score)}</Tag>}>
                <Auto v={d.company} />
              </Section>
              {d.flags && <Section title="Risk flags"><Auto v={d.flag_details ?? d.flags} /></Section>}
              {pc && <Section title="Price"><EChart height={320} option={{ ...lineChart(pc.dates, { Close: pc.close }), dataZoom: [{ type: 'inside' }] }} /></Section>}
              {rc && <Section title="Revenue & PAT (₹ Cr)"><EChart height={280} option={lineChart(rc.years, { Revenue: rc.revenue_cr, PAT: rc.pat_cr }, true)} /></Section>}
              {ra && <Section title="ROE / ROCE / D-E"><EChart height={280} option={lineChart(ra.years, { ROE: ra.roe, ROCE: ra.roce, 'D/E': ra.de })} /></Section>}
              {sh && <Section title="Shareholding %"><EChart height={280} option={lineChart(sh.quarters, { Promoter: sh.promoter, FII: sh.fii, DII: sh.dii })} /></Section>}
              {(['val', 'tech', 'score'] as const).map((k) => d[k] && <Section key={k} title={k === 'val' ? 'Valuation' : k === 'tech' ? 'Technicals' : 'Scores'}><Auto v={d[k]} /></Section>)}
              {([['fin_annual', 'Annual financials'], ['fin_qtr', 'Quarterly'], ['bs', 'Balance sheet'], ['cf', 'Cash flow'], ['ratios', 'Ratios'], ['growth', 'Growth'], ['sh', 'Shareholding'], ['peers', 'Peers']] as const)
                .map(([k, t]) => isRows(d[k]) && <Section key={k} title={t}><DataTable rows={d[k]} link={{ symbol: co }} /></Section>)}
            </>
          )
        }}
      </Q>
    </>
  )
}

export function FSectorsTab() {
  const [name, setName] = useState<string>()
  const list = useFund('/sectors')
  const one = useFund(`/sector/${encodeURIComponent(name ?? '')}`, undefined, !!name)
  return (
    <>
      <Q q={list}>{(d: any) => <DataTable rows={d.rows} link={{ sector: setName }} />}</Q>
      {name && (
        <Section title={name}>
          <Q q={one}>{(d: any) => (<><Auto v={d.stats} /><div style={{ height: 8 }} /><DataTable rows={d.rows} link={{ symbol: co }} /></>)}</Q>
        </Section>
      )}
    </>
  )
}

export function FTopTab() {
  const [limit, setLimit] = useState(100)
  const [mcap, setMcap] = useState(0)
  const q = useFund('/top', { limit, min_mcap: mcap })
  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <InputNumber min={10} max={1000} value={limit} onChange={(v) => setLimit(v ?? 100)} addonBefore="Top" />
        <InputNumber min={0} value={mcap} onChange={(v) => setMcap(v ?? 0)} addonBefore="Min mcap ₹Cr" />
      </Space>
      <Q q={q}>{(d: any) => <DataTable rows={d.rows} link={{ symbol: co }} pageSize={50} />}</Q>
    </>
  )
}

export function FScreensTab() {
  const idx = useFund('/screens')
  const [name, setName] = useState<string>()
  const [vals, setVals] = useState<Record<string, number>>({})
  const spec = idx.data?.screens?.find((s: any) => s.key === name)
  const params = Object.fromEntries(Object.entries(vals).map(([k, v]) => [k, v]))
  const run = useFund(`/screens/${name}`, params, !!name)
  return (
    <>
      <Q q={idx}>
        {(d: any) => (
          <Space wrap style={{ marginBottom: 12 }}>
            {d.screens.map((s: any) => (
              <Button key={s.key} type={name === s.key ? 'primary' : 'default'} title={s.desc} onClick={() => { setName(s.key); setVals({}) }}>{s.title}</Button>
            ))}
          </Space>
        )}
      </Q>
      {spec && (
        <Space wrap style={{ marginBottom: 12 }}>
          {spec.params.map((p: any) => (
            <InputNumber key={p.name} addonBefore={p.label} step={Number(p.step)} defaultValue={p.default}
              onChange={(v) => v != null && setVals((o) => ({ ...o, [p.name]: v }))} />
          ))}
        </Space>
      )}
      {name && <Q q={run}>{(d: any) => <Section title={`${d.n} results`}><DataTable rows={d.rows} link={{ symbol: co }} /></Section>}</Q>}
    </>
  )
}

export function FSqlTab() {
  const [sql, setSql] = useState('SELECT symbol, name, sector FROM companies LIMIT 20')
  const [res, setRes] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const samples = useFund('/sql')
  const run = async () => { setBusy(true); try { setRes(await fSql(sql)) } finally { setBusy(false) } }
  return (
    <>
      <Section title="Read-only SQL">
        <Input.TextArea rows={5} value={sql} onChange={(e) => setSql(e.target.value)} style={{ fontFamily: 'monospace' }} />
        <Space style={{ marginTop: 8 }} wrap>
          <Button type="primary" loading={busy} onClick={run}>Run</Button>
          {isRows(samples.data?.samples) || Array.isArray(samples.data?.samples)
            ? (samples.data.samples as any[]).map((s, i) => { const q = typeof s === 'string' ? s : s.sql; const t = typeof s === 'string' ? `sample ${i + 1}` : (s.title ?? s.name ?? `sample ${i + 1}`); return <Tag key={i} style={{ cursor: 'pointer' }} onClick={() => setSql(q)}>{t}</Tag> })
            : null}
        </Space>
        {res?.error && <div style={{ color: 'var(--bear, #ef5350)', marginTop: 8 }}>{res.error}</div>}
      </Section>
      {res?.rows && <DataTable rows={res.rows} columns={res.columns} pageSize={50} />}
    </>
  )
}

export function FHealthTab() {
  const q = useFund('/admin/health')
  const src = useFund('/sources')
  return (
    <>
      <Q q={q}>
        {(d: any) => (
          <>
            {(['src_health', 'table_counts', 'dq_summary', 'recent_errors', 'snapshot_info', 'score_info'] as const).map((k) => (
              d[k] != null && <Section key={k} title={k.replace(/_/g, ' ')}><Auto v={d[k]} /></Section>
            ))}
          </>
        )}
      </Q>
      <Q q={src}>
        {(d: any) => (
          <>
            {(['last_runs', 'recent', 'dq', 'dq_recent'] as const).map((k) => (
              d[k] != null && <Section key={k} title={`sources · ${k.replace(/_/g, ' ')}`}><Auto v={d[k]} /></Section>
            ))}
          </>
        )}
      </Q>
    </>
  )
}
