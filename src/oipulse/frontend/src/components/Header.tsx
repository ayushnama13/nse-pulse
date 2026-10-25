import { useEffect, useState } from 'react'
import { Select, Button, Space, Tooltip } from 'antd'
import {
  ThunderboltOutlined,
  BulbOutlined,
  ColumnHeightOutlined,
} from '@ant-design/icons'
import { useShell } from '@/store'
import { SYMBOLS } from '@/api/types'
import { useForceSnapshot } from '@/api/queries'
import { AlertCenter } from './AlertCenter'
import { Logo } from './Glass'

function Clock() {
  const [t, setT] = useState('')
  useEffect(() => {
    const tick = () =>
      setT(
        new Date().toLocaleTimeString('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }) + ' IST',
      )
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])
  return <span className="mono" style={{ color: 'var(--fg-3)', fontSize: 12 }}>{t}</span>
}

/** The signature: a breathing cyan dot whose ring ripples outward once on
 *  every fresh snapshot (the ring element remounts via key on snap time). */
function LivePulse() {
  const live = useShell((s) => s.live)
  const t = useShell((s) => s.snap?.time)
  const word = { live: 'LIVE', stale: 'STALE', error: 'ERROR' }[live]
  return (
    <span className={`pulse ${live}`}>
      <span className="pulse-core" />
      {t && <span key={t} className="pulse-ring" />}
      <span className={`pulse-word ${live}`}>{word}</span>
    </span>
  )
}

export function Header() {
  const symbol = useShell((s) => s.symbol)
  const setSymbol = useShell((s) => s.setSymbol)
  const expiry = useShell((s) => s.expiry)
  const setExpiry = useShell((s) => s.setExpiry)
  const snap = useShell((s) => s.snap)
  const toggleTheme = useShell((s) => s.toggleTheme)
  const toggleDensity = useShell((s) => s.toggleDensity)
  const force = useForceSnapshot()

  const expiryOptions = (snap?.expiries ?? []).map((e) => ({ value: e, label: e }))

  return (
    <header className="app-header">
      <div className="header-brand">
        <Logo size={22} />
        <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: '-0.02em' }}>
          OI <span style={{ color: 'var(--gold)' }}>Pulse</span>
        </span>
      </div>

      <Select
        value={symbol}
        onChange={setSymbol}
        options={SYMBOLS.map((s) => ({ value: s, label: s }))}
        style={{ width: 132 }}
        size="middle"
        variant="filled"
      />
      <Select
        value={expiry}
        onChange={setExpiry}
        options={expiryOptions}
        placeholder="Expiry"
        style={{ width: 150 }}
        size="middle"
        variant="filled"
        allowClear
        disabled={!expiryOptions.length}
      />

      <LivePulse />

      <div style={{ flex: 1 }} />

      <Clock />
      <Space size={6}>
        <Tooltip title="Force snapshot (S)">
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={force.isPending}
            onClick={() => force.mutate({ symbol, expiry })}
          >
            Snap
          </Button>
        </Tooltip>
        <Tooltip title="Toggle theme">
          <Button icon={<BulbOutlined />} onClick={toggleTheme} />
        </Tooltip>
        <Tooltip title="Toggle density">
          <Button icon={<ColumnHeightOutlined />} onClick={toggleDensity} />
        </Tooltip>
        <AlertCenter />
      </Space>
    </header>
  )
}
