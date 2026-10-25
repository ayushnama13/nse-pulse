/**
 * Pure analytics logic — ported verbatim from legacy public/js/app.js.
 * No DOM, no globals. Every function here is golden-tested against the legacy
 * behaviour in __tests__/analytics.test.ts so the migration can't silently
 * change a number.
 */

import type { ChainRow, FlowPoint } from '@/api/types'

export type RegimeClass = 'bull' | 'bear' | 'neutral' | 'warn'

/** One classifier input, auditable: which way it voted (null = abstained). */
export interface RegimeVote {
  label: string
  dir: 'bull' | 'bear' | null
  detail: string
}

export interface Regime {
  regime: string
  cls: RegimeClass
  bulls: number
  bears: number
  total: number
  votes: RegimeVote[]
}

/**
 * Top-N highlight engine. Returns Map<strike, rank(1..n)>.
 * Legacy `_topRanks(rows, key, n=5, useAbs=false)`. Generic so Compare rows
 * (ceOIA/ceOIB/…) rank the same way as chain rows.
 */
export function topRanks<T extends { strike: number }>(
  rows: T[],
  key: keyof T,
  n = 5,
  useAbs = false,
): Map<number, number> {
  const out = new Map<number, number>()
  rows
    .map((r) => ({ s: r.strike, v: useAbs ? Math.abs((r[key] as number) || 0) : ((r[key] as number) || 0) }))
    .filter((x) => x.v > 0)
    .sort((a, b) => b.v - a.v)
    .slice(0, n)
    .forEach((x, i) => out.set(x.s, i + 1))
  return out
}

/** Strike nearest to spot. Legacy `nearestATM()`. Returns null on empty input. */
export function nearestATM(chain: ChainRow[], spot: number | null | undefined): number | null {
  if (!chain.length || !spot) return null
  let best = chain[0]
  let bd = Math.abs(chain[0].strike - spot)
  for (const r of chain) {
    const d = Math.abs(r.strike - spot)
    if (d < bd) {
      bd = d
      best = r
    }
  }
  return best.strike
}

/** Premium-weighted PCR: Σ(peOI·peLTP) / Σ(ceOI·ceLTP). Legacy applyData WPCR. */
export function wpcr(chain: ChainRow[]): number {
  let ceVal = 0
  let peVal = 0
  for (const r of chain) {
    ceVal += (r.ceOI || 0) * (r.ceLTP || 0)
    peVal += (r.peOI || 0) * (r.peLTP || 0)
  }
  return ceVal > 0 ? peVal / ceVal : 0
}

export interface RegimeInput {
  pcr: number
  volPcr: number
  wpcr: number
  spot: number | null
  gammaFlip: number | null
  chain: ChainRow[]
}

/** Multi-signal regime classifier. Legacy `classifyRegime()` voting logic,
 *  extended with a per-signal vote breakdown so the UI can show WHY. */
export function classifyRegime(s: RegimeInput): Regime {
  const votes: RegimeVote[] = []
  const vote = (label: string, dir: 'bull' | 'bear' | null, detail: string) => votes.push({ label, dir, detail })

  if (s.pcr > 1.2) vote('OI PCR', 'bull', `${s.pcr.toFixed(2)} > 1.2`)
  else if (s.pcr < 0.8) vote('OI PCR', 'bear', `${s.pcr.toFixed(2)} < 0.8`)
  else vote('OI PCR', null, `${s.pcr.toFixed(2)} neutral`)

  if (s.volPcr > 1.2) vote('Vol PCR', 'bull', `${s.volPcr.toFixed(2)} > 1.2`)
  else if (s.volPcr > 0 && s.volPcr < 0.8) vote('Vol PCR', 'bear', `${s.volPcr.toFixed(2)} < 0.8`)
  else vote('Vol PCR', null, `${s.volPcr.toFixed(2)} neutral`)

  if (s.wpcr > 1.2) vote('WPCR ₹', 'bull', `${s.wpcr.toFixed(2)} > 1.2`)
  else if (s.wpcr > 0 && s.wpcr < 0.8) vote('WPCR ₹', 'bear', `${s.wpcr.toFixed(2)} < 0.8`)
  else vote('WPCR ₹', null, `${s.wpcr.toFixed(2)} neutral`)

  if (s.gammaFlip && s.spot) {
    if (s.spot > s.gammaFlip) vote('Spot vs γ-flip', 'bull', `spot above flip ${Math.round(s.gammaFlip)}`)
    else vote('Spot vs γ-flip', 'bear', `spot below flip ${Math.round(s.gammaFlip)}`)
  } else {
    vote('Spot vs γ-flip', null, 'no flip strike')
  }

  let netPe = 0
  let netCe = 0
  for (const r of s.chain) {
    netPe += r.peChg || 0
    netCe += r.ceChg || 0
  }
  const net = netPe - netCe
  if (net > 100000) vote('Net writing', 'bull', `PE−CE ΔOI +${Math.round(net / 1000)}K`)
  else if (net < -100000) vote('Net writing', 'bear', `CE−PE ΔOI +${Math.round(-net / 1000)}K`)
  else vote('Net writing', null, 'flat (<100K)')

  // Legacy parity: ratios computed over FIRED signals only (abstains excluded).
  const bulls = votes.filter((v) => v.dir === 'bull').length
  const bears = votes.filter((v) => v.dir === 'bear').length
  const total = bulls + bears || 1
  const base = { bulls, bears, total, votes }
  if (bulls / total >= 0.7) return { regime: 'Bullish', cls: 'bull', ...base }
  if (bears / total >= 0.7) return { regime: 'Bearish', cls: 'bear', ...base }
  if (Math.abs(bulls - bears) <= 1) return { regime: 'Neutral / Mixed', cls: 'neutral', ...base }
  return bulls > bears
    ? { regime: 'Lean Bullish', cls: 'warn', ...base }
    : { regime: 'Lean Bearish', cls: 'warn', ...base }
}

