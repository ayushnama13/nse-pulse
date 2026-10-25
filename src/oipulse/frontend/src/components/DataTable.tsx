import { useMemo, type ReactNode } from 'react'
import { Alert, Card, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { GlassEmpty, GlassLoader } from './Glass'
import type { Row } from '@/api/research'

const NUM = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })

export function cell(v: any): ReactNode {
  if (v === null || v === undefined) return <span style={{ opacity: 0.4 }}>—</span>
  if (typeof v === 'number') return NUM.format(v)
  if (typeof v === 'boolean') return v ? 'yes' : 'no'
  if (typeof v === 'object') return JSON.stringify(v)
  const s = String(v)
  return /^\d{4}-\d{2}-\d{2}T00:00:00/.test(s) ? s.slice(0, 10) : s
}

/** Generic table over array-of-objects. `link` columns render as clickable. */
export function DataTable({
  rows, columns, link, pageSize = 25, size = 'small',
}: {
  rows: Row[] | undefined | null
  columns?: string[]
  link?: Record<string, (v: string, row: Row) => void>
  pageSize?: number
  size?: 'small' | 'middle'
}) {
  const cols = useMemo<ColumnsType<Row>>(() => {
    const keys = columns ?? (rows && rows.length ? Object.keys(rows[0]) : [])
    return keys.map((k) => ({
      title: k, dataIndex: k, key: k, ellipsis: true,
      sorter: (a: Row, b: Row) => (typeof a[k] === 'number' && typeof b[k] === 'number' ? a[k] - b[k] : String(a[k] ?? '').localeCompare(String(b[k] ?? ''))),
      render: (v: any, row: Row) =>
        link?.[k] && v != null ? <a onClick={() => link[k](String(v), row)}>{String(v)}</a> : cell(v),
    }))
  }, [rows, columns, link])
  if (!rows || rows.length === 0) return <GlassEmpty description="No data yet — run an EOD ingest to populate." />
  return (
    <Table size={size} columns={cols} dataSource={rows} rowKey={(_, i) => String(i)} scroll={{ x: 'max-content' }}
      pagination={rows.length > pageSize ? { pageSize, showSizeChanger: false } : false} />
  )
}

/** Wrap a query result: loader / error / content. */
export function Q<T>({ q, children }: { q: { data?: T; isLoading: boolean; error: unknown }; children: (d: T) => ReactNode }) {
  if (q.isLoading) return <GlassLoader pad={48} />
  if (q.error) return <Alert type="error" showIcon message={String((q.error as Error).message ?? q.error)} />
  if (q.data === undefined) return null
  return <>{children(q.data)}</>
}

export function Section({ title, extra, children }: { title: ReactNode; extra?: ReactNode; children: ReactNode }) {
  return <Card size="small" title={title} extra={extra} style={{ marginBottom: 12 }}>{children}</Card>
}
