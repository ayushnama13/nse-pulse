import { Card } from 'antd'
import { GlassEmpty } from '@/components/Glass'
import { useShell } from '@/store'
import { palette } from '@/theme'

/** Zone D — "What changed": scannable history of alert-engine events and
 *  regime flips, newest first. Answers "what did I miss?" without toasts. */
export function ChangeFeed() {
  const events = useShell((s) => s.events)

  return (
    <Card size="small" title="What changed" styles={{ body: { padding: '4px 12px', maxHeight: 320, overflowY: 'auto' } }}>
      {events.length === 0 ? (
        <GlassEmpty description="Quiet so far — events land here (OI spurts, PCR crosses, regime flips)" style={{ padding: 12 }} />
      ) : (
        events.map((e) => (
          <div key={e.id} className="feed-row">
            <span className="mono" style={{ color: 'var(--fg-4)', fontSize: 11, flexShrink: 0 }}>{e.time}</span>
            <span style={{ flexShrink: 0, color: e.level === 'warning' ? palette.amber : palette.info }}>{e.icon}</span>
            <span style={{ color: 'var(--fg-2)' }}>{e.message}</span>
          </div>
        ))
      )}
    </Card>
  )
}
