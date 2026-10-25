import { create } from 'zustand'
import { useShell } from '@/store'

/** Selected equity / company symbol shared by the Ticker and Company pages. */
export const useEq = create<{ symbol: string; set: (s: string) => void }>((set) => ({
  symbol: 'RELIANCE',
  set: (symbol) => set({ symbol: symbol.toUpperCase() }),
}))

export function openTicker(sym: string) {
  useEq.getState().set(sym)
  useShell.getState().setTab('ticker')
}
export function openCompany(sym: string) {
  useEq.getState().set(sym)
  useShell.getState().setTab('fcompany')
}
