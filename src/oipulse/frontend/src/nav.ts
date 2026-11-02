/** Single source of truth for navigation: 6 top-level menus → tab keys. */
export interface MenuItem {
  key: string
  label: string
  description: string
}

export interface MenuGroup {
  title?: string
  items: MenuItem[]
}

export interface Menu {
  key: string
  label: string
  link?: string
  groups?: MenuGroup[]
  items?: MenuItem[]
}

export const MENUS: Menu[] = [
  {
    key: 'home',
    label: 'Home',
    link: 'dashboard',
    items: [{ key: 'dashboard', label: 'Dashboard', description: 'Main application dashboard and overview' }]
  },
  {
    key: 'market',
    label: 'Market',
    items: [
      { key: 'market', label: 'Market', description: 'NSE broad market sentiment and advance-decline' },
      { key: 'indices', label: 'Indices', description: 'Sectoral and benchmark index performance' },
      { key: 'fiidii', label: 'FII / DII', description: 'Institutional daily buying and selling flows' },
      { key: 'deals', label: 'Deals', description: 'Significant block and bulk deals executed' },
      { key: 'news', label: 'News', description: 'Live financial news and market updates' },
      { key: 'delivery', label: 'Delivery', description: 'Scrip-wise delivery volume and accumulation' },
      { key: 'restrictions', label: 'Bans & Bands', description: 'F&O ban list and circuit filters' },
      { key: 'fiideriv', label: 'FII Derivatives', description: 'FII futures and options open interest trends' },
    ]
  },
  {
    key: 'options',
    label: 'Options',
    groups: [
      {
        title: 'Live',
        items: [
          { key: 'home', label: 'Overview', description: 'Live option chain summary and market pulse' },
          { key: 'chain', label: 'Option Chain', description: 'Full options chain with Greeks and OI buildup' },
          { key: 'pulse', label: 'Pulse', description: 'Real-time momentum and order flow tracking' },
          { key: 'multi', label: 'Multi-Index', description: 'Cross-index option comparison and spread tracker' },
        ]
      },
      {
        title: 'Analysis',
        items: [
          { key: 'oi', label: 'OI & Gamma', description: 'Open interest distribution and gamma exposure' },
          { key: 'vol', label: 'Vol & Skew', description: 'Implied volatility surface and smile skews' },
          { key: 'trends', label: 'Trends', description: 'Intraday OI build-up and price-action trends' },
          { key: 'analytics', label: 'Analytics', description: 'Advanced analytics, PCR, and max pain analysis' },
          { key: 'macro', label: 'Macro', description: 'Economic indicators and macro correlation' },
        ]
      },
      {
        title: 'Tools',
        items: [
          { key: 'compare', label: 'Compare', description: 'Compare strike data across multiple expiries/symbols' },
          { key: 'calendar', label: 'Calendar', description: 'Expiry calendar and event tracker' },
          { key: 'payoff', label: 'Payoff', description: 'Multi-leg options strategy payoff calculator' },
          { key: 'eodchain', label: 'EOD Chain', description: 'End-of-day historical option chain data' },
        ]
      }
    ]
  },
  {
    key: 'stocks',
    label: 'Stocks',
    items: [
      { key: 'ticker', label: 'Ticker', description: 'Single stock deep-dive and technical indicators' },
      { key: 'screener', label: 'Equity Screener', description: 'Filter stocks by fundamental and technical metrics' },
      { key: 'watchlists', label: 'Watchlists', description: 'Custom stock watchlists and price alerts' },
      { key: 'portfolio', label: 'Holdings', description: 'Portfolio holdings and position tracking' },
      { key: 'alerts', label: 'Alerts', description: 'Live market alerts and threshold triggers' },
      { key: 'insider', label: 'Insider & SAST', description: 'Insider trading and promoter shareholding disclosures' },
      { key: 'pledge', label: 'Promoter Pledge', description: 'Promoter pledged shares and risk analysis' },
    ]
  },
  {
    key: 'fundamentals',
    label: 'Fundamentals',
    items: [
      { key: 'fdash', label: 'Overview', description: 'Fundamentals dashboard and valuation overview' },
      { key: 'fcompanies', label: 'Companies', description: 'Comprehensive list of listed companies' },
      { key: 'fcompany', label: 'Company', description: 'Detailed financial statements and ratios' },
      { key: 'fsectors', label: 'Sectors', description: 'Sector-wise financial performance and metrics' },
      { key: 'ftop', label: 'Top Scored', description: 'Top fundamentally scored companies' },
      { key: 'fscreens', label: 'Screens', description: 'Fundamental screening presets' },
      { key: 'fsql', label: 'SQL', description: 'Custom SQL query runner for fundamental data' },
    ]
  },
  {
    key: 'reference',
    label: 'Reference',
    items: [
      { key: 'ipo', label: 'IPOs', description: 'Upcoming, ongoing, and past IPO performance' },
      { key: 'etf', label: 'ETFs', description: 'Exchange Traded Funds tracking and comparison' },
      { key: 'dq', label: 'Data Quality', description: 'System data health and freshness checks' },
      { key: 'fhealth', label: 'Fundamentals Health', description: 'Database integrity and ingest status' },
    ]
  },
]

