/** Client-side alert rule engine. Pure + edge-triggered (fires on the tick the
 *  condition becomes true, not every tick it stays true). Golden-tested. */

import type { OptionChain } from '@/api/types'

export type AlertRuleType = 'pcr_above' | 'pcr_below' | 'oi_spurt' | 'spot_cross_maxpain'

export interface AlertRule {
  id: string
  type: AlertRuleType
  threshold: number
  enabled: boolean
}

export interface AlertEvent {
  ruleId: string
  level: 'info' | 'warning'
  message: string
}

export const DEFAULT_RULES: AlertRule[] = [
  { id: 'pcr-hi', type: 'pcr_above', threshold: 1.3, enabled: true },
  { id: 'pcr-lo', type: 'pcr_below', threshold: 0.7, enabled: true },
  { id: 'spurt', type: 'oi_spurt', threshold: 200000, enabled: true },
  { id: 'maxpain', type: 'spot_cross_maxpain', threshold: 0, enabled: true },
]

function maxAbsChg(snap: OptionChain): number {
  let m = 0
  for (const r of snap.chain ?? []) {
    m = Math.max(m, Math.abs(r.ceChg), Math.abs(r.peChg))
  }
  return m
}

/** Returns events that NEWLY trigger comparing `snap` against `prev`. */
export function evalAlerts(rules: AlertRule[], snap: OptionChain, prev: OptionChain | null): AlertEvent[] {
  const out: AlertEvent[] = []
  for (const rule of rules) {
    if (!rule.enabled) continue
    switch (rule.type) {
      case 'pcr_above':
        if (snap.pcr > rule.threshold && (!prev || prev.pcr <= rule.threshold))
          out.push({ ruleId: rule.id, level: 'info', message: `OI PCR ${snap.pcr.toFixed(2)} crossed above ${rule.threshold}` })
        break
      case 'pcr_below':
        if (snap.pcr < rule.threshold && (!prev || prev.pcr >= rule.threshold))
          out.push({ ruleId: rule.id, level: 'warning', message: `OI PCR ${snap.pcr.toFixed(2)} crossed below ${rule.threshold}` })
        break
      case 'oi_spurt': {
        const cur = maxAbsChg(snap)
        const was = prev ? maxAbsChg(prev) : 0
        if (cur > rule.threshold && was <= rule.threshold)
          out.push({ ruleId: rule.id, level: 'info', message: `OI spurt — |ΔOI| crossed ${(rule.threshold / 1000).toFixed(0)}K` })
        break
      }
      case 'spot_cross_maxpain': {
        if (!prev || !snap.maxPain || !prev.maxPain) break
        const curSign = Math.sign(snap.spot - snap.maxPain)
        const prevSign = Math.sign(prev.spot - prev.maxPain)
        if (curSign !== 0 && prevSign !== 0 && curSign !== prevSign)
          out.push({ ruleId: rule.id, level: 'warning', message: `Spot crossed Max Pain (${snap.maxPain})` })
        break
      }
    }
  }
  return out
}
