# OI Pulse — HOME Page Redesign ("Command Center")

A BlackRock/Bloomberg-grade landing screen. This is the page that loads first and
answers, in five seconds, the only question a trader actually has when they open
the app: **"What is the tape telling me right now, and where do I look next?"**

Today the app opens on the raw Option Chain — a spreadsheet. That's a *tool*, not a
*briefing*. A terminal-grade home is a **decision surface**: synthesized signals on
top, drill-down underneath, zero hunting.

This is a design spec, not code. It targets the React stack already built
(Ant 5 + ECharts + lightweight-charts + Zustand). Every widget maps to an
endpoint that already exists.

---

## 1. Design principles (the rules every widget obeys)

1. **Signal over data.** The home shows *conclusions* (regime, bias, where the wall
   is), not 1,200 cells. Raw chain is one click away, never the front page.
2. **Decision hierarchy.** Reading order = importance order: Verdict → Levels →
   Flow → Drilldown. Eyes land on the verdict first, every time.
3. **One glance, one breath, one scroll.** Glance = regime + spot + bias.
   Breath = key levels + intraday flow. Scroll = supporting evidence.
4. **Calm by default, loud on change.** Static state is muted greys/navy. *Change*
   (OI spurt, regime flip, spot crossing a wall) is the only thing allowed to
   flash, pulse, or color-saturate. Motion = information.
5. **Every number is sourced and timestamped.** A faint "13:18 · live" stamp on
   each card. Stale data desaturates rather than lies.
6. **Density is a feature.** Tabular-nums everywhere, 12–13px mono numerics, tight
   gutters. A pro wants more on screen, not whitespace. (Density toggle already exists.)

---

## 2. Information architecture — what earns a place on HOME

Ruthless triage. A widget is on the home **only if a trader acts on it within the
first 10 seconds**. Everything else stays in its tab.

| Zone | Widget | Answers | Source (existing) |
|---|---|---|---|
| **A · Verdict bar** | Regime verdict + conviction meter | "Bull or bear, how sure?" | `classifyRegime` (client) |
| A | Spot + Δ + sparkline | "Where & moving how fast?" | `/api/option-chain` |
| A | 3-PCR cluster (OI/Vol/W) | "Positioning vs flow vs capital agree?" | option-chain + `wpcr` |
| A | India VIX dial | "Fear regime?" | `/api/vix` |
| **B · Battle map** | Strike "wall" ladder around spot | "Where are support/resistance walls? γ-flip? max-pain magnet?" | chain + `gex` + `maxPain` |
| **C · Intraday flow** | Spot vs CE Δ vs PE Δ (the Pulse mini) | "Who's writing/covering as price moves?" | `/api/intraday-flow` |
| C | Capital-flow bars (₹) | "Where is real money parking today?" | chain (OI×LTP×lot) |
| **D · What changed** | Live event feed (spurts, regime flips, wall breaks) | "What just happened while I blinked?" | alert engine (built) |
| D | Top movers strip | "Which strikes are hot?" | chain ΔOI |
| **E · Context rail** | Multi-index mini-cards | "Is this index-specific or market-wide?" | `/api/multi` |
| E | Expiry term mini | "Front-week vs next?" | `/api/calendar` |

Notably **excluded** from home (live in their tabs): full chain table, IV smile,
straddle ladder, z-scores, payoff builder, compare. They're analysis, not briefing.

---

## 3. Layout — desktop (≥1280px)

