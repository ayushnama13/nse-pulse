import { useMemo, useState } from 'react'
import { GlassEmpty } from '@/components/Glass'
import { Card } from 'antd'
import { useShell } from '@/store'
import { nearestATM, sliceAroundATM } from '@/lib/analytics'
import { fmt, fmt0, fmtSigned } from '@/lib/format'
import { palette } from '@/theme'

/**
 * Battle Map — the spatial picture of the position book around spot.
 * One SVG fuses: OI walls (bar length), today's ΔOI (bright edge segment),
 * spot (gold rule, interpolated), max-pain (violet ✦) and γ-flip (amber dash).
 * Click a row → pin the strike and jump to the chain.
 */

const ROW_H = 24
const W = 760
const CX = 380 // strike-label column center
const LABEL_HALF = 44 // half-width reserved for the strike label
const BAR_MAX = 250 // max bar length either side

interface RowGeom {
  strike: number
  y: number
  ceLen: number
  peLen: number
  ceChg: number
  peChg: number
  ceOI: number
  peOI: number
}

export function BattleMap() {
  const snap = useShell((s) => s.snap)
  const pinned = useShell((s) => s.pinned)
  const togglePin = useShell((s) => s.togglePin)
  const setTab = useShell((s) => s.setTab)
  const [hover, setHover] = useState<number | null>(null)

  const chain = useMemo(() => snap?.chain ?? [], [snap])
  const spot = snap?.spot ?? null
  const atm = useMemo(() => nearestATM(chain, spot), [chain, spot])

  const rows = useMemo<RowGeom[]>(() => {
    const slice = sliceAroundATM(chain, atm, 10).sort((a, b) => b.strike - a.strike) // high → low (ladder)
    const maxOI = Math.max(1, ...slice.map((r) => Math.max(r.ceOI, r.peOI)))
    return slice.map((r, i) => ({
      strike: r.strike,
      y: i * ROW_H + ROW_H / 2,
      ceLen: (r.ceOI / maxOI) * BAR_MAX,
      peLen: (r.peOI / maxOI) * BAR_MAX,
      ceChg: r.ceChg,
      peChg: r.peChg,
      ceOI: r.ceOI,
      peOI: r.peOI,
    }))
  }, [chain, atm])

  const H = rows.length * ROW_H + 8

  /** y for an arbitrary price, linearly interpolated between ladder rows. */
  const yFor = (price: number): number | null => {
    if (!rows.length) return null
    if (price >= rows[0].strike) return rows[0].y
    if (price <= rows[rows.length - 1].strike) return rows[rows.length - 1].y
    for (let i = 1; i < rows.length; i++) {
      const hi = rows[i - 1]
      const lo = rows[i]
      if (price <= hi.strike && price >= lo.strike) {
        const t = (hi.strike - price) / (hi.strike - lo.strike || 1)
        return hi.y + t * (lo.y - hi.y)
      }
    }
    return null
  }

  const spotY = spot != null ? yFor(spot) : null
  const flipY = snap?.gammaFlip != null ? yFor(snap.gammaFlip) : null
  const mpRow = rows.find((r) => r.strike === snap?.maxPain)

  // walls = top CE-OI and top PE-OI rows
  const ceWall = rows.reduce((b, r) => (r.ceOI > b.ceOI ? r : b), rows[0] ?? null)
  const peWall = rows.reduce((b, r) => (r.peOI > b.peOI ? r : b), rows[0] ?? null)

  if (!chain.length || !rows.length) {
    return (
      <Card size="small" title="Battle Map">
        <GlassEmpty description="Waiting for the option chain…" />
      </Card>
    )
  }

  const hoverRow = rows.find((r) => r.strike === hover)

  return (
    <Card
      size="small"
      title="Battle Map · OI walls around spot"
      extra={
        <span className="microlabel">
          <span style={{ color: palette.ce }}>■ CE</span>&nbsp;&nbsp;
          <span style={{ color: palette.pe }}>■ PE</span>&nbsp;&nbsp;
          <span style={{ color: palette.gold }}>— spot</span>&nbsp;&nbsp;
          <span style={{ color: palette.violet }}>✦ max pain</span>&nbsp;&nbsp;
          <span style={{ color: palette.amber }}>┄ γ-flip</span>
        </span>
      }
    >
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', display: 'block' }} role="img" aria-label="OI battle map">
        <defs>
          {/* glass depth: bars brighten toward the strike column */}
          <linearGradient id="bmap-ce" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor={palette.ce} stopOpacity="0.35" />
            <stop offset="1" stopColor={palette.ce} stopOpacity="0.95" />
          </linearGradient>
          <linearGradient id="bmap-pe" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor={palette.pe} stopOpacity="0.95" />
            <stop offset="1" stopColor={palette.pe} stopOpacity="0.35" />
          </linearGradient>
          <filter id="bmap-glow-bull" x="-60%" y="-60%" width="220%" height="220%">
            <feDropShadow dx="0" dy="0" stdDeviation="2.2" floodColor={palette.bull} floodOpacity="0.8" />
          </filter>
          <filter id="bmap-glow-bear" x="-60%" y="-60%" width="220%" height="220%">
            <feDropShadow dx="0" dy="0" stdDeviation="2.2" floodColor={palette.bear} floodOpacity="0.8" />
          </filter>
          <filter id="bmap-glow-spot" x="-40%" y="-300%" width="180%" height="700%">
            <feDropShadow dx="0" dy="0" stdDeviation="2.4" floodColor={palette.gold} floodOpacity="0.7" />
          </filter>
        </defs>
        {rows.map((r) => {
          const isATM = r.strike === atm
          const isPin = pinned.includes(r.strike)
          const ceX = CX - LABEL_HALF - r.ceLen
          const peX = CX + LABEL_HALF
          const chgCap = (chg: number, side: 'ce' | 'pe') => {
            if (Math.abs(chg) < 1) return null
            const capW = Math.min(28, 4 + (Math.abs(chg) / 100000) * 12)
            const x = side === 'ce' ? ceX : peX + r.peLen - capW
            return (
              <rect
                x={x}
                y={r.y - 7}
                width={capW}
                height={14}
                rx={3}
                fill={chg > 0 ? palette.bull : palette.bear}
                opacity={0.95}
                filter={chg > 0 ? 'url(#bmap-glow-bull)' : 'url(#bmap-glow-bear)'}
              />
            )
          }
          return (
            <g
              key={r.strike}
              className="bmap-row"
              onMouseEnter={() => setHover(r.strike)}
              onMouseLeave={() => setHover(null)}
              onClick={() => {
                togglePin(r.strike)
                setTab('chain')
              }}
            >
              <rect className="bmap-bg" x={0} y={r.y - ROW_H / 2} width={W} height={ROW_H} fill={isATM ? 'rgba(34,211,238,0.07)' : 'transparent'} />
              {/* CE wall bar (left) */}
              <rect x={ceX} y={r.y - 7} width={r.ceLen} height={14} rx={4} fill="url(#bmap-ce)" opacity={hover === r.strike ? 1 : 0.8} />
              {/* PE wall bar (right) */}
              <rect x={peX} y={r.y - 7} width={r.peLen} height={14} rx={4} fill="url(#bmap-pe)" opacity={hover === r.strike ? 1 : 0.8} />
              {/* ΔOI caps */}
              {chgCap(r.ceChg, 'ce')}
              {chgCap(r.peChg, 'pe')}
              {/* strike label */}
              <text
                x={CX}
                y={r.y + 4}
                textAnchor="middle"
                fontSize={12}
                fontFamily="'IBM Plex Mono', monospace"
                fontWeight={isATM || isPin ? 700 : 500}
                fill={isPin ? palette.violet : isATM ? palette.gold : 'var(--fg-3)'}
              >
                {fmt0(r.strike)}
              </text>
              {/* wall tags */}
              {ceWall && r.strike === ceWall.strike && (
                <text x={ceX - 6} y={r.y + 4} textAnchor="end" fontSize={9} fill={palette.ce} fontWeight={700} letterSpacing={1}>
                  WALL
                </text>
              )}
              {peWall && r.strike === peWall.strike && (
                <text x={peX + r.peLen + 6} y={r.y + 4} fontSize={9} fill={palette.pe} fontWeight={700} letterSpacing={1}>
                  WALL
                </text>
              )}
              {/* max pain marker */}
              {mpRow && r.strike === mpRow.strike && (
                <text x={CX + LABEL_HALF - 10} y={r.y - 9} fontSize={11} fill={palette.violet}>
                  ✦
                </text>
              )}
            </g>
          )
        })}

        {/* γ-flip dashed rule */}
        {flipY != null && (
          <g pointerEvents="none">
            <line x1={24} x2={W - 24} y1={flipY} y2={flipY} stroke={palette.amber} strokeWidth={1} strokeDasharray="5 4" opacity={0.9} />
            <text x={W - 26} y={flipY - 4} textAnchor="end" fontSize={9} fill={palette.amber} fontFamily="'IBM Plex Mono', monospace">
              γ-flip {fmt0(snap?.gammaFlip)}
            </text>
          </g>
        )}

        {/* spot rule */}
        {spotY != null && (
          <g pointerEvents="none">
            <line x1={12} x2={W - 12} y1={spotY} y2={spotY} stroke={palette.gold} strokeWidth={1.6} filter="url(#bmap-glow-spot)" />
            <circle cx={12} cy={spotY} r={3} fill={palette.gold} />
            <text x={16} y={spotY - 5} fontSize={10} fill={palette.gold} fontFamily="'IBM Plex Mono', monospace" fontWeight={600}>
              SPOT {fmt2num(spot)}
            </text>
          </g>
        )}
      </svg>

      <div className="microlabel" style={{ marginTop: 6, minHeight: 16 }}>
        {hoverRow
          ? `${fmt0(hoverRow.strike)} · CE ${fmt(hoverRow.ceOI)} (${fmtSigned(hoverRow.ceChg)}) · PE ${fmt(hoverRow.peOI)} (${fmtSigned(hoverRow.peChg)}) · click to pin + open chain`
          : 'bar length = OI · colored cap = today’s ΔOI (teal add / red unwind) · hover a strike'}
      </div>
    </Card>
  )
}

function fmt2num(n: number | null): string {
  return n == null ? '—' : n.toFixed(2)
}
