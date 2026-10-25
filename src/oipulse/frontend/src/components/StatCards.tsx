import { Card } from 'antd'
import { useShell } from '@/store'
import { fmt, fmt0, fmt2 } from '@/lib/format'
import { Sparkline } from './Sparkline'
import { palette } from '@/theme'

/** The 9-stat header strip: Spot, Max Pain, OI PCR, Vol PCR, WPCR ₹,
 *  Top Resistance, Top Support, Total CE OI, Total PE OI. */
export function StatCards() {
  const snap = useShell((s) => s.snap)
  const wpcr = useShell((s) => s.wpcr)
  const spotHist = useShell((s) => s.spotHist)
  const pcrHist = useShell((s) => s.pcrHist)
  const volPcrHist = useShell((s) => s.volPcrHist)

  // Top resistance = strike with most CE OI; top support = most PE OI.
  let topRes = 0
  let topSup = 0
  let resOI = -1
  let supOI = -1
  for (const r of snap?.chain ?? []) {
    if (r.ceOI > resOI) {
      resOI = r.ceOI
      topRes = r.strike
    }
    if (r.peOI > supOI) {
      supOI = r.peOI
      topSup = r.strike
    }
  }

  const pcrColor = (v: number) => (v > 1.2 ? palette.bull : v < 0.8 ? palette.bear : 'var(--fg)')

  const deltaOf = (hist: typeof spotHist, digits = 2): { txt: string; up: boolean } | undefined => {
    if (hist.length < 2) return undefined
    const d = hist[hist.length - 1].v - hist[hist.length - 2].v
    if (d === 0) return undefined
    return { txt: `${d > 0 ? '+' : ''}${d.toFixed(digits)}`, up: d > 0 }
  }

  const cards: {
    title: string
    value: string
    color?: string
    spark?: { data: typeof spotHist; color: string }
    delta?: { txt: string; up: boolean }
  }[] = [
    { title: 'SPOT', value: fmt2(snap?.spot), color: palette.gold, spark: { data: spotHist, color: palette.gold }, delta: deltaOf(spotHist) },
    { title: 'MAX PAIN', value: fmt0(snap?.maxPain) },
    { title: 'OI PCR', value: fmt2(snap?.pcr), color: pcrColor(snap?.pcr ?? 1), spark: { data: pcrHist, color: pcrColor(snap?.pcr ?? 1) }, delta: deltaOf(pcrHist) },
    { title: 'VOL PCR', value: fmt2(snap?.volPcr), color: pcrColor(snap?.volPcr ?? 1), spark: { data: volPcrHist, color: pcrColor(snap?.volPcr ?? 1) } },
    { title: 'WPCR ₹', value: fmt2(wpcr), color: pcrColor(wpcr) },
    { title: 'TOP RESISTANCE', value: topRes ? fmt0(topRes) : '—', color: palette.ce },
    { title: 'TOP SUPPORT', value: topSup ? fmt0(topSup) : '—', color: palette.pe },
    { title: 'TOTAL CE OI', value: fmt(snap?.totalCEOI), color: palette.ce },
    { title: 'TOTAL PE OI', value: fmt(snap?.totalPEOI), color: palette.pe },
  ]

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: 10,
        marginBottom: 14,
      }}
    >
      {cards.map((c) => (
        <Card key={c.title} size="small" styles={{ body: { padding: '10px 12px' } }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
            <div>
              <div className="microlabel" style={{ marginBottom: 3 }}>{c.title}</div>
              <span
                key={c.value}
                className="mono tick-flash"
                style={{ color: c.color ?? 'var(--fg)', fontSize: 21, fontWeight: 600, lineHeight: 1.15 }}
              >
                {c.value}
              </span>
              {c.delta && (
                <div className="mono" style={{ fontSize: 11, color: c.delta.up ? palette.bull : palette.bear }}>
                  {c.delta.txt}
                </div>
              )}
            </div>
            {c.spark && c.spark.data.length > 1 && <Sparkline data={c.spark.data} color={c.spark.color} />}
          </div>
        </Card>
      ))}
    </div>
  )
}
