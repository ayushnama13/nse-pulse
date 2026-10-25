import { useMemo, useState, useRef, useEffect } from 'react'
import { GlassEmpty } from '@/components/Glass'
import { AgGridReact } from 'ag-grid-react'
import {
  ModuleRegistry,
  AllCommunityModule,
  themeQuartz,
  type ColDef,
  type ColGroupDef,
  type ICellRendererParams,
  type RowClassParams,
  type CellClickedEvent,
} from 'ag-grid-community'
import { Segmented, Select, Card, Space } from 'antd'
import { NotesStrip } from '@/components/NotesStrip'
import { useShell } from '@/store'
import type { ChainRow } from '@/api/types'
import { fmt, fmt2, fmtSigned } from '@/lib/format'
import { nearestATM, topRanks } from '@/lib/analytics'
import { palette } from '@/theme'

ModuleRegistry.registerModules([AllCommunityModule])

/* Glass grid: rows stay translucent so the blurred slab behind shows through
   (.chain-grid .ag-root-wrapper in styles.css provides the glass). */
const GRID_THEMES = {
  dark: themeQuartz.withParams({
    backgroundColor: 'rgba(15, 19, 27, 0.01)',
    foregroundColor: palette.fg2,
    headerBackgroundColor: 'rgba(255, 255, 255, 0.03)',
    headerTextColor: palette.fg3,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    rowHoverColor: 'rgba(34, 211, 238, 0.05)',
    accentColor: palette.gold,
    oddRowBackgroundColor: 'rgba(255, 255, 255, 0.015)',
    fontFamily: "'IBM Plex Mono', ui-monospace, monospace",
    fontSize: 12.5,
    headerFontSize: 10.5,
    wrapperBorderRadius: 16,
  }),
  light: themeQuartz.withParams({
    backgroundColor: 'rgba(255, 255, 255, 0.01)',
    foregroundColor: '#101622',
    headerBackgroundColor: 'rgba(16, 22, 34, 0.03)',
    headerTextColor: '#5d6880',
    borderColor: 'rgba(16, 22, 34, 0.07)',
    rowHoverColor: 'rgba(8, 145, 178, 0.05)',
    accentColor: '#0891b2',
    oddRowBackgroundColor: 'rgba(16, 22, 34, 0.015)',
    fontFamily: "'IBM Plex Mono', ui-monospace, monospace",
    fontSize: 12.5,
    headerFontSize: 10.5,
    wrapperBorderRadius: 16,
  }),
}

const ATM_RANGES = [
  { label: '±200', value: 200 },
  { label: '±300', value: 300 },
  { label: '±500', value: 500 },
  { label: '±1000', value: 1000 },
  { label: 'All', value: 0 },
]

const BUILDUPS = [
  { label: 'Any buildup', value: 'all' },
  { label: 'CE Short Buildup', value: 'ce-build' },
  { label: 'CE Short Covering', value: 'ce-cover' },
  { label: 'PE Long Buildup', value: 'pe-build' },
  { label: 'PE Long Unwinding', value: 'pe-unwind' },
]

/** Inline OI cell: number + a faint proportional bar tinted CE/PE. */
function makeOICell(side: 'ce' | 'pe', maxOI: number) {
  return function OICell(p: ICellRendererParams<ChainRow, number>) {
    const v = p.value ?? 0
    const pct = maxOI > 0 ? Math.min(100, (v / maxOI) * 100) : 0
    const tint = side === 'ce' ? 'rgba(59,130,246,0.18)' : 'rgba(239,68,68,0.18)'
    return (
      <div style={{ position: 'relative', width: '100%', textAlign: 'right' }} className="mono">
        <div
          style={{
            position: 'absolute',
            inset: 0,
            width: `${pct}%`,
            background: tint,
            borderRadius: 3,
            [side === 'ce' ? 'right' : 'left']: 0,
          }}
        />
        <span style={{ position: 'relative' }}>{fmt(v)}</span>
      </div>
    )
  }
}

