import { useEffect, useRef, useState } from 'react'
import { Tooltip, Progress } from 'antd'
import { useShell } from '@/store'
import { useVix } from '@/api/queries'
import { fmt2 } from '@/lib/format'
import { Sparkline } from '@/components/Sparkline'
import { palette } from '@/theme'

const CLS_COLOR: Record<string, string> = {
  bull: palette.bull,
  bear: palette.bear,
  neutral: palette.violet,
  warn: palette.amber,
}

function pickNum(obj: unknown, keys: string[]): number | null {
  if (!obj || typeof obj !== 'object') return null
  const o = obj as Record<string, unknown>
  for (const k of keys) {
    const v = o[k]
    if (typeof v === 'number') return v
    if (typeof v === 'string' && v.trim() && !Number.isNaN(Number(v))) return Number(v)
  }
  return null
}

/** Zone A — the verdict: regime + auditable conviction, spot, PCR cluster, VIX. */
export function VerdictBar() {
  const snap = useShell((s) => s.snap)
  const regime = useShell((s) => s.regime)
  const wpcr = useShell((s) => s.wpcr)
  const spotHist = useShell((s) => s.spotHist)
  const { data: vixEnv } = useVix()

  // single 600ms pulse on regime flip — motion only on change
  const [flip, setFlip] = useState(false)
  const prevRegime = useRef<string | null>(null)
  useEffect(() => {
    if (regime && prevRegime.current && prevRegime.current !== regime.regime) {
      setFlip(true)
      const t = setTimeout(() => setFlip(false), 700)
      return () => clearTimeout(t)
    }
    prevRegime.current = regime?.regime ?? null
  }, [regime])

  const env = vixEnv as Record<string, unknown> | undefined
  const vix = env && env.available !== false ? pickNum(env.data ?? env, ['last', 'lastValue', 'LTP', 'indexClose']) : null
  const vixColor = vix == null ? palette.fg4 : vix < 12 ? palette.bull : vix > 20 ? palette.bear : palette.gold

  const color = CLS_COLOR[regime?.cls ?? 'neutral']
  const conviction = regime ? Math.max(regime.bulls, regime.bears) : 0
  const spotDelta =
    spotHist.length >= 2 ? (snap?.spot ?? 0) - spotHist[spotHist.length - 2].v : 0
  const spotPct = snap?.spot ? (spotDelta / snap.spot) * 100 : 0

  const pcrCell = (label: string, v: number | undefined | null) => {
    const c = v == null ? palette.fg4 : v > 1.2 ? palette.bull : v < 0.8 ? palette.bear : 'var(--fg)'
    return (
      <div key={label} style={{ textAlign: 'center' }}>
        <div className="microlabel">{label}</div>
        <div className="mono" style={{ fontSize: 18, color: c }}>{fmt2(v)}</div>
      </div>
    )
  }

  const votesTip = regime ? (
    <div style={{ minWidth: 220 }}>
      {regime.votes.map((v) => (
        <div key={v.label} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12, padding: '2px 0' }}>
          <span>
            {v.dir === 'bull' ? '✓' : v.dir === 'bear' ? '✗' : '·'} {v.label}
          </span>
          <span className="mono" style={{ color: v.dir === 'bull' ? palette.bull : v.dir === 'bear' ? palette.bear : palette.fg4 }}>
            {v.detail}
          </span>
        </div>
      ))}
    </div>
  ) : null

  return (
    <div className="verdict-bar">
      <Tooltip title={votesTip} placement="bottomLeft">
        <div style={{ cursor: 'help' }}>
          <div className="microlabel">Regime · {regime ? `${regime.bulls}↑ ${regime.bears}↓` : '—'}</div>
          <div style={{ fontSize: 20, fontWeight: 700, color, whiteSpace: 'nowrap' }}>
            <span className={`verdict-dot${flip ? ' flip' : ''}`} style={{ background: color, color }} />
            {regime?.regime ?? 'Waiting…'}
          </div>
          <div className="conviction" aria-label={`conviction ${conviction} of 5`}>
            {[0, 1, 2, 3, 4].map((i) => (
              <span key={i} style={i < conviction ? { background: color } : undefined} />
            ))}
          </div>
        </div>
      </Tooltip>

      <div>
        <div className="microlabel">{snap?.symbol ?? ''} Spot</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span key={snap?.time} className="mono tick-flash" style={{ fontSize: 28, fontWeight: 600, color: palette.gold }}>
            {fmt2(snap?.spot)}
          </span>
          <span className="mono" style={{ fontSize: 13, color: spotDelta >= 0 ? palette.bull : palette.bear }}>
            {spotDelta >= 0 ? '+' : ''}
            {fmt2(spotDelta)} ({spotPct >= 0 ? '+' : ''}
            {spotPct.toFixed(2)}%)
          </span>
        </div>
        {spotHist.length > 1 && <Sparkline data={spotHist} color={palette.gold} width={140} height={20} />}
      </div>

      <div style={{ display: 'flex', gap: 26, justifyContent: 'center' }}>
        {pcrCell('OI PCR', snap?.pcr)}
        {pcrCell('Vol PCR', snap?.volPcr)}
        {pcrCell('WPCR ₹', wpcr)}
      </div>

      <div style={{ textAlign: 'center' }}>
        <div className="microlabel">India VIX</div>
        <Progress
          type="dashboard"
          percent={vix != null ? Math.min(100, (vix / 30) * 100) : 0}
          size={64}
          strokeColor={vixColor}
          trailColor="var(--bg-3)"
          format={() => (
            <span className="mono" style={{ fontSize: 14, color: vixColor }}>{vix != null ? fmt2(vix) : '—'}</span>
          )}
        />
      </div>
    </div>
  )
}
