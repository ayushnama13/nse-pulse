import { useState, type ReactNode } from 'react'
import { Tooltip } from 'antd'
import {
  AppstoreOutlined,
  AreaChartOutlined,
  BarChartOutlined,
  CalendarOutlined,
  CompassOutlined,
  DashboardOutlined,
  GlobalOutlined,
  HeartOutlined,
  LineChartOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RiseOutlined,
  SlidersOutlined,
  TableOutlined,
  AlertOutlined,
  ApartmentOutlined,
  BankOutlined,
  CodeOutlined,
  DatabaseOutlined,
  EyeOutlined,
  FilterOutlined,
  FundOutlined,
  PieChartOutlined,
  ProfileOutlined,
  ReadOutlined,
  SafetyOutlined,
  StockOutlined,
  SwapOutlined,
  TrophyOutlined,
  WalletOutlined,
} from '@ant-design/icons'
import { useShell } from '@/store'
import { TAB_ORDER, type TabKey } from '@/router'
import { NAV_GROUPS, TAB_LABELS } from '@/nav'
import { Logo } from './Glass'

const ICONS: Record<string, ReactNode> = {
  market: <FundOutlined />, ticker: <StockOutlined />, indices: <LineChartOutlined />, fiidii: <SwapOutlined />,
  deals: <BankOutlined />, screener: <FilterOutlined />, eodchain: <TableOutlined />, news: <ReadOutlined />,
  fdash: <PieChartOutlined />, fcompanies: <ApartmentOutlined />, fcompany: <ProfileOutlined />, fsectors: <AppstoreOutlined />,
  ftop: <TrophyOutlined />, fscreens: <FilterOutlined />, fsql: <CodeOutlined />,
  portfolio: <WalletOutlined />, alerts: <AlertOutlined />, watchlists: <EyeOutlined />,
  dq: <DatabaseOutlined />, fhealth: <SafetyOutlined />,
}
const NAV0: Record<string, { label: string; icon: ReactNode }> = {
  home: { label: 'Home', icon: <CompassOutlined /> },
  chain: { label: 'Option Chain', icon: <TableOutlined /> },
  oi: { label: 'OI & Gamma', icon: <BarChartOutlined /> },
  vol: { label: 'Vol & Skew', icon: <RiseOutlined /> },
  trends: { label: 'Trends', icon: <LineChartOutlined /> },
  analytics: { label: 'Analytics', icon: <DashboardOutlined /> },
  macro: { label: 'Macro', icon: <GlobalOutlined /> },
  multi: { label: 'Multi-Index', icon: <AppstoreOutlined /> },
  compare: { label: 'Compare', icon: <AreaChartOutlined /> },
  pulse: { label: 'Pulse', icon: <HeartOutlined /> },
  calendar: { label: 'Calendar', icon: <CalendarOutlined /> },
  payoff: { label: 'Payoff', icon: <SlidersOutlined /> },
}

const NAV = new Proxy(NAV0, {
  get: (t, k: string) => t[k] ?? { label: TAB_LABELS[k] ?? k, icon: ICONS[k] ?? <AppstoreOutlined /> },
})

const RAIL_KEY = 'oipulse:rail'

/** The glass icon rail — primary navigation. Collapses to icons; expands to
 *  icon + label + shortcut. On mobile (CSS) it becomes a floating bottom dock. */
export function Sidebar() {
  const tab = useShell((s) => s.tab) as TabKey
  const setTab = useShell((s) => s.setTab)
  const [open, setOpen] = useState(() => localStorage.getItem(RAIL_KEY) === '1')

  const toggle = () => {
    setOpen((o) => {
      try {
        localStorage.setItem(RAIL_KEY, o ? '0' : '1')
      } catch {
        /* ignore */
      }
      return !o
    })
  }

  return (
    <nav className={`side-rail${open ? ' open' : ''}`} aria-label="Primary">
      <div className="rail-brand">
        <Logo size={26} />
        <span className="brand-name">
          OI <span style={{ color: 'var(--gold)' }}>Pulse</span>
        </span>
      </div>
      {NAV_GROUPS.map((g) => (
        <div key={g.title}>
          {open && <div className="side-group mono" style={{ fontSize: 10, opacity: 0.5, padding: '10px 14px 2px', textTransform: 'uppercase' }}>{g.title}</div>}
          {!open && <div style={{ height: 1, background: 'var(--border, #ffffff14)', margin: '6px 10px' }} />}
          {g.tabs.map((k) => {
            const i = TAB_ORDER.indexOf(k)
            const item = (
              <div
                key={k}
                role="button"
                tabIndex={0}
                className={`side-item${tab === k ? ' active' : ''}`}
                onClick={() => setTab(k)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') setTab(k)
                }}
              >
                {NAV[k].icon}
                <span className="side-label">{NAV[k].label}</span>
                {i < 9 && <span className="side-key mono">{i + 1}</span>}
              </div>
            )
            return open ? item : <Tooltip key={k} title={NAV[k].label} placement="right">{item}</Tooltip>
          })}
        </div>
      ))}
      <div className="rail-spacer" />
      <div className="side-item rail-toggle" role="button" tabIndex={0} onClick={toggle} onKeyDown={(e) => e.key === 'Enter' && toggle()}>
        {open ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
        <span className="side-label">Collapse</span>
      </div>
    </nav>
  )
}
