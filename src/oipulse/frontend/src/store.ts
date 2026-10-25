import { create } from 'zustand'
import type { OptionChain, LiveState } from '@/api/types'
import { wpcr as computeWpcr, classifyRegime, type Regime } from '@/lib/analytics'

/** Trailing in-memory headline history (sparklines), capped like the legacy
 *  80-point arrays. Separate from DB-backed history. */
const HISTORY_CAP = 80

export interface HistPoint {
  t: string
  v: number
}

/** One row in the "What changed" feed. */
export interface FeedEvent {
  id: number
  time: string
  icon: string
  level: 'info' | 'warning'
  message: string
}

const FEED_CAP = 50
let feedSeq = 1

interface ShellState {
  symbol: string
  expiry: string | undefined
  tab: string
  theme: 'dark' | 'light'
  density: 'comfortable' | 'compact'

  // latest live snapshot + derived headline
  snap: OptionChain | null
  wpcr: number
  live: LiveState

  // trailing sparkline histories
  spotHist: HistPoint[]
  pcrHist: HistPoint[]
  volPcrHist: HistPoint[]
  wpcrHist: HistPoint[]

  // pinned strikes — highlighted across chain/charts
  pinned: number[]

  // derived regime (auditable votes) + live event feed
  regime: Regime | null
  events: FeedEvent[]
  addEvent: (e: Omit<FeedEvent, 'id'>) => void

  setSymbol: (s: string) => void
  setExpiry: (e: string | undefined) => void
  setTab: (t: string) => void
  toggleTheme: () => void
  toggleDensity: () => void
  applySnapshot: (snap: OptionChain, live?: LiveState) => void
  setLive: (live: LiveState) => void
  togglePin: (strike: number) => void
}

const PIN_KEY = 'oipulse:pinned'
function loadPins(): number[] {
  try {
    const raw = localStorage.getItem(PIN_KEY)
    return raw ? (JSON.parse(raw) as number[]) : []
  } catch {
    return []
  }
}

function push(arr: HistPoint[], p: HistPoint): HistPoint[] {
  const next = [...arr, p]
  return next.length > HISTORY_CAP ? next.slice(next.length - HISTORY_CAP) : next
}

export const useShell = create<ShellState>((set) => ({
  symbol: 'NIFTY',
  expiry: undefined,
  tab: 'home',
  theme: 'dark',
  density: 'comfortable',
  snap: null,
  wpcr: 0,
  live: 'live',
  spotHist: [],
  pcrHist: [],
  volPcrHist: [],
  wpcrHist: [],
  pinned: loadPins(),
  regime: null,
  events: [],

  addEvent: (e) =>
    set((s) => ({ events: [{ id: feedSeq++, ...e }, ...s.events].slice(0, FEED_CAP) })),

  setSymbol: (symbol) =>
    set({ symbol, expiry: undefined, snap: null, regime: null, events: [], spotHist: [], pcrHist: [], volPcrHist: [], wpcrHist: [] }),
  setExpiry: (expiry) => set({ expiry }),
  setTab: (tab) => set({ tab }),
  toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
  toggleDensity: () => set((s) => ({ density: s.density === 'comfortable' ? 'compact' : 'comfortable' })),
  setLive: (live) => set({ live }),
  togglePin: (strike) =>
    set((s) => {
      const next = s.pinned.includes(strike) ? s.pinned.filter((x) => x !== strike) : [...s.pinned, strike]
      try {
        localStorage.setItem(PIN_KEY, JSON.stringify(next))
      } catch {
        /* ignore quota / unavailable */
      }
      return { pinned: next }
    }),

  applySnapshot: (snap, live = 'live') =>
    set((s) => {
      // Ignore frames for a symbol the user has since switched away from.
      if (snap.symbol && snap.symbol.toUpperCase() !== s.symbol.toUpperCase()) return s
      const w = snap.wpcr ?? computeWpcr(snap.chain || [])
      // Same-timestamp frame (poll of an unchanged snapshot, SSE replay):
      // update headline state but don't append duplicate history points.
      const dup = s.spotHist.length > 0 && s.spotHist[s.spotHist.length - 1].t === snap.time
      const regime = classifyRegime({
        pcr: snap.pcr ?? 0,
        volPcr: snap.volPcr ?? 0,
        wpcr: w,
        spot: snap.spot ?? null,
        gammaFlip: snap.gammaFlip ?? null,
        chain: snap.chain ?? [],
      })
      // Regime flip → feed event (single source: the store sees every frame).
      let events = s.events
      if (s.regime && s.regime.regime !== regime.regime) {
        events = [
          {
            id: feedSeq++,
            time: snap.time,
            icon: regime.cls === 'bull' ? '↑' : regime.cls === 'bear' ? '↓' : '↔',
            level: 'info' as const,
            message: `Regime → ${regime.regime} (${regime.bulls}↑ ${regime.bears}↓)`,
          },
          ...events,
        ].slice(0, FEED_CAP)
      }
      return {
        snap,
        wpcr: w,
        regime,
        events,
        live: snap.stale ? 'stale' : live,
        spotHist: dup ? s.spotHist : push(s.spotHist, { t: snap.time, v: snap.spot }),
        pcrHist: dup ? s.pcrHist : push(s.pcrHist, { t: snap.time, v: snap.pcr }),
        volPcrHist: dup ? s.volPcrHist : push(s.volPcrHist, { t: snap.time, v: snap.volPcr }),
        wpcrHist: dup ? s.wpcrHist : push(s.wpcrHist, { t: snap.time, v: w }),
      }
    }),
}))
