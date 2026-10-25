/** Hooks for the EOD-research (/api/research) and fundamentals (/api/fundamentals) JSON APIs. */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from './client'

export type Row = Record<string, any>
type P = Record<string, string | number | undefined>

const get = <T = any>(key: string, path: string, params?: P, enabled = true) =>
  useQuery<T>({ queryKey: [key, path, params ?? {}], queryFn: () => apiGet<T>(path, params), enabled, staleTime: 60_000 })

export const useMeta = () => get('r', '/research/meta')
export const useMarket = () => get('r', '/research/market')
export const useTicker = (symbol: string, days: number) => get('r', `/research/ticker/${symbol}`, { days }, !!symbol)
export const useIndices = (name: string | undefined, days: number) => get('r', '/research/indices', { name, days })
export const useFiiDii = (days: number) => get('r', '/research/fii-dii', { days })
export const useDeals = (symbol: string | undefined, days: number) => get('r', '/research/deals', { symbol, days })
export const useNews = (symbol?: string) => get('r', '/research/news', { symbol })
export const useEodChain = (symbol: string) => get('r', `/research/option-chain/${symbol}`, undefined, !!symbol)
export const useDataQuality = () => get('r', '/research/data-quality')
export const useSavedScreens = () => get('r', '/research/screener/saved')
export const usePortfolio = (name = 'default') => get('r', '/research/portfolio', { name })
export const useAlerts = () => get('r', '/research/alerts')
export const useWatchlists = () => get('r', '/research/watchlists')

export const useFund = (path: string, params?: P, enabled = true) => get('f', `/fundamentals${path}`, params, enabled)

/** POST/DELETE helper that invalidates the research cache afterwards. */
export function useRMutation<TIn = any, TOut = any>(fn: (v: TIn) => Promise<TOut>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ['r'] }) })
}

export const rPost = <T = any>(path: string, body?: unknown) => apiPost<T>(`/research${path}`, body)
export async function rDelete(path: string) {
  const res = await fetch(`/api/research${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
export async function rUpload(path: string, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`/api/research${path}`, { method: 'POST', body: fd })
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new Error(body?.detail ?? `HTTP ${res.status}`)
  return body
}
export async function fSql(sql: string) {
  const res = await fetch('/api/fundamentals/sql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json' },
    body: new URLSearchParams({ sql }),
  })
  return res.json()
}
