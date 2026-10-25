import type { ThemeConfig } from 'antd'
import { theme as antdTheme } from 'antd'

/**
 * OBSIDIAN GLASS — the OI Pulse design system.
 *
 * Near-black graphite canvas, translucent glass panels, electric-cyan light.
 * These hexes are the single source of truth for the React app and are also
 * exported as `palette` so chart code (ECharts/lightweight-charts, which can't
 * read CSS vars easily) shares the exact same colors.
 *
 * Key names are kept stable (`gold` = the primary accent) so every consumer
 * reskins without code churn.
 */

export const palette = {
  bg: '#05070b', // the void
  bg1: '#0a0d13', // canvas layer
  bg2: '#0f131b', // panel glass (solid fallback)
  bg3: '#161b26', // raised glass
  line: '#1c2330', // hairline
  line2: '#293245',
  fg: '#eaeef6',
  fg2: '#c4cbda',
  fg3: '#7e89a0',
  fg4: '#4f586d',
  gold: '#22d3ee', // electric cyan — THE interactive light
  goldSoft: '#7debff',
  goldDeep: '#0ea5c4',
  bull: '#3ecf8e', // spring green
  bear: '#ff5470', // signal rose
  ce: '#5b9bff', // periwinkle — call side
  pe: '#ff7e67', // coral — put side (blue/orange pair: colorblind-safe)
  violet: '#a78bfa', // analytical overlays
  amber: '#fbbf24',
  info: '#2dd4bf',
} as const

const fontStack = "'Space Grotesk', system-ui, -apple-system, sans-serif"
export const monoFont = "'IBM Plex Mono', ui-monospace, monospace"

/** Translucent glass fills shared between Ant tokens and CSS. */
const glass = {
  panel: 'rgba(15, 19, 27, 0.72)',
  raised: 'rgba(22, 27, 38, 0.82)',
  overlay: 'rgba(13, 17, 25, 0.92)',
}

export const darkTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
  token: {
    colorPrimary: palette.gold,
    colorInfo: palette.info,
    colorSuccess: palette.bull,
    colorError: palette.bear,
    colorWarning: palette.amber,
    colorBgBase: palette.bg,
    colorTextBase: palette.fg,
    colorBgContainer: glass.panel,
    colorBgElevated: glass.raised,
    colorBgLayout: palette.bg,
    colorBgSpotlight: glass.overlay,
    colorBorder: 'rgba(255, 255, 255, 0.07)',
    colorBorderSecondary: 'rgba(255, 255, 255, 0.05)',
    colorTextSecondary: palette.fg2,
    colorTextTertiary: palette.fg3,
    colorTextQuaternary: palette.fg4,
    colorPrimaryBg: 'rgba(34, 211, 238, 0.10)',
    colorPrimaryBgHover: 'rgba(34, 211, 238, 0.16)',
    borderRadius: 12,
    borderRadiusSM: 8,
    borderRadiusLG: 18,
    controlHeight: 34,
    fontFamily: fontStack,
    fontSize: 14,
    boxShadow: '0 12px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.05)',
    boxShadowSecondary: '0 16px 48px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06)',
    wireframe: false,
  },
  components: {
    Layout: {
      headerBg: 'rgba(5, 7, 11, 0.7)',
      bodyBg: palette.bg,
      headerHeight: 54,
      headerPadding: '0 16px',
    },
    Card: {
      colorBgContainer: glass.panel,
      headerBg: 'transparent',
      paddingLG: 18,
    },
    Button: {
      borderRadius: 999,
      borderRadiusSM: 999,
      borderRadiusLG: 999,
      defaultBg: 'rgba(255,255,255,0.04)',
      defaultBorderColor: 'rgba(255,255,255,0.08)',
      defaultShadow: 'none',
      primaryShadow: '0 0 16px rgba(34,211,238,0.35)',
      fontWeight: 600,
    },
    Select: {
      colorBgContainer: 'rgba(255,255,255,0.04)',
      colorBgElevated: glass.overlay,
      optionSelectedBg: 'rgba(34, 211, 238, 0.12)',
      borderRadius: 8,
      borderRadiusLG: 10,
    },
    Input: {
      colorBgContainer: 'rgba(255,255,255,0.04)',
      borderRadius: 999,
    },
    InputNumber: {
      colorBgContainer: 'rgba(255,255,255,0.04)',
      borderRadius: 10,
    },
    Statistic: {
      contentFontSize: 22,
      titleFontSize: 11,
    },
    Table: {
      headerBg: 'rgba(255,255,255,0.03)',
      colorBgContainer: 'transparent',
      rowHoverBg: 'rgba(34, 211, 238, 0.05)',
      headerSplitColor: 'transparent',
      borderColor: 'rgba(255,255,255,0.05)',
      cellFontSizeSM: 12,
    },
    Tabs: {
      itemColor: palette.fg3,
      itemSelectedColor: palette.gold,
      itemHoverColor: palette.fg,
      inkBarColor: palette.gold,
      titleFontSize: 13,
    },
    Modal: {
      contentBg: glass.overlay,
      headerBg: 'transparent',
      borderRadiusLG: 20,
    },
    Popover: {
      colorBgElevated: glass.overlay,
      borderRadiusLG: 16,
    },
    Tooltip: {
      colorBgSpotlight: glass.overlay,
      borderRadius: 10,
    },
    Tag: {
      borderRadiusSM: 999,
      defaultBg: 'rgba(255,255,255,0.05)',
    },
    Segmented: {
      itemSelectedBg: 'rgba(34, 211, 238, 0.14)',
      trackBg: 'rgba(255,255,255,0.04)',
      borderRadius: 999,
    },
    Slider: {
      handleColor: palette.gold,
      trackBg: palette.goldDeep,
      trackHoverBg: palette.gold,
      railBg: 'rgba(255,255,255,0.08)',
      railHoverBg: 'rgba(255,255,255,0.12)',
    },
    Switch: {
      handleBg: '#dffaff',
    },
    Notification: {
      colorBgElevated: glass.overlay,
      borderRadiusLG: 16,
    },
    Divider: {
      colorSplit: 'rgba(255,255,255,0.06)',
    },
  },
}

