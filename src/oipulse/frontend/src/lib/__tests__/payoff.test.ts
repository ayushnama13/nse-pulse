import { describe, it, expect } from 'vitest'
import { legPnL, payoffCurve, payoffStats, type Leg } from '../payoff'

describe('legPnL', () => {
  it('long call: loses premium below strike, gains above', () => {
    const leg: Leg = { type: 'CE', action: 'BUY', strike: 100, qty: 1, premium: 5 }
    expect(legPnL(leg, 90, 1)).toBe(-5) // OTM → -premium
    expect(legPnL(leg, 105, 1)).toBe(0) // breakeven
    expect(legPnL(leg, 110, 1)).toBe(5)
  })
  it('short put: keeps premium above strike, loses below', () => {
    const leg: Leg = { type: 'PE', action: 'SELL', strike: 100, qty: 1, premium: 4 }
    expect(legPnL(leg, 110, 1)).toBe(4) // OTM → +premium
    expect(legPnL(leg, 96, 1)).toBe(0) // breakeven
    expect(legPnL(leg, 90, 1)).toBe(-6)
  })
  it('qty and lot scale', () => {
    const leg: Leg = { type: 'CE', action: 'BUY', strike: 100, qty: 2, premium: 5 }
    expect(legPnL(leg, 110, 75)).toBe(2 * 75 * (10 - 5))
  })
})

describe('payoffCurve + stats: long straddle', () => {
  const legs: Leg[] = [
    { type: 'CE', action: 'BUY', strike: 100, qty: 1, premium: 5 },
    { type: 'PE', action: 'BUY', strike: 100, qty: 1, premium: 5 },
  ]
  it('breakevens at strike ± total premium', () => {
    const curve = payoffCurve(legs, 100, 1, 401, 0.2) // wide span to include 90/110
    const stats = payoffStats(curve)
    expect(stats.breakevens.length).toBe(2)
    const sorted = [...stats.breakevens].sort((a, b) => a - b)
    expect(sorted[0]).toBeCloseTo(90, 0)
    expect(sorted[1]).toBeCloseTo(110, 0)
  })
  it('max loss is -total premium at the strike', () => {
    const curve = payoffCurve(legs, 100, 1, 401, 0.2)
    const stats = payoffStats(curve)
    expect(stats.maxLoss).toBeCloseTo(-10, 5)
  })
  it('long straddle: profit unbounded, loss bounded', () => {
    const stats = payoffStats(payoffCurve(legs, 100, 1, 401, 0.2))
    expect(stats.maxProfitUnbounded).toBe(true)
    expect(stats.maxLossUnbounded).toBe(false)
  })
})

describe('unbounded detection', () => {
  it('naked short call: loss unbounded, profit bounded at premium', () => {
    const legs: Leg[] = [{ type: 'CE', action: 'SELL', strike: 100, qty: 1, premium: 5 }]
    const stats = payoffStats(payoffCurve(legs, 100, 1, 401, 0.2))
    expect(stats.maxLossUnbounded).toBe(true)
    expect(stats.maxProfitUnbounded).toBe(false)
    expect(stats.maxProfit).toBeCloseTo(5, 5)
  })
  it('covered-style flat curve: neither unbounded', () => {
    const legs: Leg[] = [
      { type: 'CE', action: 'BUY', strike: 100, qty: 1, premium: 5 },
      { type: 'CE', action: 'SELL', strike: 110, qty: 1, premium: 2 },
    ]
    const stats = payoffStats(payoffCurve(legs, 100, 1, 401, 0.2))
    expect(stats.maxProfitUnbounded).toBe(false)
    expect(stats.maxLossUnbounded).toBe(false)
  })
})
