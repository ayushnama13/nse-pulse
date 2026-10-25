import { Select, Button, Tooltip } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { useShell } from '@/store'
import { SECTIONS, TAB_LABELS, sectionOf } from '@/nav'
import { SYMBOLS } from '@/api/types'
import { useForceSnapshot } from '@/api/queries'
import { AlertCenter } from './AlertCenter'
import { cn } from '@/lib/utils'

/** Tab strip for the active section, plus the symbol/expiry controls on Options. */
export function SectionBar() {
  const tab = useShell((s) => s.tab)
  const setTab = useShell((s) => s.setTab)
  const symbol = useShell((s) => s.symbol)
  const setSymbol = useShell((s) => s.setSymbol)
  const expiry = useShell((s) => s.expiry)
  const setExpiry = useShell((s) => s.setExpiry)
  const snap = useShell((s) => s.snap)
  const force = useForceSnapshot()
  const key = sectionOf(tab)
  const section = SECTIONS.find((s) => s.key === key)!
  const isOptions = key === 'options' || tab === 'compare' || tab === 'calendar' || tab === 'payoff'
  const expiryOptions = (snap?.expiries ?? []).map((e) => ({ value: e, label: e }))
  if (section.tabs.length < 2 && !isOptions) return null

  return (
    <div className="border-b bg-background">
      <div className="mx-auto flex max-w-[1680px] items-center gap-3 px-4">
        <div className="flex flex-1 gap-1 overflow-x-auto">
          {section.tabs.length > 1 &&
            section.tabs.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  'relative whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors',
                  tab === t ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {TAB_LABELS[t]}
                {tab === t && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded bg-foreground" />}
              </button>
            ))}
        </div>
        {isOptions && (
          <div className="flex items-center gap-2 py-1.5">
            <Select value={symbol} onChange={setSymbol} options={SYMBOLS.map((s) => ({ value: s, label: s }))} style={{ width: 120 }} size="small" />
            <Select value={expiry} onChange={setExpiry} options={expiryOptions} placeholder="Expiry" style={{ width: 130 }} size="small" allowClear disabled={!expiryOptions.length} />
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