/** PORCELAIN GLASS — the light twin. Cool porcelain surfaces, ink text, the
 *  same cyan light running through frosted white panes. */
export const lightTheme: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    colorPrimary: '#0891b2',
    colorInfo: '#0d9488',
    colorSuccess: '#0e9f6e',
    colorError: '#e11d48',
    colorWarning: '#d97706',
    colorBgBase: '#eef1f7',
    colorTextBase: '#101622',
    colorBgContainer: 'rgba(255, 255, 255, 0.78)',
    colorBgElevated: 'rgba(255, 255, 255, 0.92)',
    colorBgLayout: '#eef1f7',
    colorBorder: 'rgba(16, 22, 34, 0.10)',
    colorBorderSecondary: 'rgba(16, 22, 34, 0.06)',
    borderRadius: 12,
    borderRadiusSM: 8,
    borderRadiusLG: 18,
    controlHeight: 34,
    fontFamily: fontStack,
    fontSize: 14,
    boxShadow: '0 10px 28px rgba(31, 41, 60, 0.10), inset 0 1px 0 rgba(255,255,255,0.9)',
    boxShadowSecondary: '0 16px 44px rgba(31, 41, 60, 0.14), inset 0 1px 0 rgba(255,255,255,0.9)',
    wireframe: false,
  },
  components: {
    Card: {
      colorBgContainer: 'rgba(255, 255, 255, 0.78)',
      headerBg: 'transparent',
      paddingLG: 18,
    },
    Button: {
      borderRadius: 999,
      borderRadiusSM: 999,
      borderRadiusLG: 999,
      fontWeight: 600,
    },
    Select: { borderRadius: 8, borderRadiusLG: 10 },
    Input: { borderRadius: 999 },
    Modal: { borderRadiusLG: 20 },
    Popover: { borderRadiusLG: 16 },
    Tag: { borderRadiusSM: 999 },
    Statistic: { contentFontSize: 22, titleFontSize: 11 },
    Table: {
      headerBg: 'rgba(16, 22, 34, 0.03)',
      colorBgContainer: 'transparent',
      rowHoverBg: 'rgba(8, 145, 178, 0.05)',
      headerSplitColor: 'transparent',
      cellFontSizeSM: 12,
    },
  },
}
