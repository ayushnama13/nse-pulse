import { Card } from 'antd'
import { GlassLoader } from '@/components/Glass'
import { useShell } from '@/store'
import { useMulti, useCalendar } from '@/api/queries'
import { fmt, fmt2 } from '@/lib/format'
import { palette } from '@/theme'

/** Zone E — context: is this move index-specific or market-wide, and how does
 *  the expiry term look? Compact rows, each a door to its full tab. */
export function ContextRail() {
  const symbol = useShell((s) => s.symbol)
  const setTab = useShell((s) => s.setTab)
  const setSymbol = useShell((s) => s.setSymbol)
  const { data: multi, isLoading: mLoad } = useMulti('NIFTY,BANKNIFTY,FINNIFTY')
  const { data: cal, isLoading: cLoad } = useCalendar(symbol, 4)

  return (
    <>
      <Card
        size="small"
        title="Indices"
        extra={<a onClick={() => setTab('multi')} style={{ fontSize: 12 }}>All →</a>}
        styles={{ body: { padding: '6px 12px' } }}
      >
        {mLoad ? (
          <GlassLoader pad={8} />
        ) : (
          (multi?.results ?? []).map((r) => {
            const active = r.symbol === symbol
            const pcrColor = (r.pcr ?? 1) > 1.2 ? palette.bull : (r.pcr ?? 1) < 0.8 ? palette.bear : 'var(--fg-2)'
            return (
              <div
                key={r.symbol}
                onClick={() => setSymbol(r.symbol)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  padding: '6px 4px',
                  cursor: 'pointer',
                  borderBottom: '1px solid var(--line)',
                  background: active ? 'var(--gold-tint)' : undefined,
                  borderRadius: 6,
                }}
              >
                <span style={{ fontWeight: active ? 700 : 500, fontSize: 12.5, color: active ? palette.gold : 'var(--fg-2)' }}>{r.symbol}</span>
                <span className="mono" style={{ fontSize: 13 }}>{r.ok === false ? '—' : fmt2(r.spot)}</span>
                <span className="mono" style={{ fontSize: 11, color: pcrColor }}>PCR {r.ok === false ? '—' : fmt2(r.pcr)}</span>
              </div>
            )
          })
        )}
      </Card>

      <Card
        size="small"
        title="Expiry term"
        extra={<a onClick={() => setTab('calendar')} style={{ fontSize: 12 }}>Calendar →</a>}
        styles={{ body: { padding: '6px 12px' } }}
      >
        {cLoad ? (
          <GlassLoader pad={8} />
        ) : (
          (cal?.expiries ?? []).map((e) => (
            <div key={e.expiry} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 4px', borderBottom: '1px solid var(--line)', fontSize: 12 }}>
              <span className="mono" style={{ color: 'var(--fg-2)' }}>{e.expiry.slice(0, 6)}</span>
              <span className="mono muted">{Math.round(e.dte)}d</span>
              <span className="mono" style={{ color: palette.violet }}>IV {fmt2(e.atmIv)}</span>
              <span className="mono muted">MP {fmt(e.maxPain)}</span>
            </div>
          ))
        )}
      </Card>
    </>
  )
}
