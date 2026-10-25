/** Single source of truth for navigation: sections → tab keys. */
export const NAV_GROUPS = [
  { title: 'Options', tabs: ['home', 'chain', 'oi', 'vol', 'trends', 'analytics', 'macro', 'multi', 'compare', 'pulse', 'calendar', 'payoff'] },
  { title: 'Equities', tabs: ['market', 'ticker', 'indices', 'fiidii', 'deals', 'screener', 'eodchain', 'news'] },
  { title: 'Fundamentals', tabs: ['fdash', 'fcompanies', 'fcompany', 'fsectors', 'ftop', 'fscreens', 'fsql'] },
  { title: 'Portfolio', tabs: ['portfolio', 'alerts', 'watchlists'] },
  { title: 'System', tabs: ['dq', 'fhealth'] },
] as const

export const TAB_LABELS: Record<string, string> = {
  home: 'Home', chain: 'Option Chain', oi: 'OI & Gamma', vol: 'Vol & Skew', trends: 'Trends', analytics: 'Analytics',
  macro: 'Macro', multi: 'Multi-Index', compare: 'Compare', pulse: 'Pulse', calendar: 'Calendar', payoff: 'Payoff',
  market: 'Market', ticker: 'Ticker', indices: 'Indices', fiidii: 'FII / DII', deals: 'Deals', screener: 'Screener',
  eodchain: 'EOD Chain', news: 'News',
  fdash: 'Overview', fcompanies: 'Companies', fcompany: 'Company', fsectors: 'Sectors', ftop: 'Top Scored',
  fscreens: 'Screens', fsql: 'SQL',
  portfolio: 'Portfolio', alerts: 'Alerts', watchlists: 'Watchlists',
  dq: 'Data Quality', fhealth: 'Fundamentals Health',
}

/** Tabs driven by the live option-chain feed (show the headline stat strip). */
export const OPTION_TABS: readonly string[] = NAV_GROUPS[0].tabs