12-column grid, three bands. ASCII wireframe:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ HEADER (existing): OI Pulse · NIFTY ▾ · 08-May ▾ · ●LIVE · 13:18 IST · ⚡ ☼ ⌗ 🔔 │
├──────────────────────────────────────────────────────────────────────────────┤
│ A · VERDICT BAR  (sticky under header, h≈92px)                                  │
│ ┌─────────────┬──────────────┬───────────────────────────┬──────────────────┐ │
│ │  ● BULLISH  │  SPOT        │  PCR  OI 0.93  Vol 1.07     │   VIX            │ │
│ │  conviction │  22,417.55   │  W 1.12   ▁▂▃▅▇ agree?      │   12.4  ◔ Calm   │ │
│ │  ▰▰▰▰▱ 4/5  │  +82 (+0.37%)│  [bull bull bull · mixed]   │   −0.3           │ │
│ └─────────────┴──────────────┴───────────────────────────┴──────────────────┘ │
├───────────────────────────────────────────────┬──────────────────────────────┤
│ B · BATTLE MAP  (col 1–7)                       │ E · CONTEXT RAIL (col 11–12) │
│   per-strike horizontal ladder, spot-centered:  │  ┌────────────────────────┐  │
│   22600 ███▌ CE wall            resistance       │  │ NIFTY  22417 ▲  PCR .93 │  │
│   22500 ██▌      ← MAX PAIN ✦                     │  │ BANKNF 48210 ▼  PCR1.04 │  │
│   22450 ─────────●SPOT──────── γ-flip ┄┄          │  │ FINNF  23110 ▲  PCR .88 │  │
│   22400 ██▍  ATM                                  │  └────────────────────────┘  │
│   22300     ▐██ PE wall          support          │  ┌────────────────────────┐  │
│   bars = OI; ▲▼ = ΔOI today; gold=spot, violet=MP │  │ EXPIRY TERM            │  │
│                                                   │  │ 08May 2DTE IV11.4 PCR.9│  │
│ C · INTRADAY FLOW  (col 1–7, below battle map)    │  │ 15May 9DTE IV12.1 PCR.9│  │
│   ┌───────────────────────────────────────────┐  │  │ 22May16DTE IV12.8 …    │  │
│   │ spot(gold) ╱╲  CE Δ(blue) PE Δ(red)        │  │  └────────────────────────┘  │
│   │ dual-axis, crosshair, last 1 session       │  │                              │
│   └───────────────────────────────────────────┘  │ D · WHAT CHANGED (col 8–10)  │
│   Capital flow ₹ by strike  ▕▏▎▍▌ CE  PE ▌▍▎▏     │  13:18 ⚡ 22600CE +2.1L STRONG│
│                                                   │  13:12 ↑ Regime → Bullish     │
│                                                   │  13:06 ✦ Spot crossed MaxPain │
│                                                   │  12:54 ⚡ 22300PE +1.4L        │
│                                                   │  … live feed, newest on top   │
└───────────────────────────────────────────────┴──────────────────────────────┘
```

**Battle map** is the centerpiece — the one widget no competitor nails. It fuses
five facts into one spatial picture: OI walls (bar length), today's ΔOI (▲▼ +
color), spot (gold line), max-pain (violet ✦ magnet), and γ-flip (dashed). A
trader reads "price is wedged below the 22600 call wall, max-pain pulling up to
22500, dealers flip long-gamma above 22450" — instantly, spatially.

---

## 4. Layout — tablet (560–1280) & mobile (<560)

- **Tablet:** verdict bar wraps to 2 rows; Battle Map + Flow stack full-width;
  Context rail + What-Changed move below as a 2-col row.
- **Mobile:** single column, reading-order = decision-order:
  `Verdict → Spot → Battle Map (compact, ATM±6) → Flow → What Changed`.
  Multi-index/term collapse into a swipeable card. Bottom tab-bar (not the
  `<select>` the legacy uses) for navigation. Verdict bar stays sticky.

---

## 5. Component specs (the four hero widgets)

### 5.1 Verdict + Conviction meter
- **Verdict** from `classifyRegime` → `BULLISH / BEARISH / NEUTRAL / LEAN x`.
- **Conviction** = `bulls/total` as a 5-segment meter (▰▰▰▰▱). Tooltip lists the
  five votes (PCR, Vol PCR, WPCR, spot-vs-γflip, net-write) each as a ✓/✗ chip —
  so the verdict is *auditable*, not a black box. This is the trust differentiator.
- Color: only the verdict dot + meter carry hue; the rest of the bar stays neutral.
- On a **regime flip**, the dot does a single 600ms pulse + a row drops into the
  What-Changed feed. Never a persistent animation.

### 5.2 Battle Map (new component — the flagship)
- Horizontal bar ladder, ~21 strikes centered on ATM (reuse `sliceAroundATM`).
- Each row: strike label · CE OI bar (left, blue) · PE OI bar (right, red),
  length ∝ OI. ΔOI shown as a brighter overlay segment + ▲/▼ glyph.
- Overlays: **spot** = gold horizontal rule; **max-pain** = violet ✦ marker;
  **γ-flip** = dashed amber rule; **top-5 walls** get a subtle gold tick.
- Render: SVG or ECharts custom series (`CustomChart` already registered).
- Interaction: hover a row → micro-popover (OI, ΔOI, LTP, IV, buildup label).
  Click → pins the strike (pinning already in store) and deep-links to Chain.

### 5.3 Intraday Flow mini
- The Pulse chart distilled: spot (gold area) + CE Δ + PE Δ on dual axis,
  crosshair, *current session only*, no controls. "Open Pulse →" link for the
  full tool. Reuses `rebasePulse` + lightweight-charts wrapper already built.

### 5.4 What-Changed feed
- Live event log fed by the **alert engine already built** (`evalAlerts`).
- Each row: `time · icon · text`, newest on top, max ~12 rows, auto-trim.
- Icons: ⚡ spurt, ↑/↓ regime, ✦ max-pain cross, ⚠ wall break.
- This converts the alert toasts (ephemeral) into a *scannable history* — "what
  did I miss in the last 30 min" answered without watching the screen.

---

## 6. Visual system

- **Type:** IBM Plex Sans (labels) + IBM Plex Mono (every number, tabular-nums).
  Numbers are the content; they get the mono treatment and never reflow on tick.
- **Color discipline:** navy canvas; gold = spot/brand/attention; teal `--bull` /
  red `--bear` = direction *only*; CE-blue / PE-red = option side *only*. Never mix
  the two red meanings in one widget. Neutral state = greys. Saturation is a
  signal, spent sparingly.
- **Elevation:** 3 shadow tiers replace borders-everywhere (cuts visual noise).
  Verdict bar = tier 3 (floats), cards = tier 1.
- **Motion:** 150–250ms ease for state; a single 600ms pulse for *events*; number
  tickers animate the delta, not the whole value. Respect `prefers-reduced-motion`.
- **Stale state:** when `live==='stale'`, the whole home desaturates ~40% and the
  timestamp stamps go amber. Honesty over false confidence.

---

## 7. Interaction & state

- HOME is a new tab `home`, made the **default** (prepend to `TAB_ORDER`, hash
  `#tab=home`). Chain demotes to position 2.
