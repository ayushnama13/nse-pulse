/**
 * TanStack Query hooks over the typed client.
 *
 * orval also generates hooks from openapi.json (`npm run gen:api` →
 * src/api/generated.ts) for endpoints with declared schemas; these hand-written
 * hooks cover the payloads whose precise domain types live in ./types.ts. Query
 * keys are namespaced by endpoint + params so cache invalidation is predictable.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from './client'
import type {
  OptionChain,
  IntradayFlow,
  SnapshotMeta,
  Health,
  OIHistory,
  OIChange,
  StrikeDetail,
  DailyAggregate,
  StraddleHistory,
  RegimeCalendar,
  Compare,
  Calendar,
  Multi,
  MacroEnvelope,
  NotesResponse,
} from './types'

export const qk = {
  optionChain: (symbol: string, expiry?: string) => ['option-chain', symbol, expiry ?? ''] as const,
  intradayFlow: (symbol: string, limit: number) => ['intraday-flow', symbol, limit] as const,
  snapshots: (symbol: string) => ['snapshots', symbol] as const,
  health: () => ['health'] as const,
  oiHistory: (symbol: string, key: string) => ['oi-history', symbol, key] as const,
  oiChange: (symbol: string, w: number) => ['oi-change', symbol, w] as const,
  strikeDetail: (symbol: string, strike: number) => ['strike-detail', symbol, strike] as const,
  dailyAgg: (symbol: string, days: number) => ['daily-aggregate', symbol, days] as const,
  straddle: (symbol: string) => ['straddle-history', symbol] as const,
  regimeCal: (symbol: string, days: number) => ['regime-calendar', symbol, days] as const,
  compare: (symbol: string, a: string, b: string) => ['compare', symbol, a, b] as const,
  calendar: (symbol: string, n: number) => ['calendar', symbol, n] as const,
  multi: (symbols: string) => ['multi', symbols] as const,
  vix: () => ['vix'] as const,
  fiiDii: () => ['fii-dii'] as const,
  participant: () => ['participant-oi'] as const,
  notes: (symbol: string) => ['notes', symbol] as const,
}

/** Live option chain. Polls as a fallback; SSE is the primary push (see store). */
export function useOptionChain(symbol: string, expiry?: string, pollMs = 20000) {
  return useQuery({
    queryKey: qk.optionChain(symbol, expiry),
    queryFn: ({ signal }) => apiGet<OptionChain>('/option-chain', { symbol, expiry }, signal),
    refetchInterval: pollMs,
    staleTime: pollMs / 2,
  })
}

export function useIntradayFlow(symbol: string, limit = 500) {
  return useQuery({
    queryKey: qk.intradayFlow(symbol, limit),
    queryFn: ({ signal }) => apiGet<IntradayFlow>('/intraday-flow', { symbol, limit }, signal),
  })
}

export function useSnapshots(symbol: string) {
  return useQuery({
    queryKey: qk.snapshots(symbol),
    queryFn: async ({ signal }) => {
      // server wraps the list: { symbol, snapshots: [...] }
      const res = await apiGet<{ snapshots?: SnapshotMeta[] } | SnapshotMeta[]>('/snapshots', { symbol }, signal)
      return Array.isArray(res) ? res : (res.snapshots ?? [])
    },
  })
}

export function useHealth() {
  return useQuery({
    queryKey: qk.health(),
    queryFn: ({ signal }) => apiGet<Health>('/health', undefined, signal),
    refetchInterval: 30000,
  })
}

export function useOIHistory(symbol: string, opts: { strikes?: string; top?: number; windowMin?: number } = {}) {
  const key = `${opts.strikes ?? ''}|${opts.top ?? 6}|${opts.windowMin ?? ''}`
  return useQuery({
    queryKey: qk.oiHistory(symbol, key),
    queryFn: ({ signal }) =>
      apiGet<OIHistory>('/oi-history', { symbol, strikes: opts.strikes, top: opts.top, windowMin: opts.windowMin }, signal),
  })
}

