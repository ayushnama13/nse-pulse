import type { ThemeConfig } from 'antd'
import { theme as antdTheme } from 'antd'

/**
 * Design tokens, aligned with the neutral shadcn palette in index.css.
 * `palette` is the dark-mode set as plain hex because ECharts and
 * lightweight-charts can't read CSS variables; `gold` is the interactive
 * accent (kept under that name so chart code needn't change).
 */
export const palette = {
  bg: '#0a0a0a',
  bg1: '#111111',
  bg2: '#171717',
  bg3: '#262626',
  line: '#262626',
  line2: '#404040',
  fg: '#fafafa',
  fg2: '#d4d4d4',
  fg3: '#a3a3a3',
  fg4: '#737373',
  gold: '#60a5fa',
  goldSoft: '#93c5fd',
  goldDeep: '#3b82f6',
  bull: '#4ade80',
  bear: '#f87171',
  ce: '#60a5fa',
  pe: '#fb923c',
  violet: '#a78bfa',
  amber: '#fbbf24',
  info: '#2dd4bf',
} as const

const fontStack = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
export const monoFont = "ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace"

const shared = {
  borderRadius: 8,
  borderRadiusSM: 6,
  borderRadiusLG: 10,
  controlHeight: 34,
  fontFamily: fontStack,
  fontSize: 14,
  wireframe: false,
}

export const darkTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
  token: {
    ...shared,
    colorPrimary: '#fafafa',
    colorInfo: palette.gold,
    colorSuccess: palette.bull,
    colorError: palette.bear,
    colorWarning: palette.amber,
    colorBgBase: palette.bg,
    colorTextBase: palette.fg,
    colorBgContainer: palette.bg2,
    colorBgElevated: palette.bg2,
    colorBgLayout: palette.bg,
    colorBorder: 'rgba(255,255,255,0.12)',
    colorBorderSecondary: 'rgba(255,255,255,0.08)',
    colorTextSecondary: palette.fg2,
    colorTextTertiary: palette.fg3,
    colorTextQuaternary: palette.fg4,
    boxShadow: '0 4px 12px rgba(0,0,0,0.45)',
  },
  components: {
    Button: { primaryColor: '#171717', defaultShadow: 'none', primaryShadow: 'none', fontWeight: 500 },
    Card: { headerBg: 'transparent' },
    Table: { headerBg: palette.bg3, colorBgContainer: 'transparent', rowHoverBg: 'rgba(255,255,255,0.04)', cellFontSizeSM: 12 },
    Tabs: { itemSelectedColor: palette.fg, inkBarColor: palette.fg, itemHoverColor: palette.fg },
    Segmented: { itemSelectedBg: palette.bg3, trackBg: palette.bg1 },
    Statistic: { contentFontSize: 22, titleFontSize: 12 },
  },
}

export const lightTheme: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    ...shared,
    colorPrimary: '#171717',
    colorInfo: '#2563eb',
    colorSuccess: '#16a34a',
    colorError: '#dc2626',
    colorWarning: '#d97706',
    colorBgBase: '#ffffff',
    colorTextBase: '#0a0a0a',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgLayout: '#ffffff',
    colorBorder: '#e5e5e5',
    colorBorderSecondary: '#efefef',
    boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
  },
  components: {
    Button: { defaultShadow: 'none', primaryShadow: 'none', fontWeight: 500 },
    Card: { headerBg: 'transparent' },
    Table: { headerBg: '#f5f5f5', colorBgContainer: 'transparent', cellFontSizeSM: 12 },
    Tabs: { itemSelectedColor: '#0a0a0a', inkBarColor: '#0a0a0a' },
    Statistic: { contentFontSize: 22, titleFontSize: 12 },
  },
}