- Everything reads the single live `snap` in the Zustand store — no new fetching
  for zone A/B; zones C/D/E use existing query hooks (`useIntradayFlow`,
  `useMulti`, `useCalendar`).
- Command palette (built) gets HOME actions: "Pin spot wall", "Jump to widest
  wall", "Mute alerts 30m".
- Click-through contracts: battle-map row → Chain (pinned); flow mini → Pulse;
  any PCR → Vol&Skew; VIX → Macro. The home is a *launchpad*, every widget a door.

---

## 8. Why this reads "BlackRock", not "hobby dashboard"

1. **Verdict-first, auditable.** A conviction meter that shows its votes = an
   institutional risk tell, not a toy gauge.
2. **The Battle Map.** One spatial object fusing OI/ΔOI/spot/max-pain/γ-flip is the
   kind of bespoke visualization terminals charge for. Nobody ships this for free.
3. **Restraint.** Calm canvas, motion only on change, sourced+timestamped numbers,
   honest stale-state. Looks expensive *because* it's disciplined, not busy.
4. **Density + speed.** Code-split, virtualized, sub-second. Feels like a tool that
   respects a professional's time.

---

## 9. Build plan (maps onto the existing React app)

| Phase | Work | New files |
|---|---|---|
| H1 | `home` tab scaffold + make default; verdict bar (zone A) from store | `tabs/HomeTab.tsx`, `home/VerdictBar.tsx` |
| H2 | **Battle Map** (the flagship) — SVG/ECharts custom series | `home/BattleMap.tsx` |
| H3 | Intraday Flow mini (reuse Pulse internals) + Capital-flow bars | `home/FlowMini.tsx` |
| H4 | What-Changed feed wired to `evalAlerts` history buffer | `home/ChangeFeed.tsx`, store: `events[]` |
| H5 | Context rail (multi-index + term) + responsive (tablet/mobile) | `home/ContextRail.tsx` |
| H6 | Motion polish, stale-desaturate, reduced-motion, command-palette verbs | — |

Est. ~3–4 focused days. Zero new backend — every datum already has an endpoint.
The only genuinely new engineering is the Battle Map; everything else recomposes
widgets the migration already produced.

---

*Spec only. Say "build the home page" to start at phase H1.*
