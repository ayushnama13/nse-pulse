/**
 * Number formatting — ported verbatim from legacy public/js/app.js (fmt/fmt0/fmt2).
 * Indian numbering: K (thousand), L (lakh, 1e5), Cr (crore, 1e7), en-IN grouping.
 * Golden-tested against the legacy outputs in __tests__/format.test.ts.
 */

const DASH = '—'

function isBad(n: number | null | undefined): boolean {
  return n === null || n === undefined || Number.isNaN(n)
}

/** Abbreviated: 1.23Cr / 4.56L / 7.8K / grouped integer. Legacy `fmt`. */
export function fmt(n: number | null | undefined): string {
  if (isBad(n)) return DASH
  const v = n as number
  const a = Math.abs(v)
  if (a >= 1e7) return (v / 1e7).toFixed(2) + 'Cr'
  if (a >= 1e5) return (v / 1e5).toFixed(2) + 'L'
  if (a >= 1e3) return (v / 1e3).toFixed(1) + 'K'
  return Math.round(v).toLocaleString('en-IN')
}

/** Grouped integer, en-IN. Legacy `fmt0`. */
export function fmt0(n: number | null | undefined): string {
  if (isBad(n)) return DASH
  return Math.round(n as number).toLocaleString('en-IN')
}

/** Fixed 2 decimals. Legacy `fmt2`. */
export function fmt2(n: number | null | undefined): string {
  if (isBad(n)) return DASH
  return (n as number).toFixed(2)
}

/** Signed abbreviated value, e.g. "+7.8K" / "-4.56L". Used for ΔOI tags. */
export function fmtSigned(n: number | null | undefined): string {
  if (isBad(n)) return DASH
  const s = fmt(n)
  return (n as number) > 0 ? '+' + s : s
}

/** Percent with sign, 2dp. e.g. "+0.34%". */
export function fmtPct(n: number | null | undefined): string {
  if (isBad(n)) return DASH
  const v = n as number
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%'
}