/** Strength tag for an OI spurt magnitude. Legacy `strengthOf`. */
export function strengthOf(absDelta: number): 'STRONG' | 'MOD' | 'WEAK' {
  if (absDelta >= 200000) return 'STRONG'
  if (absDelta >= 80000) return 'MOD'
  return 'WEAK'
}

/** Per-side OI z-scores vs the current snapshot's cross-strike mean+stddev.
 *  Legacy `renderZScore`. Returns rows with |z| ≥ 2, sorted by |z| desc. */
export function zScores(
  chain: ChainRow[],
  side: 'ce' | 'pe',
): { strike: number; z: number }[] {
  const key = side === 'ce' ? 'ceOI' : 'peOI'
  const vals = chain.map((r) => r[key]).filter((v) => v > 0)
  if (vals.length < 2) return []
  const mu = vals.reduce((a, b) => a + b, 0) / vals.length
  const variance = vals.reduce((a, b) => a + (b - mu) ** 2, 0) / vals.length
  const sd = Math.sqrt(variance)
  if (sd === 0) return []
  return chain
    .filter((r) => r[key] > 0)
    .map((r) => ({ strike: r.strike, z: (r[key] - mu) / sd }))
    .filter((x) => Math.abs(x.z) >= 2)
    .sort((a, b) => Math.abs(b.z) - Math.abs(a.z))
}

/** Buildup label from ΔOI sign per side (Position Buildup table). */
export function classifyBuildup(side: 'ce' | 'pe', chg: number): string {
  if (side === 'ce') return chg > 0 ? 'Short Buildup' : chg < 0 ? 'Short Covering' : '—'
  return chg > 0 ? 'Long Buildup' : chg < 0 ? 'Long Unwinding' : '—'
}

/** Slice `n` strikes either side of the ATM strike (by index, like the legacy
 *  ATM±N windows in renderOIBars/renderGammaChart). */
export function sliceAroundATM<T extends { strike: number }>(rows: T[], atm: number | null, n: number): T[] {
  if (!rows.length) return rows
  const sorted = [...rows].sort((a, b) => a.strike - b.strike)
  if (atm == null) return sorted.slice(0, n * 2 + 1)
  let idx = 0
  let best = Infinity
  sorted.forEach((r, i) => {
    const d = Math.abs(r.strike - atm)
    if (d < best) {
      best = d
      idx = i
    }
  })
  return sorted.slice(Math.max(0, idx - n), idx + n + 1)
}

// ── Pulse ΔOI rebasing (legacy renderPulse + _tsToMinFrom915) ───────────────

/** Minutes since 09:15 IST for an ISO timestamp's HH:MM, clamped 0..375. */
export function tsToMinFrom915(timestamp: string): number {
  const hh = parseInt(timestamp.slice(11, 13), 10)
  const mm = parseInt(timestamp.slice(14, 16), 10)
  if (Number.isNaN(hh) || Number.isNaN(mm)) return 0
  const mins = hh * 60 + mm - (9 * 60 + 15)
  return Math.max(0, Math.min(375, mins))
}

/** Inverse: minutes-from-09:15 → "HH:MM". Legacy `_minToHHMM`. */
export function minToHHMM(min: number): string {
  const total = 9 * 60 + 15 + Math.round(min)
  const hh = Math.floor(total / 60)
  const mm = total % 60
  return String(hh).padStart(2, '0') + ':' + String(mm).padStart(2, '0')
}

export type PulseRefMode = 'prev' | 'day' | 'window'

export interface PulseSeries {
  points: FlowPoint[]
  ce: number[]
  pe: number[]
  oiMaxAbs: number
}

/**
 * Rebase a single day's intraday-flow series for the Pulse chart.
 * `day` is already filtered to one date, ascending by time.
 * Returns the points inside [startMin,endMin] plus rebased ce/pe arrays.
 * Legacy `renderPulse` rebasing (§8.15).
 */
export function rebasePulse(
  day: FlowPoint[],
  startMin: number,
  endMin: number,
  mode: PulseRefMode,
): PulseSeries {
  const visible = day.filter((s) => {
    const m = tsToMinFrom915(s.timestamp)
    return m >= startMin && m <= endMin
  })
  let baseCe = 0
  let basePe = 0
  if (mode === 'day' && day.length) {
    baseCe = day[0].totalCeChg
    basePe = day[0].totalPeChg
  } else if (mode === 'window' && visible.length) {
    baseCe = visible[0].totalCeChg
    basePe = visible[0].totalPeChg
  }
  const ce = visible.map((s) => s.totalCeChg - baseCe)
  const pe = visible.map((s) => s.totalPeChg - basePe)
  let oiMaxAbs = 1
  for (const v of [...ce, ...pe]) oiMaxAbs = Math.max(oiMaxAbs, Math.abs(v))
  return { points: visible, ce, pe, oiMaxAbs }
}