export const TOOL_TABS = ['compare', 'calendar', 'payoff', 'eodchain'] as const
export const SYSTEM_TABS = ['dq', 'fhealth'] as const

export const TAB_LABELS: Record<string, string> = {
  dashboard: 'Dashboard', tools: 'Tools',
  home: 'Overview', chain: 'Option Chain', oi: 'OI & Gamma', vol: 'Vol & Skew', trends: 'Trends', analytics: 'Analytics',
  macro: 'Macro', multi: 'Multi-Index', compare: 'Compare', pulse: 'Pulse', calendar: 'Calendar', payoff: 'Payoff',
  market: 'Market', ticker: 'Ticker', indices: 'Indices', fiidii: 'FII / DII', deals: 'Deals', screener: 'Equity Screener',
  eodchain: 'EOD Chain', news: 'News',
  delivery: 'Delivery', restrictions: 'Bans & Bands', fiideriv: 'FII Derivatives', insider: 'Insider & SAST', pledge: 'Promoter Pledge',
  fdash: 'Overview', fcompanies: 'Companies', fcompany: 'Company', fsectors: 'Sectors', ftop: 'Top Scored',
  fscreens: 'Screens', fsql: 'SQL',
  portfolio: 'Holdings', alerts: 'Alerts', watchlists: 'Watchlists',
  ipo: 'IPOs', etf: 'ETFs', dq: 'Data Quality', fhealth: 'Fundamentals Health',
}

export const SECTIONS = MENUS.map((m) => {
  let tabs: string[] = []
  if (m.link) tabs = [m.link]
  else if (m.items) tabs = m.items.map((i) => i.key)
  else if (m.groups) tabs = m.groups.flatMap((g) => g.items.map((i) => i.key))
  return { key: m.key, label: m.label, tabs }
})

export type SectionKey = (typeof MENUS)[number]['key']

export const NAV_GROUPS = [
  ...SECTIONS.map((s) => ({ title: s.label, tabs: s.tabs })),
  { title: 'Hub', tabs: ['tools'] },
  { title: 'System', tabs: SYSTEM_TABS },
] as const

export function sectionOf(tab: string): SectionKey {
  if (tab === 'dashboard') return 'home'
  for (const m of MENUS) {
    if (m.link === tab) return m.key as SectionKey
    if (m.items && m.items.some((i) => i.key === tab)) return m.key as SectionKey
    if (m.groups && m.groups.some((g) => g.items.some((i) => i.key === tab))) return m.key as SectionKey
  }
  if (['tools', 'dq', 'fhealth'].includes(tab)) return 'reference'
  return 'options'
}

export const OPTION_TABS: readonly string[] = [
  'home', 'chain', 'pulse', 'multi', 'oi', 'vol', 'trends', 'analytics', 'macro', 'compare', 'calendar', 'payoff', 'eodchain'
]
