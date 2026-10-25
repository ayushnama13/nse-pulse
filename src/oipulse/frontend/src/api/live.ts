/**
 * Unified live-snapshot subscription. Prefers WebSocket (/ws/stream); on
 * failure falls back to SSE (/api/stream) AND keeps retrying WS with backoff —
 * when WS comes back, SSE is closed and the connection upgrades transparently.
 * Both transports deliver the same snapshot frames. Returns an unsubscribe fn.
 */

import type { OptionChain } from './types'
import { subscribeStream } from './sse'

export type LiveTransport = 'ws' | 'sse'

const WS_RETRY_BASE_MS = 5000
const WS_RETRY_MAX_MS = 60000

export function subscribeLive(
  symbol: string,
  onSnapshot: (snap: OptionChain) => void,
  onTransport?: (t: LiveTransport) => void,
): () => void {
  let closed = false
  let ws: WebSocket | null = null
  let sseStop: (() => void) | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let retryMs = WS_RETRY_BASE_MS

  const startSSE = () => {
    if (closed || sseStop) return
    onTransport?.('sse')
    sseStop = subscribeStream(symbol, onSnapshot)
  }

  const stopSSE = () => {
    sseStop?.()
    sseStop = null
  }

  const scheduleRetry = () => {
    if (closed || retryTimer) return
    retryTimer = setTimeout(() => {
      retryTimer = null
      retryMs = Math.min(retryMs * 2, WS_RETRY_MAX_MS)
      connectWS()
    }, retryMs)
  }

  const connectWS = () => {
    if (closed) return
    try {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/stream?symbol=${encodeURIComponent(symbol)}`)
      ws.onopen = () => {
        retryMs = WS_RETRY_BASE_MS
        stopSSE() // upgrade: WS is back, drop the SSE fallback
        onTransport?.('ws')
      }
      ws.onmessage = (ev) => {
        try {
          onSnapshot(JSON.parse(ev.data) as OptionChain)
        } catch {
          /* keepalive / malformed */
        }
      }
      ws.onclose = () => {
        ws = null
        if (closed) return
        startSSE() // degrade while we retry
        scheduleRetry()
      }
      ws.onerror = () => {
        // onclose follows; nothing extra to do
      }
    } catch {
      startSSE()
      scheduleRetry()
    }
  }

  connectWS()

  return () => {
    closed = true
    if (retryTimer) clearTimeout(retryTimer)
    try {
      ws?.close()
    } catch {
      /* ignore */
    }
    stopSSE()
  }
}
