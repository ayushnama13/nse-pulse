import { useState } from 'react'
import { Col, Input, InputNumber, Row as ARow, Space, Statistic } from 'antd'
import { EChart } from '@/charts/EChart'
import { DataTable, Q, Section } from '@/components/DataTable'
import { openTicker } from '@/lib/eq'
import { useDeliveryLeaders, useDeliveryHistory } from '@/api/data'

const tick = (s: string) => openTicker(s)

export function DeliveryTab() {
  const [minVolume, setMinVolume] = useState<number | undefined>(100000)
  const [dateInput, setDateInput] = useState<string>('')
  const [selectedSymbol, setSelectedSymbol] = useState<string>('RELIANCE')

  const qLeaders = useDeliveryLeaders(dateInput || undefined, minVolume)
  const qHistory = useDeliveryHistory(selectedSymbol, 90)

  return (
    <Q q={qLeaders}>
      {(rows: any[]) => {
        if (!rows || rows.length === 0) {
          return (
            <div style={{ padding: 16 }}>
              <Space style={{ marginBottom: 16 }}>
                <Input placeholder="Date (YYYY-MM-DD)" value={dateInput} onChange={(e) => setDateInput(e.target.value)} style={{ width: 160 }} />
                <InputNumber placeholder="Min Volume" value={minVolume} onChange={(v) => setMinVolume(v ?? undefined)} style={{ width: 160 }} />
              </Space>
              <DataTable rows={[]} />
            </div>
          )
        }

        const topDel = rows[0]
        const maxDeliveryPct = topDel?.delivery_pct ?? 0
        const totalCount = rows.length
        const avgDeliveryPct = rows.reduce((acc, r) => acc + (r.delivery_pct || 0), 0) / (totalCount || 1)

        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Section title="Delivery Volume Leaders — Filters & Summary">
              <Space wrap style={{ marginBottom: 12 }}>
                <Input placeholder="Date (YYYY-MM-DD)" value={dateInput} onChange={(e) => setDateInput(e.target.value)} style={{ width: 160 }} allowClear />
                <InputNumber placeholder="Min Volume" value={minVolume} onChange={(v) => setMinVolume(v ?? undefined)} style={{ width: 160 }} />
              </Space>
              <ARow gutter={16}>
                <Col><Statistic title="Total Leaders" value={totalCount} /></Col>
                <Col><Statistic title="Top Delivery %" value={maxDeliveryPct} precision={2} suffix="%" valueStyle={{ color: 'var(--bull, #26a69a)' }} /></Col>
                <Col><Statistic title="Average Delivery %" value={avgDeliveryPct} precision={2} suffix="%" /></Col>
              </ARow>
            </Section>

            <Section title="Top Delivery % Leaders (Click row for 90d chart)">
              <DataTable
                rows={rows}
                link={{ symbol: tick }}
              />
            </Section>

            <Section title={`90-Day Delivery History: ${selectedSymbol}`}>
              <Q q={qHistory}>
                {(hist: any[]) => {
                  if (!hist || hist.length === 0) return <DataTable rows={[]} />
                  const dates = hist.map((r) => String(r.date).slice(0, 10))
                  const volumes = hist.map((r) => r.volume)
                  const deliveryPcts = hist.map((r) => r.delivery_pct)

                  const option = {
                    tooltip: { trigger: 'axis' },
                    grid: { left: 56, right: 56, top: 24, bottom: 56 },
                    xAxis: { type: 'category', data: dates },
                    yAxis: [
                      { type: 'value', name: 'Volume' },
                      { type: 'value', name: 'Delivery %', max: 100, min: 0 },
                    ],
                    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
                    series: [
                      { name: 'Volume', type: 'bar', yAxisIndex: 0, data: volumes, itemStyle: { color: 'rgba(34, 211, 238, 0.5)' } },
                      { name: 'Delivery %', type: 'line', yAxisIndex: 1, data: deliveryPcts, itemStyle: { color: '#a78bfa' }, showSymbol: false },
                    ],
                  }
                  return (
                    <>
                      <EChart option={option as any} height={320} />
                      <div style={{ marginTop: 12 }}>
                        <DataTable
                          rows={hist.map((h) => ({
                            ...h,
                            symbol: selectedSymbol,
                          }))}
                          link={{
                            symbol: (s) => setSelectedSymbol(s),
                          }}
                        />
                      </div>
                    </>
                  )
                }}
              </Q>
            </Section>
          </div>
        )
      }}
    </Q>
  )
}
