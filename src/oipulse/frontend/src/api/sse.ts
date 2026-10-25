/**
 * SSE subscription to GET /api/stream?symbol=… — the scheduler pushes one full
 * snapshot frame per persisted snapshot. Returns an unsubscribe fn. The shell
 * wires this into the query cache so live pushes update the UI instantly, with
 * the 20s poll as an off-hours fallback.
 */

import type { OptionChain } from './types'

export function subscribeStream(
  symbol: string,
  onSnapshot: (snap: OptionChain) => void,
  onError?: (e: Event) => void,
): () => void {
  const url = `/api/stream?symbol=${encodeURIComponent(symbol)}`
  const es = new EventSource(url)

  es.onmessage = (ev) => {
    if (!ev.data) return
    try {
      const snap = JSON.parse(ev.data) as OptionChain
      onSnapshot(snap)
    } catch {
      /* keepalive / malformed frame — ignore */
    }
  }
  es.onerror = (e) => {
    onError?.(e)
    // EventSource auto-reconnects; nothing to do here.
  }

  return () => es.close()
}
