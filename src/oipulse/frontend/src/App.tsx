import { Component, lazy, Suspense, useEffect, useState, type ComponentType, type ReactNode } from 'react'
import { ConfigProvider, App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { darkTheme, lightTheme } from './theme'
import { useShell } from './store'
import { useHashSync, type TabKey } from './router'
import { SECTIONS } from './nav'
import { TAB_LABELS, OPTION_TABS } from './nav'
import { useQueryClient } from '@tanstack/react-query'
import { useOptionChain, useForceSnapshot, qk } from './api/queries'
import { subscribeLive } from './api/live'
import { Navbar, MobileBottomNav } from './components/Navbar'
import { SectionBar } from './components/SectionBar'
import { StatCards } from './components/StatCards'
import { CommandPalette } from './components/CommandPalette'
import { ShortcutsHelp } from './components/ShortcutsHelp'
import { GlassEmpty, GlassLoader } from './components/Glass'
import { Placeholder } from './tabs/Placeholder'

const DashboardTab = lazy(() => import('./tabs/DashboardTab').then((m) => ({ default: m.DashboardTab })))
const ToolsTab = lazy(() => import('./tabs/ToolsTab').then((m) => ({ default: m.ToolsTab })))
const HomeTab = lazy(() => import('./tabs/HomeTab').then((m) => ({ default: m.HomeTab })))
const ChainTab = lazy(() => import('./tabs/ChainTab').then((m) => ({ default: m.ChainTab })))
const PulseTab = lazy(() => import('./tabs/PulseTab').then((m) => ({ default: m.PulseTab })))
const TrendsTab = lazy(() => import('./tabs/TrendsTab').then((m) => ({ default: m.TrendsTab })))
const OIGammaTab = lazy(() => import('./tabs/OIGammaTab').then((m) => ({ default: m.OIGammaTab })))
const VolSkewTab = lazy(() => import('./tabs/VolSkewTab').then((m) => ({ default: m.VolSkewTab })))
const AnalyticsTab = lazy(() => import('./tabs/AnalyticsTab').then((m) => ({ default: m.AnalyticsTab })))
const MacroTab = lazy(() => import('./tabs/MacroTab').then((m) => ({ default: m.MacroTab })))
const MultiTab = lazy(() => import('./tabs/MultiTab').then((m) => ({ default: m.MultiTab })))
const CompareTab = lazy(() => import('./tabs/CompareTab').then((m) => ({ default: m.CompareTab })))
const CalendarTab = lazy(() => import('./tabs/CalendarTab').then((m) => ({ default: m.CalendarTab })))
const PayoffTab = lazy(() => import('./tabs/PayoffTab').then((m) => ({ default: m.PayoffTab })))

const MarketTab = lazy(() => import('./tabs/research/EquityTabs').then((m) => ({ default: m.MarketTab })))
const TickerTab = lazy(() => import('./tabs/research/EquityTabs').then((m) => ({ default: m.TickerTab })))
const IndicesTab = lazy(() => import('./tabs/research/EquityTabs').then((m) => ({ default: m.IndicesTab })))
const FiiDiiTab = lazy(() => import('./tabs/research/EquityTabs').then((m) => ({ default: m.FiiDiiTab })))
const DealsTab = lazy(() => import('./tabs/research/EquityTabs').then((m) => ({ default: m.DealsTab })))
const NewsTab = lazy(() => import('./tabs/research/EquityTabs').then((m) => ({ default: m.NewsTab })))
const EodChainTab = lazy(() => import('./tabs/research/EquityTabs').then((m) => ({ default: m.EodChainTab })))
const DataQualityTab = lazy(() => import('./tabs/research/EquityTabs').then((m) => ({ default: m.DataQualityTab })))
const ScreenerTab = lazy(() => import('./tabs/research/EquityTabs').then((m) => ({ default: m.ScreenerTab })))
const FDashTab = lazy(() => import('./tabs/research/FundamentalsTabs').then((m) => ({ default: m.FDashTab })))
const FCompaniesTab = lazy(() => import('./tabs/research/FundamentalsTabs').then((m) => ({ default: m.FCompaniesTab })))
const FCompanyTab = lazy(() => import('./tabs/research/FundamentalsTabs').then((m) => ({ default: m.FCompanyTab })))
const FSectorsTab = lazy(() => import('./tabs/research/FundamentalsTabs').then((m) => ({ default: m.FSectorsTab })))
const FTopTab = lazy(() => import('./tabs/research/FundamentalsTabs').then((m) => ({ default: m.FTopTab })))
const FScreensTab = lazy(() => import('./tabs/research/FundamentalsTabs').then((m) => ({ default: m.FScreensTab })))
const FSqlTab = lazy(() => import('./tabs/research/FundamentalsTabs').then((m) => ({ default: m.FSqlTab })))
const FHealthTab = lazy(() => import('./tabs/research/FundamentalsTabs').then((m) => ({ default: m.FHealthTab })))
const PortfolioTab = lazy(() => import('./tabs/research/PortfolioTabs').then((m) => ({ default: m.PortfolioTab })))
const AlertsTab = lazy(() => import('./tabs/research/PortfolioTabs').then((m) => ({ default: m.AlertsTab })))
const WatchlistsTab = lazy(() => import('./tabs/research/PortfolioTabs').then((m) => ({ default: m.WatchlistsTab })))

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

/** Live data orchestration: WS push (primary) + poll fallback → store.
 *  While WS is healthy the poll relaxes to 60s; push frames are also written
 *  into the query cache so both stay consistent. */
function useLiveData() {
  const symbol = useShell((s) => s.symbol)
  const expiry = useShell((s) => s.expiry)
  const apply = useShell((s) => s.applySnapshot)
  const setLive = useShell((s) => s.setLive)
  const qc = useQueryClient()
  const [transport, setTransport] = useState<'ws' | 'sse'>('sse')
  const { data, error } = useOptionChain(symbol, expiry, transport === 'ws' ? 60000 : 20000)

  useEffect(() => {
    if (data) apply(data, data.stale ? 'stale' : 'live')
  }, [data, apply])
  useEffect(() => {
    if (error) setLive('error')
  }, [error, setLive])
  useEffect(() => {
    const unsub = subscribeLive(
      symbol,
      (snap) => {
        apply(snap)
        // keep the query cache in sync so components reading the hook see pushes
        qc.setQueryData(qk.optionChain(symbol, undefined), snap)
      },
      setTransport,
    )
    return unsub
  }, [symbol, apply, qc])
}

const TAB_COMPONENTS: Partial<Record<TabKey, ComponentType>> = {
  dashboard: DashboardTab,
  tools: ToolsTab,
  home: HomeTab,
  chain: ChainTab,
  pulse: PulseTab,
  trends: TrendsTab,
  oi: OIGammaTab,
  vol: VolSkewTab,
  analytics: AnalyticsTab,
  macro: MacroTab,
  multi: MultiTab,
  compare: CompareTab,
  calendar: CalendarTab,
  payoff: PayoffTab,
  market: MarketTab, ticker: TickerTab, indices: IndicesTab, fiidii: FiiDiiTab, deals: DealsTab, screener: ScreenerTab,
  eodchain: EodChainTab, news: NewsTab, dq: DataQualityTab,
  fdash: FDashTab, fcompanies: FCompaniesTab, fcompany: FCompanyTab, fsectors: FSectorsTab, ftop: FTopTab,
  fscreens: FScreensTab, fsql: FSqlTab, fhealth: FHealthTab,
  portfolio: PortfolioTab, alerts: AlertsTab, watchlists: WatchlistsTab,
}

/** One tab crashing must never black out the shell — contain it, keep the
 *  rest of the terminal alive. Keyed by tab so navigation resets the error. */
class TabBoundary extends Component<{ children: ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null }
  static getDerivedStateFromError(err: Error) {
    return { err }
  }
  render() {
    if (this.state.err) {
      return (
        <GlassEmpty
          description={
            <span>
              This view hit an error and was contained — the rest of the app is fine.
              <br />
              <code style={{ fontSize: 11 }}>{String(this.state.err)}</code>
            </span>
          }
        />
      )
    }
    return this.props.children
  }
}

