import { describe, it, expect } from 'vitest'
import {
  topRanks,
  nearestATM,
  wpcr,
  classifyRegime,
  tsToMinFrom915,
  minToHHMM,
  rebasePulse,
} from '../analytics'
import type { ChainRow, FlowPoint } from '@/api/types'

const row = (p: Partial<ChainRow> & { strike: number }): ChainRow => ({
  strike: p.strike,
  ceOI: p.ceOI ?? 0,
  peOI: p.peOI ?? 0,
  ceChg: p.ceChg ?? 0,
  peChg: p.peChg ?? 0,
  ceVol: p.ceVol ?? 0,
  peVol: p.peVol ?? 0,
  ceLTP: p.ceLTP ?? 0,
  peLTP: p.peLTP ?? 0,
  ceIV: p.ceIV ?? 0,
  peIV: p.peIV ?? 0,
})

const chain: ChainRow[] = [
  row({ strike: 22000, ceOI: 100, peOI: 500, ceChg: 10, peChg: 200000, ceLTP: 470, peLTP: 5 }),
  row({ strike: 22500, ceOI: 1000, peOI: 1000, ceChg: -5, peChg: 50, ceLTP: 100, peLTP: 100 }),
  row({ strike: 23000, ceOI: 300, peOI: 50, ceChg: 5, peChg: 5, ceLTP: 5, peLTP: 470 }),
]

describe('topRanks', () => {
  it('ranks top-N by value desc, drops zeros', () => {
    const m = topRanks(chain, 'ceOI', 2)
    expect(m.get(22500)).toBe(1)
    expect(m.get(23000)).toBe(2)
    expect(m.has(22000)).toBe(false) // 100 is 3rd, outside top-2
  })
  it('useAbs ranks by magnitude', () => {
    const m = topRanks(chain, 'ceChg', 3, true)
    expect(m.get(22000)).toBe(1) // |10| largest
    expect(m.size).toBe(3)
  })
})

describe('nearestATM', () => {
  it('picks the closest strike to spot', () => {
    expect(nearestATM(chain, 22450)).toBe(22500)
    expect(nearestATM(chain, 22010)).toBe(22000)
  })
  it('null on empty chain or falsy spot', () => {
    expect(nearestATM([], 22450)).toBeNull()
    expect(nearestATM(chain, 0)).toBeNull()
  })
})

describe('wpcr', () => {
  it('premium-weighted PCR', () => {
    // ceVal = 100*470 + 1000*100 + 300*5 = 148500
    // peVal = 500*5  + 1000*100 + 50*470 = 126000
    expect(wpcr(chain)).toBeCloseTo(126000 / 148500, 6)
  })
  it('zero CE value → 0', () => {
    expect(wpcr([row({ strike: 1, ceOI: 0, peOI: 5, peLTP: 5 })])).toBe(0)
  })
})

describe('classifyRegime', () => {
  it('all-bull signals → Bullish', () => {
    const r = classifyRegime({ pcr: 1.3, volPcr: 1.25, wpcr: 1.3, spot: 22450, gammaFlip: 22400, chain })
    expect(r).toMatchObject({ regime: 'Bullish', cls: 'bull' })
  })
  it('all-bear signals → Bearish', () => {
    const bearChain = [row({ strike: 22000, ceChg: 200000, peChg: 0 })]
    const r = classifyRegime({ pcr: 0.7, volPcr: 0.7, wpcr: 0.7, spot: 22000, gammaFlip: 22400, chain: bearChain })
    expect(r).toMatchObject({ regime: 'Bearish', cls: 'bear' })
  })
  it('one bull one bear → Neutral / Mixed', () => {
    const flat = [row({ strike: 22000, ceChg: 1, peChg: 1 })]
    const r = classifyRegime({ pcr: 1.3, volPcr: 0.7, wpcr: 1.0, spot: 22000, gammaFlip: null, chain: flat })
    expect(r).toMatchObject({ regime: 'Neutral / Mixed', cls: 'neutral' })
  })
})

describe('tsToMinFrom915 / minToHHMM', () => {
  const ts = (hhmm: string) => `2026-05-04T${hhmm}:00+05:30`
  it('minutes since 09:15, clamped 0..375', () => {
    expect(tsToMinFrom915(ts('09:18'))).toBe(3)
    expect(tsToMinFrom915(ts('10:00'))).toBe(45)
    expect(tsToMinFrom915(ts('15:30'))).toBe(375)
    expect(tsToMinFrom915(ts('08:00'))).toBe(0) // clamp low
    expect(tsToMinFrom915(ts('16:00'))).toBe(375) // clamp high
  })
  it('minToHHMM inverts', () => {
    expect(minToHHMM(0)).toBe('09:15')
    expect(minToHHMM(45)).toBe('10:00')
    expect(minToHHMM(375)).toBe('15:30')
  })
})

describe('rebasePulse', () => {
  const day: FlowPoint[] = [
    { timestamp: '2026-05-04T09:18:00+05:30', time: '09:18', spot: 22340, totalCeChg: 200, totalPeChg: 100, netChg: -100 },
    { timestamp: '2026-05-04T10:00:00+05:30', time: '10:00', spot: 22360, totalCeChg: 1000, totalPeChg: 500, netChg: -500 },
    { timestamp: '2026-05-04T11:00:00+05:30', time: '11:00', spot: 22380, totalCeChg: 1500, totalPeChg: 900, netChg: -600 },
  ]
  it('prev mode: no shift', () => {
    const r = rebasePulse(day, 0, 375, 'prev')
    expect(r.ce).toEqual([200, 1000, 1500])
    expect(r.pe).toEqual([100, 500, 900])
    expect(r.oiMaxAbs).toBe(1500)
  })
  it('day mode: rebased to first point of the day', () => {
    const r = rebasePulse(day, 0, 375, 'day')
    expect(r.ce).toEqual([0, 800, 1300])
    expect(r.pe).toEqual([0, 400, 800])
  })
  it('window mode: rebased to first visible point', () => {
    const r = rebasePulse(day, 45, 375, 'window') // drops the 09:18 point
    expect(r.points.length).toBe(2)
    expect(r.ce).toEqual([0, 500])
    expect(r.pe).toEqual([0, 400])
  })
})
