import { useShell } from '@/store'
import { palette } from '@/theme'
import { cn } from '@/lib/utils'
import { fmt0, fmt2 } from '@/lib/format'

/** Compact single-line context strip for Option pages. */
export function StatCards() {
  const snap = useShell((s) => s.snap)
  const spotHist = useShell((s) => s.spotHist)

  const spotDelta = (() => {
    if (spotHist.length < 2) return null
    const d = spotHist[spotHist.length - 1].v - spotHist[spotHist.length - 2].v
    return { txt: `${d > 0 ? '+' : ''}${d.toFixed(2)}`, up: d > 0 }
  })()

  const atmIv = snap?.atmCeIV ? `${snap.atmCeIV.toFixed(1)}%` : null
  const pcr = snap?.pcr != null ? fmt2(snap.pcr) : null
  const maxPain = snap?.maxPain != null ? fmt0(snap.maxPain) : null

  return (
    <div className="mx-auto max-w-[1680px] px-4 py-2">
      <div className="flex flex-wrap items-center gap-6 rounded-md border bg-card px-3 py-2 text-xs shadow-xs">
        {snap?.spot != null && (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground uppercase font-mono text-[10px]">Spot</span>
            <span className="font-mono font-semibold text-foreground text-sm" style={{ color: palette.gold }}>
              {fmt2(snap.spot)}
            </span>
            {spotDelta && (
              <span className={cn('font-mono text-[11px]', spotDelta.up ? 'text-profit' : 'text-loss')}>
                {spotDelta.txt}
              </span>
            )}
          </div>
        )}

        {pcr != null && (
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground uppercase font-mono text-[10px]">PCR</span>
            <span className="font-mono font-semibold text-foreground">{pcr}</span>
          </div>
        )}

        {maxPain != null && (
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground uppercase font-mono text-[10px]">Max Pain</span>
            <span className="font-mono font-semibold text-foreground">{maxPain}</span>
          </div>
        )}

        {atmIv != null && (
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground uppercase font-mono text-[10px]">ATM IV</span>
            <span className="font-mono font-semibold text-foreground">{atmIv}</span>
          </div>
        )}
      </div>
    </div>
  )
}