function Panel() {
  const tab = useShell((s) => s.tab) as TabKey
  const Comp = TAB_COMPONENTS[tab]
  return (
    <TabBoundary key={tab}>
      <Suspense fallback={<GlassLoader pad={72} />}>{Comp ? <Comp /> : <Placeholder name={TAB_LABELS[tab]} />}</Suspense>
    </TabBoundary>
  )
}

function Shell() {
  useHashSync()
  useLiveData()
  const live = useShell((s) => s.live)
  const tab = useShell((s) => s.tab)
  const setTab = useShell((s) => s.setTab)
  const symbol = useShell((s) => s.symbol)
  const expiry = useShell((s) => s.expiry)
  const theme = useShell((s) => s.theme)
  const density = useShell((s) => s.density)
  const force = useForceSnapshot()
  const snapNow = force.mutate // stable across renders (TanStack v5)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)

  // reflect theme/density on <html> for CSS hooks
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.dataset.density = density === 'compact' ? 'compact' : 'comfortable'
  }, [theme, density])

  // keyboard shortcuts: Ctrl/⌘+K palette, 1–7 sections, S snapshot, ? help
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
        return
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const t = e.target as HTMLElement
      if (t && ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) return
      if (e.key >= '1' && e.key <= '9') {
        const sec = SECTIONS[parseInt(e.key, 10) - 1]
        if (sec) setTab(sec.tabs[0])
      } else if (e.key === 's' || e.key === 'S') {
        snapNow({ symbol, expiry })
      } else if (e.key === '?') {
        setHelpOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setTab, snapNow, symbol, expiry])

  return (
    <div className={`min-h-full pb-14 md:pb-0${live === 'stale' ? ' app-stale' : ''}`}>
      <Navbar onSearch={() => setPaletteOpen(true)} onHelp={() => setHelpOpen(true)} />
      <SectionBar />
      <main className="app-main" key={tab}>
        {tab !== 'home' && OPTION_TABS.includes(tab) && <StatCards />}
        <Panel />
      </main>
      <MobileBottomNav />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <ShortcutsHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}

export default function App() {
  const theme = useShell((s) => s.theme)
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider theme={theme === 'dark' ? darkTheme : lightTheme}>
        <AntApp>
          <Shell />
        </AntApp>
      </ConfigProvider>
    </QueryClientProvider>
  )
}
