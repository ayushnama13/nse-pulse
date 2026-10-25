/**
 * Domain types for the shapes the UI actually renders.
 *
 * orval generates request plumbing + query keys from openapi.json, but the
 * FastAPI routes return bare dicts (no response_model), so their generated
 * response types are loose. These hand-written types are the precise contract
 * for the payloads we read — kept in sync with snapshots.compute_snapshot and
 * the §9 data shapes in README.md.
 */

export type Symbol = 'NIFTY' | 'BANKNIFTY' | 'FINNIFTY' | 'NIFTYIT' | 'MIDCPNIFTY'

export const SYMBOLS: Symbol[] = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'NIFTYIT', 'MIDCPNIFTY']

/** One per-strike row (element of `chain`). */
export interface ChainRow {
  strike: number
  ceOI: number
  peOI: number
  ceChg: number
  peChg: number
  ceVol: number
  peVol: number
  ceLTP: number
  peLTP: number
  ceIV: number
  peIV: number
}

/** Per-strike gamma exposure (element of `gex`). */
export interface GexPoint {
  strike: number
  gex: number
  ceGex: number
  peGex: number
}

/** Response of GET /api/option-chain and each SSE `data:` frame. */
export interface OptionChain {
  time: string
  timestamp: string
  symbol: string
  lotSize: number
  spot: number
  pcr: number
  volPcr: number
  wpcr?: number | null
  maxPain: number
  totalCEOI: number
  totalPEOI: number
  totalCEVol: number
  totalPEVol: number
  atmStrike: number
  atmStraddle: number
  atmCeIV: number
  atmPeIV: number
  gammaFlip: number | null
  expiries: string[]
  currentExpiry: string
  gex: GexPoint[]
  chain: ChainRow[]
  data?: unknown[]
  stale?: boolean
  error?: string
}

/** One element of GET /api/intraday-flow `.series`. */
export interface FlowPoint {
  time: string
  timestamp: string
  spot: number
  totalCeChg: number
  totalPeChg: number
  netChg: number
}

export interface IntradayFlow {
  series: FlowPoint[]
}

/** GET /api/snapshots — metadata rows (no chain). */
export interface SnapshotMeta {
  timestamp: string
  time: string
  symbol: string
  spot: number
  pcr: number
  volPcr: number
  maxPain: number
}

/** GET /api/health */
export interface Health {
  ok: boolean
  marketOpen: boolean
  snapshotCounts: Record<string, number>
  lastFetch: Record<string, string>
  autoSymbols: string[]
  intervalSec: number
  dbPath: string
  dbSizeBytes: number
  now: string
}

export type LiveState = 'live' | 'stale' | 'error'

// ── Trends / history endpoints ──────────────────────────────────────────────
export interface OIHistoryPoint {
  time: string
  timestamp: string
  spot: number
  strikes: Record<string, { ceOI: number; peOI: number }>
}
export interface OIHistory {
  strikes: number[]
  series: OIHistoryPoint[]
}

export interface OIChangeRow {
  strike: number
  ceChg: number
  peChg: number
}
export interface OIChange {
  available: boolean
  rows: OIChangeRow[]
  summary?: {
    fromTime: string
    toTime: string
    fromTimestamp: string
    toTimestamp: string
    fromSpot: number
    toSpot: number
    totalCeChange: number
    totalPeChange: number
  }
}

export interface StrikeDetailPoint {
  time: string
  timestamp: string
  spot: number
  ceOI: number
  peOI: number
  ceLTP: number
  peLTP: number
  ceIV: number
  peIV: number
  ceChg: number
  peChg: number
}
export interface StrikeDetail {
  strike: number
  series: StrikeDetailPoint[]
}

export interface DailyAggRow {
  date: string
  spot: number
  pcr: number
  volPcr: number
  wpcr: number
  totalCEOI: number
  totalPEOI: number
  maxPain: number
}
export interface DailyAggregate {
  days: DailyAggRow[]
}

export interface StraddlePoint {
  time: string
  timestamp: string
  spot: number
  strike: number | null
  straddle: number
  pcr: number
  volPcr: number
  wpcr: number
}
export interface StraddleHistory {
  series: StraddlePoint[]
}

// ── Analytics ───────────────────────────────────────────────────────────────
export interface RegimeCell {
  bucket: string
  regime: string | null
  cls: 'bull' | 'bear' | 'neutral' | 'warn' | 'empty'
  bulls?: number
  bears?: number
}
export interface RegimeCalendar {
  days: { date: string; cells: RegimeCell[] }[]
  buckets: string[]
}

// ── Compare ─────────────────────────────────────────────────────────────────
export interface CompareRow {
  strike: number
  ceOIA: number
  ceOIB: number
  peOIA: number
  peOIB: number
  ceOIDelta: number
  peOIDelta: number
  ceLTPA: number
  ceLTPB: number
  peLTPA: number
  peLTPB: number
}
export interface Compare {
  symbol: string
  a: SnapshotMeta & { atmStrike?: number }
  b: SnapshotMeta & { atmStrike?: number }
  spotMove: number
  pcrShift: number
  maxPainShift: number
  rows: CompareRow[]
}

// ── Calendar ────────────────────────────────────────────────────────────────
export interface CalendarRow {
  expiry: string
  dte: number
  atmStrike: number
  atmStraddle: number
  atmCeIV: number
  atmPeIV: number
  atmIv: number
  pcr: number
  maxPain: number
  totalCEOI: number
  totalPEOI: number
  strikes: number
}
export interface Calendar {
  symbol: string
  spot: number
  expiries: CalendarRow[]
}

// ── Multi-Index ─────────────────────────────────────────────────────────────
export interface MultiResult extends Partial<OptionChain> {
  symbol: string
  ok?: boolean
  error?: string
}
export interface Multi {
  results: MultiResult[]
}

// ── Strike notes ────────────────────────────────────────────────────────────
export interface Note {
  id: number
  strike: number
  side: 'CE' | 'PE' | null
  body: string
  created_at?: string
  updated_at?: string
}
export interface NotesResponse {
  symbol: string
  notes: Note[]
}

// ── Macro (nse-library passthrough; fields read defensively) ─────────────────
export interface MacroEnvelope<T = Record<string, unknown>> {
  available: boolean
  data?: T
  [k: string]: unknown
}
