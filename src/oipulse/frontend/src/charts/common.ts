import { palette, monoFont } from '@/theme'
import { useShell } from '@/store'

/**
 * Shared ECharts styling. Series hues (gold/CE/PE/bull/bear/violet) are
 * theme-constant — only the CHROME (axis text, grid lines, tooltip surface)
 * flips with the theme. Components call `getChrome(theme)` and put the result
 * in their useMemo deps; the two chrome objects are built once, so identity is
 * stable per theme and memos only re-run on an actual toggle.
 */

export const baseGrid = { left: 56, right: 56, top: 28, bottom: 36, containLabel: true }

interface ChromeColors {
  axis: string
  label: string
  split: string
  tooltipBg: string
  tooltipFg: string
  pointer: string
  nameText: string
  heatmapBorder: string
  track: string
}

function buildChrome(c: ChromeColors) {
  const axisLine = { lineStyle: { color: c.axis } }
  const splitLine = { lineStyle: { color: c.split, opacity: 0.5 } }
  const axisLabel = { color: c.label, fontFamily: monoFont, fontSize: 10 }
  return {
    axisLine,
    splitLine,
    axisLabel,
    heatmapBorder: c.heatmapBorder,
    labelColor: c.label,
    fgColor: c.tooltipFg,
    lineColor: c.axis,
    trackColor: c.track,
    legendText: { color: c.label },
    tooltipBase: {
      trigger: 'axis' as const,
      backgroundColor: c.tooltipBg,
      borderColor: c.axis,
      textStyle: { color: c.tooltipFg, fontFamily: monoFont, fontSize: 12 },
      axisPointer: { type: 'cross' as const, lineStyle: { color: c.pointer } },
    },
    dataZoomInside: [
      { type: 'inside' as const, throttle: 50 },
      {
        type: 'slider' as const,
        height: 16,
        bottom: 4,
        borderColor: c.axis,
        fillerColor: 'rgba(34,211,238,0.10)',
        handleStyle: { color: palette.gold },
        textStyle: { color: c.nameText, fontSize: 9 },
      },
    ],
    categoryAxis(data: string[]) {
      return { type: 'category' as const, data, axisLine, axisLabel, axisTick: { show: false } }
    },
    valueAxis(name?: string, opts: Record<string, unknown> = {}) {
      return {
        type: 'value' as const,
        name,
        nameTextStyle: { color: c.nameText, fontSize: 10 },
        axisLine: { show: false },
        axisLabel,
        splitLine,
        ...opts,
      }
    },
  }
}

const DARK = buildChrome({
  axis: palette.line,
  label: palette.fg3,
  split: palette.line,
  tooltipBg: 'rgba(13, 17, 25, 0.94)',
  tooltipFg: palette.fg,
  pointer: palette.fg4,
  nameText: palette.fg4,
  heatmapBorder: palette.bg,
  track: palette.bg3,
})

const LIGHT = buildChrome({
  axis: '#dde2ec',
  label: '#5d6880',
  split: '#dde2ec',
  tooltipBg: 'rgba(255, 255, 255, 0.97)',
  tooltipFg: '#101622',
  pointer: '#8d97ac',
  nameText: '#8d97ac',
  heatmapBorder: '#ffffff',
  track: '#e7ebf3',
})

export type ChartChrome = typeof DARK

export function getChrome(theme: 'dark' | 'light'): ChartChrome {
  return theme === 'light' ? LIGHT : DARK
}

/** Hook form — subscribes to the shell theme so chart options rebuild on toggle. */
export function useChartChrome(): ChartChrome {
  return getChrome(useShell((s) => s.theme))
}

// Back-compat constants (dark) — being phased out; prefer getChrome(theme).
export const axisLine = DARK.axisLine
export const splitLine = DARK.splitLine
export const axisLabel = DARK.axisLabel
export const tooltipBase = DARK.tooltipBase
export const dataZoomInside = DARK.dataZoomInside
export const categoryAxis = DARK.categoryAxis
export const valueAxis = DARK.valueAxis
