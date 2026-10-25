import { useEffect, useMemo, useState } from 'react'
import { Modal, Input } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useShell } from '@/store'
import { TAB_ORDER, type TabKey } from '@/router'
import { SYMBOLS } from '@/api/types'
import { useForceSnapshot } from '@/api/queries'

const TAB_LABELS: Record<TabKey, string> = {
  home: 'Home',
  chain: 'Option Chain', oi: 'OI & Gamma', vol: 'Vol & Skew', trends: 'Trends', analytics: 'Analytics',
  macro: 'Macro', multi: 'Multi-Index', compare: 'Compare', pulse: 'Pulse', calendar: 'Calendar', payoff: 'Payoff',
}

interface Cmd {
  id: string
  label: string
  hint: string
  run: () => void
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const setTab = useShell((s) => s.setTab)
  const setSymbol = useShell((s) => s.setSymbol)
  const toggleTheme = useShell((s) => s.toggleTheme)
  const toggleDensity = useShell((s) => s.toggleDensity)
  const symbol = useShell((s) => s.symbol)
  const expiry = useShell((s) => s.expiry)
  const force = useForceSnapshot()
  const snapNow = force.mutate // stable across renders (TanStack v5)
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)

  const commands = useMemo<Cmd[]>(() => {
    const tabs = TAB_ORDER.map((k) => ({ id: `tab:${k}`, label: `Go to ${TAB_LABELS[k]}`, hint: 'Tab', run: () => setTab(k) }))
    const syms = SYMBOLS.map((s) => ({ id: `sym:${s}`, label: `Switch to ${s}`, hint: 'Symbol', run: () => setSymbol(s) }))
    return [
      ...tabs,
      ...syms,
      { id: 'snap', label: 'Force snapshot', hint: 'Action', run: () => snapNow({ symbol, expiry }) },
      { id: 'theme', label: 'Toggle theme', hint: 'Action', run: toggleTheme },
      { id: 'density', label: 'Toggle density', hint: 'Action', run: toggleDensity },
    ]
  }, [setTab, setSymbol, toggleTheme, toggleDensity, snapNow, symbol, expiry])

  const filtered = useMemo(() => {
    const needle = q.toLowerCase().trim()
    if (!needle) return commands
    return commands.filter((c) => c.label.toLowerCase().includes(needle) || c.hint.toLowerCase().includes(needle))
  }, [q, commands])

  useEffect(() => {
    if (open) {
      setQ('')
      setActive(0)
    }
  }, [open])
  useEffect(() => setActive(0), [q])

  const exec = (c?: Cmd) => {
    if (!c) return
    c.run()
    onClose()
  }

  return (
    <Modal open={open} onCancel={onClose} footer={null} closable={false} width={520} styles={{ body: { padding: 0 } }} style={{ top: 90 }}>
      <Input
        autoFocus
        size="large"
        variant="borderless"
        prefix={<SearchOutlined style={{ color: 'var(--fg-4)', marginRight: 6 }} />}
        placeholder="Type a command…  (tabs, symbols, snapshot, theme)"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActive((a) => Math.min(a + 1, filtered.length - 1))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActive((a) => Math.max(a - 1, 0))
          } else if (e.key === 'Enter') {
            exec(filtered[active])
          }
        }}
        style={{ borderBottom: '1px solid var(--glass-edge)', borderRadius: 0, padding: '14px 16px' }}
      />
      <div style={{ maxHeight: 360, overflowY: 'auto', padding: 6 }}>
        {filtered.length === 0 && <div className="muted" style={{ padding: 16 }}>No matches</div>}
        {filtered.map((c, i) => (
          <div
            key={c.id}
            onMouseEnter={() => setActive(i)}
            onClick={() => exec(c)}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '9px 12px',
              borderRadius: 10,
              cursor: 'pointer',
              background: i === active ? 'var(--gold-tint)' : 'transparent',
              boxShadow: i === active ? 'inset 2px 0 0 var(--gold)' : 'none',
              color: i === active ? 'var(--fg)' : 'var(--fg-2)',
              transition: 'background var(--t-fast) var(--ease)',
            }}
          >
            <span>{c.label}</span>
            <span
              className="microlabel"
              style={{ background: 'rgba(255,255,255,0.05)', padding: '2px 9px', borderRadius: 999 }}
            >
              {c.hint}
            </span>
          </div>
        ))}
      </div>
      <div
        style={{
          display: 'flex',
          gap: 14,
          padding: '8px 14px',
          borderTop: '1px solid var(--glass-edge)',
          fontSize: 11,
          color: 'var(--fg-4)',
        }}
      >
        <span><kbd>↑</kbd> <kbd>↓</kbd> navigate</span>
        <span><kbd>↵</kbd> run</span>
        <span><kbd>esc</kbd> close</span>
      </div>
    </Modal>
  )
}
