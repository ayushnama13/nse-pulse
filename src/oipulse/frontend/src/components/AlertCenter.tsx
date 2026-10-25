import { useEffect, useRef, useState } from 'react'
import { App, Badge, Button, Popover, Switch, InputNumber, Space, Divider } from 'antd'
import { BellOutlined } from '@ant-design/icons'
import { useShell } from '@/store'
import { evalAlerts, DEFAULT_RULES, type AlertRule } from '@/lib/alerts'
import type { OptionChain } from '@/api/types'

const RULES_KEY = 'oipulse:alertRules'
const LABELS: Record<string, string> = {
  pcr_above: 'PCR crosses above',
  pcr_below: 'PCR crosses below',
  oi_spurt: 'OI spurt |ΔOI| >',
  spot_cross_maxpain: 'Spot crosses Max Pain',
}

function loadRules(): AlertRule[] {
  try {
    const raw = localStorage.getItem(RULES_KEY)
    return raw ? (JSON.parse(raw) as AlertRule[]) : DEFAULT_RULES
  } catch {
    return DEFAULT_RULES
  }
}

const EVENT_ICON: Record<string, string> = {
  'pcr-hi': '⤴', 'pcr-lo': '⤵', spurt: '⚡', maxpain: '✦',
}

export function AlertCenter() {
  const { notification } = App.useApp()
  const snap = useShell((s) => s.snap)
  const addEvent = useShell((s) => s.addEvent)
  const [rules, setRules] = useState<AlertRule[]>(loadRules)
  const [fired, setFired] = useState(0)
  const [canNotify, setCanNotify] = useState(typeof Notification !== 'undefined' && Notification.permission === 'granted')
  const prevRef = useRef<OptionChain | null>(null)

  useEffect(() => {
    try {
      localStorage.setItem(RULES_KEY, JSON.stringify(rules))
    } catch {
      /* ignore */
    }
  }, [rules])

  useEffect(() => {
    if (!snap) return
    const events = evalAlerts(rules, snap, prevRef.current)
    prevRef.current = snap
    for (const ev of events) {
      addEvent({ time: snap.time, icon: EVENT_ICON[ev.ruleId] ?? '•', level: ev.level, message: ev.message })
      notification.open({
        message: `${snap.symbol} alert`,
        description: ev.message,
        type: ev.level === 'warning' ? 'warning' : 'info',
        placement: 'bottomRight',
        duration: 6,
      })
      if (canNotify && typeof Notification !== 'undefined') {
        try {
          new Notification(`OI Pulse · ${snap.symbol}`, { body: ev.message })
        } catch {
          /* notification may throw on some browsers */
        }
      }
    }
    if (events.length) setFired((n) => n + events.length)
  }, [snap, rules, notification, canNotify, addEvent])

  const setRule = (id: string, patch: Partial<AlertRule>) => setRules((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)))

  const enableNotifications = async () => {
    if (typeof Notification === 'undefined') return
    const p = await Notification.requestPermission()
    setCanNotify(p === 'granted')
  }

  const content = (
    <div style={{ width: 300 }}>
      {rules.map((r) => (
        <div key={r.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
          <Switch size="small" checked={r.enabled} onChange={(v) => setRule(r.id, { enabled: v })} />
          <span style={{ flex: 1, fontSize: 12 }}>{LABELS[r.type]}</span>
          {r.type !== 'spot_cross_maxpain' && (
            <InputNumber
              size="small"
              value={r.threshold}
              onChange={(v) => setRule(r.id, { threshold: v ?? r.threshold })}
              style={{ width: 90 }}
              step={r.type === 'oi_spurt' ? 50000 : 0.1}
            />
          )}
        </div>
      ))}
      <Divider style={{ margin: '8px 0' }} />
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <span className="muted" style={{ fontSize: 11 }}>{fired} fired this session</span>
        {!canNotify && (
          <Button size="small" onClick={enableNotifications}>
            Enable push
          </Button>
        )}
      </Space>
    </div>
  )

  return (
    <Popover
      content={content}
      title={<span className="microlabel">Alert rules</span>}
      trigger="click"
      placement="bottomRight"
    >
      <Badge count={fired} size="small" overflowCount={9}>
        <Button icon={<BellOutlined />} />
      </Badge>
    </Popover>
  )
}
