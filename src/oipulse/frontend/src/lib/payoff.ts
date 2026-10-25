/** Pure 2-leg (or N-leg) option payoff math for the Payoff tab. Golden-tested. */

export interface Leg {
  type: 'CE' | 'PE'
  action: 'BUY' | 'SELL'
  strike: number
  qty: number
  premium: number
}

/** P&L of one leg at expiry underlying price S, in rupees (qty × lot aware). */
export function legPnL(leg: Leg, S: number, lot: number): number {
  const intrinsic = leg.type === 'CE' ? Math.max(S - leg.strike, 0) : Math.max(leg.strike - S, 0)
  const sign = leg.action === 'BUY' ? 1 : -1
  const v = sign * (intrinsic - leg.premium) * leg.qty * lot
  return v === 0 ? 0 : v // normalize -0 → 0
}

export interface PayoffCurve {
  prices: number[]
  pnl: number[]
}

/** Total P&L across underlying prices spanning ±`span` of spot. */
export function payoffCurve(legs: Leg[], spot: number, lot: number, points = 121, span = 0.08): PayoffCurve {
  const lo = spot * (1 - span)
  const hi = spot * (1 + span)
  const step = (hi - lo) / (points - 1)
  const prices: number[] = []
  const pnl: number[] = []
  for (let i = 0; i < points; i++) {
    const S = lo + i * step
    prices.push(S)
    pnl.push(legs.reduce((sum, leg) => sum + legPnL(leg, S, lot), 0))
  }
  return { prices, pnl }
}

export interface PayoffStats {
  maxProfit: number
  maxLoss: number
  breakevens: number[]
  /** P&L still rising at a domain edge → true max profit is unbounded (e.g. naked long call). */
  maxProfitUnbounded: boolean
  /** P&L still falling at a domain edge → true max loss is unbounded (e.g. naked short call). */
  maxLossUnbounded: boolean
}

export function payoffStats(curve: PayoffCurve): PayoffStats {
  const { prices, pnl } = curve
  let maxProfit = -Infinity
  let maxLoss = Infinity
  for (const v of pnl) {
    if (v > maxProfit) maxProfit = v
    if (v < maxLoss) maxLoss = v
  }
  const n = pnl.length
  // outward slope at each edge (toward -∞ on the left, +∞ on the right)
  const rightOut = n >= 2 ? pnl[n - 1] - pnl[n - 2] : 0
  const leftOut = n >= 2 ? pnl[0] - pnl[1] : 0
  const eps = 1e-9
  const maxProfitUnbounded =
    (rightOut > eps && pnl[n - 1] >= maxProfit - eps) || (leftOut > eps && pnl[0] >= maxProfit - eps)
  const maxLossUnbounded =
    (rightOut < -eps && pnl[n - 1] <= maxLoss + eps) || (leftOut < -eps && pnl[0] <= maxLoss + eps)
  // A breakeven is a sign change. Treat 0 as non-negative so a P&L that lands
  // exactly on a grid point is counted once (linear interp gives that point).
  const breakevens: number[] = []
  for (let i = 1; i < pnl.length; i++) {
    const a = pnl[i - 1]
    const b = pnl[i]
    if (a < 0 !== b < 0 && a !== b) {
      const t = -a / (b - a)
      breakevens.push(prices[i - 1] + t * (prices[i] - prices[i - 1]))
    }
  }
  return { maxProfit, maxLoss, breakevens, maxProfitUnbounded, maxLossUnbounded }
}
