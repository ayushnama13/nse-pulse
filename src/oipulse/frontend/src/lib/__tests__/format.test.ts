import { describe, it, expect } from 'vitest'
import { fmt, fmt0, fmt2, fmtSigned, fmtPct } from '../format'

// Golden values: computed from the legacy public/js/app.js fmt/fmt0/fmt2
// implementations. If a value here changes, the port drifted.
describe('fmt (Indian abbreviations)', () => {
  it('crore / lakh / thousand thresholds', () => {
    expect(fmt(15_82_34_567)).toBe('15.82Cr')
    expect(fmt(1_47_209)).toBe('1.47L')
    expect(fmt(12_450)).toBe('12.4K') // 12.45 → toFixed(1) rounds down (float repr)
    expect(fmt(999)).toBe('999')
  })
  it('exact boundaries', () => {
    expect(fmt(1e7)).toBe('1.00Cr')
    expect(fmt(1e5)).toBe('1.00L')
    expect(fmt(1e3)).toBe('1.0K')
  })
  it('negatives keep sign and magnitude', () => {
    expect(fmt(-50_000)).toBe('-50.0K')
    expect(fmt(-1.5e7)).toBe('-1.50Cr')
  })
  it('grouped integers below 1000 use en-IN', () => {
    expect(fmt(500)).toBe('500')
  })
  it('bad input → em dash', () => {
    expect(fmt(null)).toBe('—')
    expect(fmt(undefined)).toBe('—')
    expect(fmt(NaN)).toBe('—')
  })
})

describe('fmt0 / fmt2', () => {
  it('fmt0 rounds and groups en-IN', () => {
    expect(fmt0(1234567)).toBe('12,34,567')
    expect(fmt0(22417.55)).toBe('22,418')
    expect(fmt0(null)).toBe('—')
  })
  it('fmt2 two decimals', () => {
    expect(fmt2(0.9333)).toBe('0.93')
    expect(fmt2(22417.5)).toBe('22417.50')
    expect(fmt2(NaN)).toBe('—')
  })
})

describe('fmtSigned / fmtPct', () => {
  it('positive gets a +, negative already has -', () => {
    expect(fmtSigned(12_450)).toBe('+12.4K')
    expect(fmtSigned(-12_450)).toBe('-12.4K')
    expect(fmtSigned(0)).toBe('0')
  })
  it('percent sign formatting', () => {
    expect(fmtPct(0.34)).toBe('+0.34%')
    expect(fmtPct(-1.2)).toBe('-1.20%')
  })
})