export function useOIChange(symbol: string, windowMin: number) {
  return useQuery({
    queryKey: qk.oiChange(symbol, windowMin),
    queryFn: ({ signal }) => apiGet<OIChange>('/oi-change', { symbol, windowMin }, signal),
  })
}

export function useStrikeDetail(symbol: string, strike: number | null) {
  return useQuery({
    queryKey: qk.strikeDetail(symbol, strike ?? 0),
    queryFn: ({ signal }) => apiGet<StrikeDetail>('/strike-detail', { symbol, strike: strike ?? 0 }, signal),
    enabled: strike != null,
  })
}

export function useDailyAggregate(symbol: string, days = 30) {
  return useQuery({
    queryKey: qk.dailyAgg(symbol, days),
    queryFn: ({ signal }) => apiGet<DailyAggregate>('/daily-aggregate', { symbol, days }, signal),
  })
}

export function useStraddleHistory(symbol: string) {
  return useQuery({
    queryKey: qk.straddle(symbol),
    queryFn: ({ signal }) => apiGet<StraddleHistory>('/straddle-history', { symbol }, signal),
  })
}

export function useRegimeCalendar(symbol: string, days = 30) {
  return useQuery({
    queryKey: qk.regimeCal(symbol, days),
    queryFn: ({ signal }) => apiGet<RegimeCalendar>('/regime-calendar', { symbol, days }, signal),
  })
}

export function useCompare(symbol: string, aTs?: string, bTs?: string) {
  return useQuery({
    queryKey: qk.compare(symbol, aTs ?? '', bTs ?? ''),
    queryFn: ({ signal }) => apiGet<Compare>('/compare', { symbol, aTs, bTs }, signal),
    enabled: !!aTs && !!bTs,
  })
}

export function useCalendar(symbol: string, maxExpiries = 6) {
  return useQuery({
    queryKey: qk.calendar(symbol, maxExpiries),
    queryFn: ({ signal }) => apiGet<Calendar>('/calendar', { symbol, maxExpiries }, signal),
  })
}

export function useMulti(symbols: string) {
  return useQuery({
    queryKey: qk.multi(symbols),
    queryFn: ({ signal }) => apiGet<Multi>('/multi', { symbols }, signal),
    staleTime: 30000,
  })
}

export function useVix() {
  return useQuery({ queryKey: qk.vix(), queryFn: ({ signal }) => apiGet<MacroEnvelope>('/vix', undefined, signal), staleTime: 60000 })
}
export function useFiiDii() {
  return useQuery({ queryKey: qk.fiiDii(), queryFn: ({ signal }) => apiGet<MacroEnvelope>('/fii-dii', undefined, signal), staleTime: 60000 })
}
export function useParticipantOi() {
  return useQuery({ queryKey: qk.participant(), queryFn: ({ signal }) => apiGet<MacroEnvelope>('/participant-oi', undefined, signal), staleTime: 60000 })
}

// ── Strike notes CRUD ───────────────────────────────────────────────────────
export function useNotes(symbol: string) {
  return useQuery({
    queryKey: qk.notes(symbol),
    queryFn: ({ signal }) => apiGet<NotesResponse>('/notes', { symbol }, signal),
  })
}

export function useAddNote(symbol: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { strike: number; body: string; side?: 'CE' | 'PE' | null }) =>
      apiPost<{ id: number }>('/notes', { symbol, ...vars }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.notes(symbol) }),
  })
}

export function useDeleteNote(symbol: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (noteId: number) => {
      const res = await fetch(`/api/notes/${noteId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.notes(symbol) }),
  })
}

/** Force a snapshot ("Snap" button). Bypasses throttle + window server-side. */
export function useForceSnapshot() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { symbol: string; expiry?: string }) =>
      apiPost<OptionChain>('/snapshot', vars),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: qk.optionChain(vars.symbol, vars.expiry) })
      qc.invalidateQueries({ queryKey: qk.snapshots(vars.symbol) })
    },
  })
}
