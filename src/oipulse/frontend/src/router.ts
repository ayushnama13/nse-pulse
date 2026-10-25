/**
 * Lightweight typed hash router — keeps `#tab=…&sym=…` in the URL so refresh
 * and deep-links survive, matching the legacy app's hash-state behaviour.
 *
 * Deviation from the planned TanStack Router: this app is a single page of
 * tabs, so a full router (loaders, nested routes) is overkill. A hash sync
 * gives exact legacy compatibility with zero added dependency and no
 * version-churn risk. Routing is isolated here, so swapping to TanStack Router
 * later is a one-file change if richer routing is ever needed.
 */

import { useEffect } from 'react'
import { useShell } from './store'
import { SYMBOLS } from './api/types'

export const TAB_ORDER = [
  'home',
  'chain',
  'oi',
  'vol',
  'trends',
  'analytics',
  'macro',
  'multi',
  'compare',
  'pulse',
  'calendar',
  'payoff',
] as const

export type TabKey = (typeof TAB_ORDER)[number]

interface HashState {
  tab?: string
  sym?: string
}

export function readHash(): HashState {
  const h = window.location.hash.replace(/^#/, '')
  const out: HashState = {}
  for (const part of h.split('&')) {
    const [k, v] = part.split('=')
    if (k && v) out[k as keyof HashState] = decodeURIComponent(v)
  }
  return out
}

function writeHash(tab: string, sym: string) {
  const next = `#tab=${tab}&sym=${sym}`
  if (window.location.hash !== next) {
    history.replaceState(null, '', next)
  }
}

/** Two-way sync between the store (symbol/tab) and the URL hash. Mount once. */
export function useHashSync() {
  const tab = useShell((s) => s.tab)
  const symbol = useShell((s) => s.symbol)
  const setTab = useShell((s) => s.setTab)
  const setSymbol = useShell((s) => s.setSymbol)

  // hash → store (initial load + back/forward). Compare against current state
  // first — setSymbol resets snapshot + sparkline histories, so calling it with
  // an unchanged symbol (e.g. back-button tab change) must be a no-op.
  useEffect(() => {
    const apply = () => {
      const h = readHash()
      const cur = useShell.getState()
      if (h.tab && h.tab !== cur.tab && (TAB_ORDER as readonly string[]).includes(h.tab)) setTab(h.tab)
      const sym = h.sym?.toUpperCase()
      if (sym && sym !== cur.symbol && (SYMBOLS as string[]).includes(sym)) setSymbol(sym)
    }
    apply()
    window.addEventListener('hashchange', apply)
    return () => window.removeEventListener('hashchange', apply)
  }, [setTab, setSymbol])

  // store → hash
  useEffect(() => {
    writeHash(tab, symbol)
  }, [tab, symbol])
}
