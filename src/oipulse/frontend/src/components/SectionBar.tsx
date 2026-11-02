import { Select, Button, Tooltip } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { useShell } from '@/store'
import { MENUS, TAB_LABELS } from '@/nav'
import { SYMBOLS } from '@/api/types'
import { useForceSnapshot } from '@/api/queries'
import { AlertCenter } from './AlertCenter'

function getMenuAndLabel(tab: string) {
  for (const m of MENUS) {
    if (m.link === tab) return { menuLabel: m.label, pageLabel: TAB_LABELS[tab] || tab }
    if (m.items) {
      const it = m.items.find(i => i.key === tab)
      if (it) return { menuLabel: m.label, pageLabel: it.label }
    }
    if (m.groups) {
      for (const g of m.groups) {
        const it = g.items.find(i => i.key === tab)
        if (it) return { menuLabel: m.label, pageLabel: it.label }
      }
    }
  }
  return { menuLabel: 'Tools', pageLabel: TAB_LABELS[tab] || tab }
}

export function SectionBar() {
  const tab = useShell((s) => s.tab)
  const symbol = useShell((s) => s.symbol)
  const setSymbol = useShell((s) => s.setSymbol)
  const expiry = useShell((s) => s.expiry)
  const setExpiry = useShell((s) => s.setExpiry)
  const snap = useShell((s) => s.snap)
  const force = useForceSnapshot()

  if (tab === 'dashboard') return null

  const { menuLabel, pageLabel } = getMenuAndLabel(tab)
  const isOptionsPage = ['home', 'chain', 'pulse', 'multi', 'oi', 'vol', 'trends', 'analytics', 'macro', 'compare', 'calendar', 'payoff', 'eodchain'].includes(tab)
  const expiryOptions = (snap?.expiries ?? []).map((e) => ({ value: e, label: e }))

  return (
    <div className="border-b bg-background">
      <div className="mx-auto flex h-12 max-w-[1680px] items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{menuLabel} /</span>
          <span className="text-sm font-semibold tracking-tight text-foreground">{pageLabel}</span>
        </div>
        {isOptionsPage && (
          <div className="flex items-center gap-2">
            <Select value={symbol} onChange={setSymbol} options={SYMBOLS.map((s) => ({ value: s, label: s }))} style={{ width: 110 }} size="small" />
            <Select value={expiry} onChange={setExpiry} options={expiryOptions} placeholder="Expiry" style={{ width: 120 }} size="small" allowClear disabled={!expiryOptions.length} />
            <Tooltip title="Force snapshot (S)">
              <Button size="small" icon={<ThunderboltOutlined />} loading={force.isPending} onClick={() => force.mutate({ symbol, expiry })} />
            </Tooltip>
            <AlertCenter />
          </div>
        )}
      </div>
    </div>
  )
}

export { SectionBar as PageHeader }
