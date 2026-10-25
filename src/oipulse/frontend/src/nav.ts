/** Single source of truth for navigation: top-bar sections → tab keys. */
export const SECTIONS = [
  { key: 'dashboard', label: 'Dashboard', tabs: ['dashboard'] },
  { key: 'options', label: 'Options', tabs: ['home', 'chain', 'oi', 'vol', 'trends', 'analytics', 'macro', 'pulse', 'multi'] },
  { key: 'equities', label: 'Equities', tabs: ['market', 'ticker', 'indices', 'fiidii', 'deals', 'news'] },
  { key: 'fundamentals', label: 'Fundamentals', tabs: ['fdash', 'fcompanies', 'fcompany', 'fsectors', 'ftop'] },
  { key: 'screener', label: 'Screener', tabs: ['screener', 'fscreens', 'fsql'] },
  { key: 'portfolio', label: 'Portfolio', tabs: ['portfolio', 'alerts', 'watchlists'] },
  { key: 'tools', label: 'Tools', tabs: ['tools'] },
] as const

export type SectionKey = (typeof SECTIONS)[number]['key']

/** Rarely used pages: reachable from the Tools hub (and Ctrl-K), not the tab strips. */
export const TOOL_TABS = ['compare', 'calendar', 'payoff', 'eodchain'] as const
/** Housekeeping pages: profile menu. */
export const SYSTEM_TABS = ['dq', 'fhealth'] as const

export const NAV_GROUPS = [
  ...SECTIONS.map((s) => ({ title: s.label, tabs: s.tabs })),
  { title: 'Hub', tabs: TOOL_TABS },
  { title: 'System', tabs: SYSTEM_TABS },
] as const

export const TAB_LABELS: Record<string, string> = {
  dashboard: 'Dashboard', tools: 'Tools',
  home: 'Overview', chain: 'Option Chain', oi: 'OI & Gamma', vol: 'Vol & Skew', trends: 'Trends', analytics: 'Analytics',
  macro: 'Macro', multi: 'Multi-Index', compare: 'Compare', pulse: 'Pulse', calendar: 'Calendar', payoff: 'Payoff',
  market: 'Market', ticker: 'Ticker', indices: 'Indices', fiidii: 'FII / DII', deals: 'Deals', screener: 'Equity Screener',
  eodchain: 'EOD Chain', news: 'News',
  fdash: 'Overview', fcompanies: 'Companies', fcompany: 'Company', fsectors: 'Sectors', ftop: 'Top Scored',
  fscreens: 'Screens', fsql: 'SQL',
  portfolio: 'Holdings', alerts: 'Alerts', watchlists: 'Watchlists',
  dq: 'Data Quality', fhealth: 'Fundamentals Health',
}

export function sectionOf(tab: string): SectionKey {
  for (const s of SECTIONS) if ((s.tabs as readonly string[]).includes(tab)) return s.key
  return 'tools' // TOOL_TABS / SYSTEM_TABS sit under the Tools hub
}

/** Tabs driven by the live option-chain feed (show the headline stat strip). */
export const OPTION_TABS: readonly string[] = SECTIONS[1].tabs
