/** Thin typed fetch wrapper. All endpoints live under /api (proxied in dev,
 *  same-origin in prod). Errors surface as thrown Error with the backend's
 *  {error: "..."} message when present. */

const BASE = '/api'

export async function apiGet<T>(path: string, params?: Record<string, string | number | undefined>, signal?: AbortSignal): Promise<T> {
  const qs = params
    ? '?' +
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join('&')
    : ''
  const res = await fetch(`${BASE}${path}${qs}`, { signal, headers: { Accept: 'application/json' } })
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const msg = (body && (body.error || body.detail)) || `HTTP ${res.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return body as T
}

export async function apiPost<T>(path: string, payload?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const msg = (body && (body.error || body.detail)) || `HTTP ${res.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return body as T
}