export function ChainTab() {
  const snap = useShell((s) => s.snap)
  const theme = useShell((s) => s.theme)
  const pinned = useShell((s) => s.pinned)
  const togglePin = useShell((s) => s.togglePin)
  const [atmRange, setAtmRange] = useState(500)
  const [buildup, setBuildup] = useState('all')
  const gridRef = useRef<AgGridReact<ChainRow>>(null)
  const scrolledRef = useRef<string | null>(null)

  const chain = snap?.chain ?? []
  const spot = snap?.spot ?? null
  const atm = useMemo(() => nearestATM(chain, spot), [chain, spot])

  const maxCeOI = useMemo(() => chain.reduce((m, r) => Math.max(m, r.ceOI), 0), [chain])
  const maxPeOI = useMemo(() => chain.reduce((m, r) => Math.max(m, r.peOI), 0), [chain])

  // Top-5 highlight maps per column (legacy parity).
  const ranks = useMemo(
    () => ({
      ceOI: topRanks(chain, 'ceOI', 5),
      ceChg: topRanks(chain, 'ceChg', 5, true),
      peOI: topRanks(chain, 'peOI', 5),
      peChg: topRanks(chain, 'peChg', 5, true),
    }),
    [chain],
  )

  const rows = useMemo(() => {
    let r = chain
    if (atmRange > 0 && atm != null) r = r.filter((x) => Math.abs(x.strike - atm) <= atmRange)
    switch (buildup) {
      case 'ce-build':
        r = r.filter((x) => x.ceChg > 0)
        break
      case 'ce-cover':
        r = r.filter((x) => x.ceChg < 0)
        break
      case 'pe-build':
        r = r.filter((x) => x.peChg > 0)
        break
      case 'pe-unwind':
        r = r.filter((x) => x.peChg < 0)
        break
    }
    return r
  }, [chain, atmRange, atm, buildup])

  const columnDefs = useMemo<(ColDef<ChainRow> | ColGroupDef<ChainRow>)[]>(() => {
    // ITM fade (legacy parity): CE is ITM below spot, PE is ITM above spot.
    const itm = (side: 'ce' | 'pe', strike: number) =>
      spot != null && (side === 'ce' ? strike < spot : strike > spot) ? 'itm' : ''
    const num = (field: keyof ChainRow, side: 'ce' | 'pe'): ColDef<ChainRow> => ({
      field,
      headerName: '',
      minWidth: 96,
      flex: 1,
      cellClass: (p) => ['mono', itm(side, p.data!.strike)].filter(Boolean).join(' '),
    })
    const deltaCell = (field: 'ceChg' | 'peChg'): ColDef<ChainRow> => ({
      ...num(field, field === 'ceChg' ? 'ce' : 'pe'),
      valueFormatter: (p) => fmtSigned(p.value),
      cellClass: (p) => {
        const v = (p.value as number) ?? 0
        const side = field === 'ceChg' ? 'ce' : 'pe'
        const cls = ['mono', v > 0 ? 'bull' : v < 0 ? 'bear' : '', itm(side as 'ce' | 'pe', p.data!.strike)]
        if (ranks[field].has(p.data!.strike)) cls.push('top-oi')
        return cls.filter(Boolean).join(' ')
      },
    })
    return [
      {
        headerName: 'CALLS',
        children: [
          {
            ...num('ceOI', 'ce'),
            headerName: 'OI',
            cellRenderer: makeOICell('ce', maxCeOI),
            cellClass: (p) => [itm('ce', p.data!.strike), ranks.ceOI.has(p.data!.strike) ? 'top-oi' : ''].filter(Boolean).join(' '),
          },
          deltaCell('ceChg'),
          { ...num('ceLTP', 'ce'), headerName: 'LTP', valueFormatter: (p) => fmt2(p.value) },
          { ...num('ceIV', 'ce'), headerName: 'IV', minWidth: 70, flex: 0.8, valueFormatter: (p) => fmt2(p.value) },
        ],
      },
      {
        headerName: '',
        children: [
          {
            field: 'strike',
            headerName: 'STRIKE',
            width: 92,
            pinned: undefined,
            cellClass: 'mono',
            cellStyle: { fontWeight: 700, color: palette.gold, textAlign: 'center' },
            headerClass: 'strike-header',
          },
        ],
      },
      {
        headerName: 'PUTS',
        children: [
          { ...num('peIV', 'pe'), headerName: 'IV', minWidth: 70, flex: 0.8, valueFormatter: (p) => fmt2(p.value) },
          { ...num('peLTP', 'pe'), headerName: 'LTP', valueFormatter: (p) => fmt2(p.value) },
          deltaCell('peChg'),
          {
            ...num('peOI', 'pe'),
            headerName: 'OI',
            cellRenderer: makeOICell('pe', maxPeOI),
            cellClass: (p) => [itm('pe', p.data!.strike), ranks.peOI.has(p.data!.strike) ? 'top-oi' : ''].filter(Boolean).join(' '),
          },
        ],
      },
    ]
  }, [maxCeOI, maxPeOI, ranks, spot])

  const rowClassRules = useMemo(
    () => ({
      'atm-row': (p: RowClassParams<ChainRow>) => atm != null && p.data?.strike === atm,
      'pinned-row': (p: RowClassParams<ChainRow>) => p.data != null && pinned.includes(p.data.strike),
    }),
    [atm, pinned],
  )

  const onCellClicked = (e: CellClickedEvent<ChainRow>) => {
    if (e.colDef.field === 'strike' && e.data) togglePin(e.data.strike)
  }

  // ATM auto-scroll — once per symbol, when the grid has rows (legacy parity).
  const symbol = snap?.symbol ?? ''
  useEffect(() => {
    if (!symbol || atm == null || scrolledRef.current === symbol) return
    const api = gridRef.current?.api
    if (!api) return
    const node = api.getRowNode(String(atm))
    if (node) {
      api.ensureNodeVisible(node, 'middle')
      scrolledRef.current = symbol
    }
  }, [symbol, atm, rows])

  if (!chain.length) {
    return (
      <Card size="small">
        <GlassEmpty description="Waiting for the first option-chain frame…" />
      </Card>
    )
  }

  return (
    <Card size="small" styles={{ body: { padding: 12 } }}>
      <NotesStrip />
      <Space style={{ marginBottom: 10 }} wrap>
        <Segmented
          options={ATM_RANGES}
          value={atmRange}
          onChange={(v) => setAtmRange(v as number)}
          size="small"
        />
        <Select options={BUILDUPS} value={buildup} onChange={setBuildup} size="small" style={{ width: 200 }} />
        <span className="muted" style={{ fontSize: 12 }}>
          {rows.length} strikes · ATM {atm ?? '—'}
        </span>
      </Space>
      <div className="chain-grid" style={{ height: 'calc(100vh - 280px)', minHeight: 420 }}>
        <AgGridReact<ChainRow>
          ref={gridRef}
          theme={GRID_THEMES[theme]}
          rowData={rows}
          columnDefs={columnDefs}
          rowClassRules={rowClassRules}
          onCellClicked={onCellClicked}
          getRowId={(p) => String(p.data.strike)}
          headerHeight={32}
          rowHeight={30}
          suppressCellFocus
          defaultColDef={{ sortable: true, resizable: true, suppressMovable: true, flex: 1 }}
        />
      </div>
    </Card>
  )
}
