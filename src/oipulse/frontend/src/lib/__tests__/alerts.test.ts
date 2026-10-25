import { describe, it, expect } from 'vitest'
import { evalAlerts, DEFAULT_RULES, type AlertRule } from '../alerts'
import type { OptionChain, ChainRow } from '@/api/types'

const row = (strike: number, ceChg = 0, peChg = 0): ChainRow => ({
  strike, ceOI: 0, peOI: 0, ceChg, peChg, ceVol: 0, peVol: 0, ceLTP: 0, peLTP: 0, ceIV: 0, peIV: 0,
})

const snap = (over: Partial<OptionChain>): OptionChain =>
  ({
    time: '', timestamp: '', symbol: 'NIFTY', lotSize: 75, spot: 100, pcr: 1, volPcr: 1, maxPain: 100,
    totalCEOI: 0, totalPEOI: 0, totalCEVol: 0, totalPEVol: 0, atmStrike: 100, atmStraddle: 0,
    atmCeIV: 0, atmPeIV: 0, gammaFlip: null, expiries: [], currentExpiry: '', gex: [], chain: [],
    ...over,
  }) as OptionChain

describe('evalAlerts (edge-triggered)', () => {
  it('pcr_above fires only on the crossing tick', () => {
    const rules: AlertRule[] = [{ id: 'a', type: 'pcr_above', threshold: 1.2, enabled: true }]
    expect(evalAlerts(rules, snap({ pcr: 1.3 }), snap({ pcr: 1.0 }))).toHaveLength(1)
    expect(evalAlerts(rules, snap({ pcr: 1.4 }), snap({ pcr: 1.3 }))).toHaveLength(0) // already above
    expect(evalAlerts(rules, snap({ pcr: 1.3 }), null)).toHaveLength(1) // first tick above
  })
  it('spot_cross_maxpain fires on sign flip', () => {
    const rules: AlertRule[] = [{ id: 'm', type: 'spot_cross_maxpain', threshold: 0, enabled: true }]
    expect(evalAlerts(rules, snap({ spot: 105, maxPain: 100 }), snap({ spot: 95, maxPain: 100 }))).toHaveLength(1)
    expect(evalAlerts(rules, snap({ spot: 106, maxPain: 100 }), snap({ spot: 105, maxPain: 100 }))).toHaveLength(0)
  })
  it('oi_spurt fires when max |ΔOI| crosses threshold', () => {
    const rules: AlertRule[] = [{ id: 's', type: 'oi_spurt', threshold: 100000, enabled: true }]
    const hot = snap({ chain: [row(100, 150000, 0)] })
    const cold = snap({ chain: [row(100, 50000, 0)] })
    expect(evalAlerts(rules, hot, cold)).toHaveLength(1)
    expect(evalAlerts(rules, hot, hot)).toHaveLength(0)
  })
  it('disabled rules never fire', () => {
    const rules: AlertRule[] = [{ id: 'a', type: 'pcr_above', threshold: 1.2, enabled: false }]
    expect(evalAlerts(rules, snap({ pcr: 2 }), snap({ pcr: 0 }))).toHaveLength(0)
  })
  it('default rule set is well-formed', () => {
    expect(DEFAULT_RULES.every((r) => r.id && r.type && typeof r.threshold === 'number')).toBe(true)
  })
})
