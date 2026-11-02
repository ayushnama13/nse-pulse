/** Hooks for the market data API (/api/data). */
import { useQuery } from '@tanstack/react-query'
import { apiGet } from './client'

type P = Record<string, string | number | undefined>

const get = <T = any>(key: string, path: string, params?: P, enabled = true) =>
  useQuery<T>({ queryKey: [key, path, params ?? {}], queryFn: () => apiGet<T>(`/data${path}`, params), enabled, staleTime: 60_000 })

export const useDeliveryLeaders = (date?: string, minVolume?: number, limit?: number) =>
  get('data', '/delivery/leaders', { date, min_volume: minVolume, limit })

export const useDeliveryHistory = (symbol: string, days?: number) =>
  get('data', `/delivery/${symbol}`, { days }, !!symbol)

export const useShortSelling = (date?: string, limit?: number) =>
  get('data', '/short-selling', { date, limit })

export const useFoBan = (date?: string, dates?: number, limit?: number) =>
  get('data', '/fo-ban', { date, dates, limit })

export const useFoBanHistory = (days?: number, limit?: number) =>
  get('data', '/fo-ban/history', { days, limit })

export const usePriceBands = (date?: string, band?: number, limit?: number) =>
  get('data', '/price-bands', { date, band, limit })

export const usePriceBandChanges = (days?: number, limit?: number) =>
  get('data', '/price-band-changes', { days, limit })

export const useInsider = (symbol?: string, days?: number, limit?: number) =>
  get('data', '/insider', { symbol, days, limit })

export const useSast = (symbol?: string, days?: number, limit?: number) =>
  get('data', '/sast', { symbol, days, limit })

export const usePledge = (minPledgedPct?: number, limit?: number) =>
  get('data', '/pledge', { min_pledged_pct: minPledgedPct, limit })

export const useIpo = (status?: string, limit?: number) =>
  get('data', '/ipo', { status, limit })

export const useEtfList = (limit?: number) =>
  get('data', '/etf', { limit })

export const useEtfDetail = (symbol: string, limit?: number) =>
  get('data', `/etf/${symbol}`, { limit }, !!symbol)

export const useFiiDeriv = (days?: number, limit?: number) =>
  get('data', '/fii-deriv', { days, limit })

export const useFiiDerivSummary = () =>
  get('data', '/fii-deriv/summary')

export const useVix = (days?: number, limit?: number) =>
  get('data', '/vix', { days, limit })

export const useTurnover = (days?: number, limit?: number) =>
  get('data', '/turnover', { days, limit })
