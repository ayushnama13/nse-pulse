import { useMemo } from 'react'
import type { HistPoint } from '@/store'
import { palette } from '@/theme'

/** Minimal inline-SVG sparkline for the header stat cards. */
export function Sparkline({
  data,
  color = palette.gold,
  width = 72,
  height = 22,
}: {
  data: HistPoint[]
  color?: string
  width?: number
  height?: number
}) {
  const d = useMemo(() => {
    if (data.length < 2) return ''
    const vals = data.map((p) => p.v)
    const min = Math.min(...vals)
    const max = Math.max(...vals)
    const span = max - min || 1
    const stepX = width / (data.length - 1)
    return vals
      .map((v, i) => {
        const x = i * stepX
        const y = height - ((v - min) / span) * (height - 2) - 1
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }, [data, width, height])

  if (!d) return <svg width={width} height={height} aria-hidden />
  return (
    <svg width={width} height={height} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}
