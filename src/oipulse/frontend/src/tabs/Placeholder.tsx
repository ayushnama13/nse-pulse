import { Card } from 'antd'
import { GlassEmpty } from '@/components/Glass'

/** Stand-in for tabs not yet ported (steps 5–9 of the migration). */
export function Placeholder({ name }: { name: string }) {
  return (
    <Card size="small">
      <GlassEmpty
        description={
          <span>
            <b style={{ color: 'var(--fg-2)' }}>{name}</b> — ported in a later migration step. Available now in the legacy UI at{' '}
            <code>/legacy</code>.
          </span>
        }
      />
    </Card>
  )
}
