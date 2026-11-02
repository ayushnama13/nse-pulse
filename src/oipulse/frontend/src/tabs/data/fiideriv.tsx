import { useState } from 'react'
import { Col, Row as ARow, Select, Space, Statistic } from 'antd'
import { EChart } from '@/charts/EChart'
import { DataTable, Q, Section } from '@/components/DataTable'
import { useFiiDeriv, useFiiDerivSummary, useVix } from '@/api/data'

export function FiiDerivTab() {
  const [days, setDays] = useState(120)
  const qSummary = useFiiDerivSummary()
  const qDeriv = useFiiDeriv(days)
  const qVix = useVix(days)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Space style={{ marginBottom: 8 }}>
        <Select
          value={days}
          onChange={setDays}
          options={[30, 120, 250].map((v) => ({ value: v, label: `${v} days` }))}
          style={{ width: 120 }}
        />
      </Space>

      <Section title="FII Derivatives Summary (Latest Session)">
        <Q q={qSummary}>
          {(summary: any[]) => {
            const totalNet = summary.reduce((acc, r) => acc + (r.net_value_cr || 0), 0)
            return (
              <>
                <ARow gutter={16} style={{ marginBottom: 12 }}>
                  <Col>
                    <Statistic
                      title="Total Net FII Derivatives (₹ Cr)"
                      value={totalNet}
                      precision={2}
                      valueStyle={{ color: totalNet >= 0 ? 'var(--bull, #26a69a)' : 'var(--bear, #ef5350)' }}
                    />
                  </Col>
                </ARow>
                <DataTable
                  rows={summary.map((r) => ({
                    ...r,
                    net_value_cr: Math.round((r.net_value_cr ?? 0) * 100) / 100,
                    net_5d_sum: Math.round((r.net_5d_sum ?? 0) * 100) / 100,
                  }))}
                />
              </>
            )
          }}
        </Q>
      </Section>

      <Section title="Daily Net Value by Instrument Group (₹ Cr)">
        <Q q={qDeriv}>
          {(derivRows: any[]) => {
            if (!derivRows || derivRows.length === 0) return <DataTable rows={[]} />
            const dates = [...new Set(derivRows.map((r: any) => String(r.date).slice(0, 10)))].sort()
            const instruments = [...new Set(derivRows.map((r: any) => r.instrument))]

            const getNet = (inst: string, dt: string) => {
              const row = derivRows.find((r: any) => r.instrument === inst && String(r.date).slice(0, 10) === dt)
              if (!row) return 0
              return (row.buy_value_cr || 0) - (row.sell_value_cr || 0)
            }

            const option = {
              tooltip: { trigger: 'axis' },
              legend: {},
              grid: { left: 56, right: 24, top: 40, bottom: 40 },
              xAxis: { type: 'category', data: dates },
              yAxis: { name: '₹ Cr' },
              series: instruments.map((inst) => ({
                name: inst,
                type: 'bar',
                data: dates.map((dt) => getNet(inst, dt)),
              })),
            }
            return <EChart option={option as any} height={320} />
          }}
        </Q>
      </Section>

      <Section title="India VIX Trend">
        <Q q={qVix}>
          {(vixRows: any[]) => {
            if (!vixRows || vixRows.length === 0) return <DataTable rows={[]} />
            const sorted = [...vixRows].reverse()
            const dates = sorted.map((r: any) => String(r.date).slice(0, 10))
            const closes = sorted.map((r: any) => r.close)
            const option = {
              tooltip: { trigger: 'axis' },
              grid: { left: 56, right: 24, top: 20, bottom: 40 },
              xAxis: { type: 'category', data: dates },
              yAxis: { scale: true },
              series: [{ type: 'line', data: closes, showSymbol: false, itemStyle: { color: '#f59e0b' } }],
            }
            return <EChart option={option as any} height={260} />
          }}
        </Q>
      </Section>
    </div>
  )
}
