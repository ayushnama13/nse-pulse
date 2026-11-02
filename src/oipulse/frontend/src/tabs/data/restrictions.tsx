import { useState } from 'react'
import { Col, Row as ARow, Select, Space, Statistic } from 'antd'
import { EChart } from '@/charts/EChart'
import { DataTable, Q, Section } from '@/components/DataTable'
import { openTicker } from '@/lib/eq'
import { useFoBan, useFoBanHistory, usePriceBandChanges, usePriceBands, useShortSelling } from '@/api/data'

const tick = (s: string) => openTicker(s)

export function RestrictionsTab() {
  const [bandFilter, setBandFilter] = useState<number | undefined>(undefined)

  const qBanToday = useFoBan(undefined, 1)
  const qBanHistory = useFoBanHistory(30)
  const qBandChanges = usePriceBandChanges(30)
  const qPriceBands = usePriceBands(undefined, bandFilter)
  const qShortSelling = useShortSelling()

  return (
    <Q q={qBanToday}>
      {(banToday: any[]) => (
        <Q q={qBanHistory}>
          {(banHist: any[]) => (
            <Q q={qBandChanges}>
              {(bandChanges: any[]) => (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <Section title="Bans & Bands Summary">
                    <ARow gutter={16}>
                      <Col><Statistic title="F&O Ban Count Today" value={banToday.length} valueStyle={{ color: 'var(--bear, #ef5350)' }} /></Col>
                      <Col><Statistic title="Price Band Changes (30d)" value={bandChanges.length} /></Col>
                    </ARow>
                  </Section>

                  <ARow gutter={16}>
                    <Col xs={24} lg={12}>
                      <Section title="F&O Ban List Today">
                        <DataTable rows={banToday} link={{ symbol: tick }} />
                      </Section>
                      <Section title="Ban Count Trend (30d)">
                        {banHist && banHist.length > 0 ? (
                          <EChart
                            option={{
                              tooltip: { trigger: 'axis' },
                              grid: { left: 40, right: 24, top: 20, bottom: 40 },
                              xAxis: { type: 'category', data: banHist.map((h: any) => String(h.date).slice(0, 10)).reverse() },
                              yAxis: { type: 'value' },
                              series: [{ type: 'bar', data: banHist.map((h: any) => h.count).reverse(), itemStyle: { color: '#ef5350' } }],
                            }}
                            height={240}
                          />
                        ) : (
                          <DataTable rows={[]} />
                        )}
                      </Section>
                    </Col>
                    <Col xs={24} lg={12}>
                      <Section title="Price Band Changes (Last 30d)">
                        <DataTable rows={bandChanges} link={{ symbol: tick }} />
                      </Section>
                    </Col>
                  </ARow>

                  <Section title="Price Bands & Short Selling">
                    <Space style={{ marginBottom: 12 }}>
                      <Select
                        placeholder="Filter by Band %"
                        allowClear
                        style={{ width: 180 }}
                        value={bandFilter}
                        onChange={(v) => setBandFilter(v ?? undefined)}
                        options={[2, 5, 10, 20].map((v) => ({ value: v, label: `${v}% Band` }))}
                      />
                    </Space>
                    <ARow gutter={16}>
                      <Col xs={24} lg={12}>
                        <Section title="Price Bands">
                          <Q q={qPriceBands}>{(pb: any) => <DataTable rows={pb} link={{ symbol: tick }} pageSize={10} />}</Q>
                        </Section>
                      </Col>
                      <Col xs={24} lg={12}>
                        <Section title="Short Selling (Latest)">
                          <Q q={qShortSelling}>{(ss: any) => <DataTable rows={ss} link={{ symbol: tick }} pageSize={10} />}</Q>
                        </Section>
                      </Col>
                    </ARow>
                  </Section>
                </div>
              )}
            </Q>
          )}
        </Q>
      )}
    </Q>
  )
}
