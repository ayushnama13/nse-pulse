'use strict';

const STATE = {
  sym: 'NIFTY', exp: null, tab: 'chain',
  chain: [], raw: null,
  spot: 0, mp: 0, pcr: 0, volPcr: 0, tce: 0, tpe: 0,
  atmStrike: null, atmStraddle: 0, atmCeIV: 0, atmPeIV: 0,
  gammaFlip: null, gex: [],
  pcrHistory: [], spotHistory: [], volPcrHistory: [],
  snapshots: [],
  oiHistory: null, straddleSeries: [],
  vixData: null, fiiDiiData: null, partOiData: null, multiData: null,
  err: null, stale: false,
  fetchCount: 0, hasData: false,
  prev: { spot: 0, mp: 0, pcr: 0, tce: 0, tpe: 0, volPcr: 0 },
  macroLastFetch: 0, multiLastFetch: 0,
  oiChange: null, oiChangeWindowMin: 120,
  multiStrikeSelected: new Set(),
  multiStrikeData: null,
  multiStrikeWindowMin: 0,
  dailyAgg: null,
  lotSize: 1,
  oiChartMode: 'oi',  // 'oi' | 'value' | 'chg' | 'chgvalue'
  atmRange: 500,       // 0 = all
  // ── Per-chart slicing controls (0 = show every strike / day) ──
  chartRange: 12,        // OI bars + Gamma chart — strikes either side of ATM
  chartRangeVol: 14,     // IV Skew, Premium Skew, Straddle Ladder
  dailyOIDays: 30,       // Daily OI vs Time
  buildupRange: 500,     // Position Buildup table
  regimeDays: 30,        // Regime Calendar heatmap
  calendarCount: 6,      // Calendar tab — number of expiries
  buildupFilter: 'all',
  pcrSmaOn: false,
  comboStrike: null,
  comboSide: 'CE',
  comboData: null,
  intradayFlow: null,
  pulseDate: null,            // YYYY-MM-DD selected in dropdown
  pulseStartMin: 0,           // minutes from 09:15 (0 → 374)
  pulseEndMin: 375,           // minutes from 09:15 (1 → 375)
  pulseRefMode: 'prev',       // 'prev' (vs prior close) | 'day' (vs day start) | 'window' (vs slider start)

  wpcr: 0,
  wpcrHistory: [],
};

const STRIKE_PALETTE = ['#3b82f6','#60a5fa','#8b5cf6','#a78bfa','#06b6d4','#14b8a6','#2dd4a0','#f0b429','#f59e0b','#fb923c','#ef4444','#f56565'];

const $ = (id) => document.getElementById(id);

const fmt = (n) => {
  if (n === null || n === undefined || isNaN(n)) return '—';
  const a = Math.abs(n);
  if (a >= 1e7) return (n / 1e7).toFixed(2) + 'Cr';
  if (a >= 1e5) return (n / 1e5).toFixed(2) + 'L';
  if (a >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return Math.round(n).toLocaleString('en-IN');
};
const fmt2 = (n) => (n === null || n === undefined || isNaN(n)) ? '—' : Number(n).toFixed(2);
const fmt0 = (n) => (n === null || n === undefined || isNaN(n)) ? '—' : Math.round(n).toLocaleString('en-IN');
const escapeHTML = (s) => String(s ?? '').replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]));

function _topRanks(rows, key, n = 5, useAbs = false) {
  const out = new Map();
  rows
    .map(r => ({ s: r.strike, v: useAbs ? Math.abs(r[key] || 0) : (r[key] || 0) }))
    .filter(x => x.v > 0)
    .sort((a, b) => b.v - a.v)
    .slice(0, n)
    .forEach((x, i) => out.set(x.s, i + 1));
  return out;
}

function setLive(state) {
  const b = $('liveBadge'), l = $('liveLabel');
  b.classList.remove('stale','error');
  if (state === 'stale') { b.classList.add('stale'); l.textContent = 'STALE'; }
  else if (state === 'error') { b.classList.add('error'); l.textContent = 'ERROR'; }
  else { l.textContent = 'LIVE'; }
}

function tickClock() {
  const opts = { timeZone: 'Asia/Kolkata', hour12: false,
                 hour: '2-digit', minute: '2-digit', second: '2-digit' };
  $('clock').textContent = new Date().toLocaleTimeString('en-IN', opts) + ' IST';
}
setInterval(tickClock, 1000); tickClock();

/* Promote any inline-styled hint blocks to .tip styling once on load */
function polishHintBlocks() {
  const all = document.querySelectorAll('.card > div[style*="font-size:11px"], .chart-card > div[style*="font-size:11px"]');
  all.forEach(el => {
    el.classList.add('tip');
    // Strip the inline style so our class wins cleanly
    el.removeAttribute('style');
  });
}
document.addEventListener('DOMContentLoaded', polishHintBlocks);
polishHintBlocks();

/* Tiny sparkline drawer */
function drawSparkline(svgId, series, color) {
  const svg = $(svgId);
  if (!svg) return;
  if (!series || series.length < 2) { svg.innerHTML = ''; return; }
  const W = 100, H = 28;
  const vals = series.map(s => s.v).filter(v => v > 0 || v === 0);
  if (vals.length < 2) { svg.innerHTML = ''; return; }
  let mn = Math.min(...vals), mx = Math.max(...vals);
  if (mn === mx) { mn -= 0.01; mx += 0.01; }
  const x = (i) => (i / (series.length - 1)) * W;
  const y = (v) => H - ((v - mn) / (mx - mn)) * H + 1;
  const path = series.map((s, i) => `${i===0?'M':'L'} ${x(i).toFixed(2)} ${y(s.v).toFixed(2)}`).join(' ');
  const area = path + ` L ${W} ${H} L 0 ${H} Z`;
  const gradId = 'sg_' + svgId;
  svg.innerHTML = `
    <defs><linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${color}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs>
    <path d="${area}" fill="url(#${gradId})"/>
    <path d="${path}" fill="none" stroke="${color}" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" opacity="0.9"/>`;
}

/* Animated count-up between two numeric values */
function animateNumber(el, from, to, format, dur = 480) {
  if (!el) return;
  if (!isFinite(from) || !isFinite(to)) { el.textContent = format(to); return; }
  const t0 = performance.now();
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  function step(now) {
    const t = Math.min(1, (now - t0) / dur);
    const v = from + (to - from) * ease(t);
    el.textContent = format(v);
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function flashStat(el) {
  if (!el) return;
  el.classList.remove('flash');
  void el.offsetWidth;
  el.classList.add('flash');
}

const TAB_ORDER = ['chain','oi','vol','trends','analytics','macro','multi','compare','pulse','calendar','payoff'];

function activateTab(tabName) {
  if (!TAB_ORDER.includes(tabName)) return;
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
  const btn = document.querySelector(`.tab[data-tab="${tabName}"]`);
  if (btn) btn.classList.add('active');
  STATE.tab = tabName;
  $('panel-' + STATE.tab).classList.add('active');
  const sel = $('tabSelect'); if (sel && sel.value !== tabName) sel.value = tabName;
  if (typeof mountAllRangeControls === 'function') mountAllRangeControls();
  if (STATE.tab === 'macro') loadMacro();
  if (STATE.tab === 'multi') loadMulti();
  if (STATE.tab === 'analytics') { loadOIHistory(); loadRegimeCalendar(); }
  if (STATE.tab === 'vol') loadStraddleHistory();
  if (STATE.tab === 'trends') { loadOIChange(); loadMultiStrike(); loadDailyAgg(); loadIntradayFlow(); loadComboData(); }
  if (STATE.tab === 'pulse') loadIntradayFlow();
  if (STATE.tab === 'calendar') loadCalendar();
  if (STATE.tab === 'payoff') initPayoff();
  render();
  writeHash();
}

document.querySelectorAll('.tab').forEach(b =>
  b.addEventListener('click', () => activateTab(b.dataset.tab))
);
if ($('tabSelect')) $('tabSelect').addEventListener('change', e => activateTab(e.target.value));

/* ── URL hash state (4.2) ─────────────────────────────────────────────
   Persist tab + symbol + expiry in #tab=…&sym=…&exp=… so refresh and
   deep-linking work. */
function readHash() {
  const h = (location.hash || '').replace(/^#/, '');
  if (!h) return {};
  const out = {};
  for (const part of h.split('&')) {
    const [k, v] = part.split('=');
    if (k) out[k] = decodeURIComponent(v || '');
  }
  return out;
}
function writeHash() {
  const parts = [`tab=${STATE.tab}`, `sym=${encodeURIComponent(STATE.sym)}`];
  if (STATE.exp) parts.push(`exp=${encodeURIComponent(STATE.exp)}`);
  const target = '#' + parts.join('&');
  if (location.hash !== target) history.replaceState(null, '', target);
}
function applyHashOnLoad() {
  const h = readHash();
  if (h.sym) {
    STATE.sym = h.sym;
    const sel = $('symSel');
    if (sel) sel.value = h.sym;
  }
  if (h.exp) STATE.exp = h.exp;
  if (h.tab && TAB_ORDER.includes(h.tab)) activateTab(h.tab);
}
window.addEventListener('hashchange', () => {
  const h = readHash();
  if (h.tab && h.tab !== STATE.tab) activateTab(h.tab);
});

/* ── Keyboard shortcuts (4.5) ─────────────────────────────────────────
   1–9 cycle tabs, S forces a snapshot. Ignored while typing in inputs. */
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const t = e.target;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
  if (e.key >= '1' && e.key <= '9') {
    const idx = parseInt(e.key, 10) - 1;
    if (idx < TAB_ORDER.length) activateTab(TAB_ORDER[idx]);
  } else if (e.key === 's' || e.key === 'S') {
    if (typeof forceSnapshot === 'function') forceSnapshot();
  } else if (e.key === '?') {
    alert('Shortcuts:\n 1–9 — switch tab\n S  — force snapshot');
  }
});

// Wire up window-btn group for OI Change (only those with data-w)
document.querySelectorAll('.window-btn[data-w]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.window-btn[data-w]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    STATE.oiChangeWindowMin = parseInt(btn.dataset.w, 10);
    loadOIChange();
  });
});

// Pulse tab — date dropdown + dual-handle time-range slider
$('pulseDateSel').addEventListener('change', e => {
  STATE.pulseDate = e.target.value || null;
  // Reset time range to full day on date change
  STATE.pulseStartMin = 0;
  STATE.pulseEndMin = 375;
  $('pulseStartSlider').value = 0;
  $('pulseEndSlider').value = 375;
  syncPulseSlider();
  if (STATE.tab === 'pulse') renderPulse();
});

function _minToHHMM(min) {
  const total = 9 * 60 + 15 + min;
  const h = Math.floor(total / 60);
  const m = total % 60;
  return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
}

function syncPulseSlider() {
  const startEl = $('pulseStartSlider'), endEl = $('pulseEndSlider');
  const fillEl = $('pulseRangeFill');
  if (!startEl || !endEl || !fillEl) return;
  let s = parseInt(startEl.value, 10);
  let e = parseInt(endEl.value, 10);
  if (s >= e) { // enforce min 1-min gap, push the inactive thumb
    if (this && this.id === 'pulseStartSlider') { e = Math.min(375, s + 1); endEl.value = e; }
    else { s = Math.max(0, e - 1); startEl.value = s; }
  }
  STATE.pulseStartMin = s;
  STATE.pulseEndMin = e;
  const leftPct = (s / 375) * 100;
  const widthPct = ((e - s) / 375) * 100;
  fillEl.style.left = leftPct + '%';
  fillEl.style.width = widthPct + '%';
  $('pulseStartLabel').textContent = _minToHHMM(s);
  $('pulseEndLabel').textContent = _minToHHMM(e);
}

['pulseStartSlider', 'pulseEndSlider'].forEach(id => {
  const el = $(id);
  if (!el) return;
  el.addEventListener('input', function() { syncPulseSlider.call(this); });
  el.addEventListener('change', () => { if (STATE.tab === 'pulse') renderPulse(); });
});

document.querySelectorAll('.window-btn[data-pulse-ref]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.window-btn[data-pulse-ref]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    STATE.pulseRefMode = btn.dataset.pulseRef;
    if (STATE.tab === 'pulse') renderPulse();
  });
});

// OI chart mode toggle (OI / Value / ΔOI)
document.querySelectorAll('.window-btn[data-oi-mode]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.window-btn[data-oi-mode]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    STATE.oiChartMode = btn.dataset.oiMode;
    if (STATE.tab === 'oi') renderOIChart();
  });
});

// Combo side toggle
document.querySelectorAll('.window-btn[data-combo-side]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.window-btn[data-combo-side]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    STATE.comboSide = btn.dataset.comboSide;
    renderComboChart();
  });
});

// Multi-Strike window toggle
document.querySelectorAll('.window-btn[data-ms-w]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.window-btn[data-ms-w]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    STATE.multiStrikeWindowMin = parseInt(btn.dataset.msW, 10) || 0;
    loadMultiStrike();
  });
});

// Chain controls
$('atmRangeSel').addEventListener('change', e => {
  STATE.atmRange = parseInt(e.target.value, 10) || 0;
  if (STATE.tab === 'chain') renderChain();
});
$('buildupFilterSel').addEventListener('change', e => {
  STATE.buildupFilter = e.target.value;
  if (STATE.tab === 'chain') renderChain();
});

/* ════════════════════════════════════════════════════════════════════════
   mountRangeControl — reusable preset-pill + min/max input panel.
   Replaces the old per-chart <select> dropdowns.
   ═══════════════════════════════════════════════════════════════════════ */
const _atmRangeFmt = (n) => n > 0 ? `ATM ±${n}` : 'All strikes';
const _daysFmt     = (n) => `last ${n} trading days`;
const _atmAbsFmt   = (n) => n > 0 ? `ATM ±${n}` : 'All strikes';
const _expFmt      = (n) => `live · nearest ${n} expiries`;
const _daysBucketFmt = (n) => `last ${n} trading days · 5 intraday buckets`;

/**
 * config: {
 *   field,            STATE field name to read/write
 *   default,          factory default (used by Reset)
 *   presets,          array of numbers; 0 = "Show All"
 *   labelFor,         (n) => preset label (defaults to "±N" / "Show All")
 *   showRange,        true → add Min/Max number inputs that mirror the value (symmetric)
 *   minBound, maxBound, step, units  for the Min/Max inputs
 *   onChange,         callback after every value change
 *   title,            section heading
 *   tagId, tagFmt     optional: keep a sibling <span> in sync with the value
 * }
 */
function mountRangeControl(mountId, cfg) {
  const m = $(mountId);
  if (!m || m.dataset.mounted === '1') return;     // idempotent
  m.dataset.mounted = '1';
  m.classList.add('chart-ctrl');

  const labelFor = cfg.labelFor || ((n) => n === 0 ? 'Show All' : '±' + n);
  const pills = cfg.presets.map(n =>
    `<button class="pill" data-pv="${n}">${labelFor(n)}</button>`).join('');

  const rangeRow = cfg.showRange ? `
    <div class="chart-ctrl-row">
      <span class="num-input">
        <span class="num-label">Min</span>
        <button data-act="dec" data-side="min">−</button>
        <input type="number" data-side="min" min="${cfg.minBound ?? 0}" max="${cfg.maxBound ?? 9999}" step="${cfg.step ?? 1}">
        <button data-act="inc" data-side="min">+</button>
      </span>
      <span class="num-input">
        <span class="num-label">Max</span>
        <button data-act="dec" data-side="max">−</button>
        <input type="number" data-side="max" min="${cfg.minBound ?? 0}" max="${cfg.maxBound ?? 9999}" step="${cfg.step ?? 1}">
        <button data-act="inc" data-side="max">+</button>
      </span>
      <span class="chart-ctrl-hint">${cfg.units || ''}</span>
    </div>` : '';

  m.innerHTML = `
    <div class="chart-ctrl-row">
      <span class="chart-ctrl-title">${cfg.title}</span>
      <button class="chart-ctrl-reset" data-act="reset" title="Restore default">↺ Reset</button>
    </div>
    <div class="chart-ctrl-row"><div class="pill-group">${pills}</div></div>
    ${rangeRow}
  `;

  function paint() {
    const v = STATE[cfg.field];
    m.querySelectorAll('[data-pv]').forEach(b =>
      b.classList.toggle('active', parseInt(b.dataset.pv, 10) === v));
    if (cfg.showRange) {
      m.querySelector('input[data-side="min"]').value = v > 0 ? v : (cfg.minBound ?? 0);
      m.querySelector('input[data-side="max"]').value = v > 0 ? v : (cfg.maxBound ?? 0);
    }
    if (cfg.tagId && cfg.tagFmt) {
      const t = $(cfg.tagId);
      if (t) t.textContent = cfg.tagFmt(v);
    }
  }
  function setValue(v) {
    STATE[cfg.field] = v;
    paint();
    cfg.onChange();
  }
  m.querySelectorAll('[data-pv]').forEach(btn => {
    btn.addEventListener('click', () => setValue(parseInt(btn.dataset.pv, 10)));
  });
  if (cfg.showRange) {
    const apply = () => {
      const lo = parseInt(m.querySelector('input[data-side="min"]').value, 10);
      const hi = parseInt(m.querySelector('input[data-side="max"]').value, 10);
      // Symmetric ATM-relative range: take the larger of |lo|, |hi|.
      const r = Math.max(Math.abs(lo) || 0, Math.abs(hi) || 0);
      setValue(r);
    };
    m.querySelectorAll('input[type=number]').forEach(inp => inp.addEventListener('change', apply));
    m.querySelectorAll('button[data-act="inc"]').forEach(b => b.addEventListener('click', () => {
      const cur = STATE[cfg.field] || cfg.default;
      setValue(Math.min(cur + (cfg.step ?? 1), cfg.maxBound ?? 999));
    }));
    m.querySelectorAll('button[data-act="dec"]').forEach(b => b.addEventListener('click', () => {
      const cur = STATE[cfg.field] || cfg.default;
      setValue(Math.max(cur - (cfg.step ?? 1), cfg.minBound ?? 0));
    }));
  }
  m.querySelector('[data-act="reset"]').addEventListener('click', () => setValue(cfg.default));
  paint();
}

/* Wire each chart's control panel — call once per panel after the
   markup is in the DOM. mountRangeControl is idempotent so it's safe
   to invoke on every tab activation. */
function mountAllRangeControls() {
  mountRangeControl('oiChartCtrl', {
    field: 'chartRange', default: 12,
    presets: [5, 10, 15, 20, 25, 50, 0],
    showRange: true, minBound: 1, maxBound: 200, step: 1, units: 'strikes either side of ATM',
    title: 'Strikes around ATM (OI, Capital, ΔOI, Gamma)',
    tagId: 'oiRangeTag', tagFmt: _atmRangeFmt,
    onChange: () => {
      if (STATE.tab === 'oi') { renderOIChart(); renderGammaChart(); }
    },
  });
  mountRangeControl('volChartCtrl', {
    field: 'chartRangeVol', default: 14,
    presets: [5, 10, 15, 20, 25, 50, 0],
    showRange: true, minBound: 1, maxBound: 200, step: 1, units: 'strikes either side of ATM',
    title: 'Strikes around ATM (IV Skew, Premium Skew, Straddle Ladder)',
    onChange: () => {
      if (STATE.tab === 'vol') { renderIVSkew(); renderPremiumSkew(); renderStraddleLadder(); }
    },
  });
  mountRangeControl('dailyOICtrl', {
    field: 'dailyOIDays', default: 30,
    presets: [7, 14, 30, 60, 90, 180, 365],
    showRange: false,
    labelFor: (n) => n + 'd',
    title: 'Days of history',
    tagId: 'dailyOITag', tagFmt: _daysFmt,
    onChange: () => loadDailyAgg(),
  });
  mountRangeControl('buildupCtrl', {
    field: 'buildupRange', default: 500,
    presets: [250, 500, 1000, 2000, 0],
    showRange: true, minBound: 50, maxBound: 5000, step: 50, units: '₹ either side of spot',
    labelFor: (n) => n === 0 ? 'All strikes' : '±' + n,
    title: 'ATM proximity (Position Buildup)',
    tagId: 'buildupTag', tagFmt: _atmAbsFmt,
    onChange: () => { if (STATE.tab === 'analytics') renderBuildup(); },
  });
  mountRangeControl('regimeCtrl', {
    field: 'regimeDays', default: 30,
    presets: [7, 14, 30, 60, 90, 180],
    showRange: false,
    labelFor: (n) => n + 'd',
    title: 'Days of history',
    tagId: 'regimeTag', tagFmt: _daysBucketFmt,
    onChange: () => loadRegimeCalendar(),
  });
  mountRangeControl('calendarCtrl', {
    field: 'calendarCount', default: 6,
    presets: [3, 4, 6, 8, 12],
    showRange: false,
    labelFor: (n) => n + ' expiries',
    title: 'Expiries to fetch',
    tagId: 'calendarTag', tagFmt: _expFmt,
    onChange: () => loadCalendar(),
  });
}

// Combo strike selector
$('comboStrikeSel').addEventListener('change', e => {
  STATE.comboStrike = parseFloat(e.target.value);
  loadComboData();
});

// PCR SMA toggle
$('pcrSmaToggle').addEventListener('click', () => {
  STATE.pcrSmaOn = !STATE.pcrSmaOn;
  $('pcrSmaToggle').textContent = STATE.pcrSmaOn ? 'SMA-5 on' : 'SMA-5 off';
  if (STATE.tab === 'analytics') renderLineChart('pcrChart', STATE.pcrHistory, '#8b5cf6', STATE.pcrSmaOn ? 5 : 0);
});

$('symSel').addEventListener('change', e => {
  STATE.sym = e.target.value; STATE.exp = null;
  STATE.pcrHistory = []; STATE.spotHistory = []; STATE.volPcrHistory = [];
  STATE.oiHistory = null; STATE.straddleSeries = [];
  STATE.oiChange = null; STATE.multiStrikeData = null; STATE.dailyAgg = null;
  STATE.multiStrikeSelected = new Set();
  STATE.intradayFlow = null; STATE.comboData = null; STATE.comboStrike = null;
  STATE.wpcrHistory = [];
  STATE.pulseDate = null; STATE.pulseStartMin = 0; STATE.pulseEndMin = 375;
  if ($('pulseStartSlider')) { $('pulseStartSlider').value = 0; $('pulseEndSlider').value = 375; }
  if (typeof writeHash === 'function') writeHash();
  poll(true);
  if (typeof connectStream === 'function') connectStream();  // re-subscribe for new symbol
  if (typeof loadNotes === 'function') loadNotes();
  if (STATE.tab === 'pulse') loadIntradayFlow();
  if (STATE.tab === 'calendar') loadCalendar();
});
$('expSel').addEventListener('change', () => { if (typeof writeHash === 'function') writeHash(); });
$('expSel').addEventListener('change', e => { STATE.exp = e.target.value || null; poll(true); });
$('snapBtn').addEventListener('click', forceSnapshot);
$('cmpBtn').addEventListener('click', runCompare);
$('multiRefreshBtn').addEventListener('click', () => { STATE.multiLastFetch = 0; loadMulti(); });

async function poll(force = false) {
  try {
    const url = `/api/option-chain?symbol=${encodeURIComponent(STATE.sym)}` +
                (STATE.exp ? `&expiry=${encodeURIComponent(STATE.exp)}` : '');
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.error || `HTTP ${res.status}`);
    }
    const data = await res.json();
    applyData(data);
    setLive(data.stale ? 'stale' : 'live');
    STATE.err = null;
    STATE.stale = !!data.stale;
    STATE.hasData = true;
    STATE.fetchCount++;
    refreshSnapshotsList();
    render();
  } catch (e) {
    STATE.err = e.message || String(e);
    setLive('error');
    if (!STATE.hasData) showFatal();
  }
}

function applyData(d) {
  STATE.prev = {
    spot: STATE.spot, mp: STATE.mp, pcr: STATE.pcr,
    tce: STATE.tce, tpe: STATE.tpe, volPcr: STATE.volPcr,
  };
  STATE.raw = d;
  STATE.chain = d.chain || [];
  STATE.spot = d.spot;
  STATE.mp = d.maxPain;
  STATE.pcr = d.pcr;
  STATE.volPcr = d.volPcr || 0;
  STATE.tce = d.totalCEOI;
  STATE.tpe = d.totalPEOI;
  STATE.atmStrike = d.atmStrike;
  STATE.atmStraddle = d.atmStraddle || 0;
  STATE.atmCeIV = d.atmCeIV || 0;
  STATE.atmPeIV = d.atmPeIV || 0;
  STATE.gammaFlip = d.gammaFlip;
  STATE.gex = d.gex || [];
  STATE.lotSize = d.lotSize || 1;

  const sel = $('expSel');
  const cur = sel.value;
  const expiries = d.expiries || [];
  if (expiries.length) {
    if (cur !== d.currentExpiry || sel.options.length !== expiries.length) {
      sel.innerHTML = '';
      expiries.forEach(e => {
        const o = document.createElement('option');
        o.value = e; o.textContent = e;
        if (e === d.currentExpiry) o.selected = true;
        sel.appendChild(o);
      });
    }
  }

  // WPCR — premium-weighted (₹) PCR
  let ceVal = 0, peVal = 0;
  for (const r of STATE.chain) {
    ceVal += (r.ceOI || 0) * (r.ceLTP || 0);
    peVal += (r.peOI || 0) * (r.peLTP || 0);
  }
  STATE.wpcr = ceVal > 0 ? peVal / ceVal : 0;

  STATE.pcrHistory.push({ t: d.time, v: d.pcr });
  STATE.spotHistory.push({ t: d.time, v: d.spot });
  STATE.volPcrHistory.push({ t: d.time, v: d.volPcr || 0 });
  STATE.wpcrHistory.push({ t: d.time, v: STATE.wpcr });
  if (STATE.pcrHistory.length > 80) STATE.pcrHistory.shift();
  if (STATE.spotHistory.length > 80) STATE.spotHistory.shift();
  if (STATE.volPcrHistory.length > 80) STATE.volPcrHistory.shift();
  if (STATE.wpcrHistory.length > 80) STATE.wpcrHistory.shift();
}

async function forceSnapshot() {
  $('snapBtn').disabled = true;
  try {
    const res = await fetch('/api/snapshot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: STATE.sym, expiry: STATE.exp || null }),
    });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.error || `HTTP ${res.status}`);
    }
    const data = await res.json();
    applyData({ ...data, stale: false });
    setLive('live'); STATE.err = null;
    refreshSnapshotsList();
    render();
  } catch (e) {
    alert('Snapshot failed: ' + e.message);
  } finally {
    $('snapBtn').disabled = false;
  }
}

async function refreshSnapshotsList() {
  try {
    const res = await fetch(`/api/snapshots?symbol=${encodeURIComponent(STATE.sym)}`, { cache: 'no-store' });
    if (!res.ok) return;
    const j = await res.json();
    STATE.snapshots = j.snapshots || [];
    populateCompareSelects();
    seedHistoriesFromSnapshots();
  } catch {}
}

function seedHistoriesFromSnapshots() {
  // On a fresh page load, seed the in-browser history arrays from persisted
  // snapshots so the charts aren't empty until 80 polls accumulate.
  if (STATE.fetchCount > 1) return;
  const snaps = STATE.snapshots.slice(-80);
  if (snaps.length < 2) return;
  STATE.pcrHistory = snaps.map(s => ({ t: s.time, v: s.pcr }));
  STATE.spotHistory = snaps.map(s => ({ t: s.time, v: s.spot }));
  STATE.volPcrHistory = snaps.map(s => ({ t: s.time, v: s.volPcr || 0 }));
}

/* ---------- Compare: cascading Date → Time selectors ---------- */
function _formatLocalDate(iso) {
  // Show as "DD-MMM" using the IST date (the timestamp string already encodes IST)
  // The timestamp looks like "2026-05-04T09:15:00+05:30" or "2026-05-04T..."
  const d = (iso || '').slice(0, 10);  // "YYYY-MM-DD"
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return iso;
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const [y, m, day] = d.split('-');
  return `${day}-${months[parseInt(m,10)-1]}-${y.slice(2)}`;
}

function _groupSnapshotsByDate(list) {
  // Returns { 'YYYY-MM-DD': [snap, snap, ...] }, oldest-to-newest within each day
  const out = {};
  for (const s of list) {
    const d = (s.timestamp || '').slice(0, 10);
    if (!d) continue;
    (out[d] ||= []).push(s);
  }
  return out;
}

function populateCompareSelects() {
  const aD = $('cmpADate'), aT = $('cmpATime');
  const bD = $('cmpBDate'), bT = $('cmpBTime');
  if (!aD || !bD) return;

  const groups = _groupSnapshotsByDate(STATE.snapshots);
  const dates = Object.keys(groups).sort();   // YYYY-MM-DD strings sort chronologically

  if (!dates.length) {
    aD.innerHTML = '<option>—</option>'; bD.innerHTML = '<option>—</option>';
    aT.innerHTML = '<option>—</option>'; bT.innerHTML = '<option>—</option>';
    $('cmpHint').textContent = 'No snapshots stored yet.';
    return;
  }

  const oldA_d = aD.value, oldA_t = aT.value;
  const oldB_d = bD.value, oldB_t = bT.value;

  const dateOpts = dates.map(d => `<option value="${d}">${_formatLocalDate(d)}</option>`).join('');
  aD.innerHTML = dateOpts;
  bD.innerHTML = dateOpts;

  // Defaults: A = oldest day, B = newest day
  aD.value = (dates.includes(oldA_d) ? oldA_d : dates[0]);
  bD.value = (dates.includes(oldB_d) ? oldB_d : dates[dates.length - 1]);

  fillTimeOptions(aD.value, aT, oldA_t, /*pickFirst*/ true);
  fillTimeOptions(bD.value, bT, oldB_t, /*pickFirst*/ false);
  updateCmpHint();
}

function fillTimeOptions(date, sel, prevValue, pickFirst) {
  const groups = _groupSnapshotsByDate(STATE.snapshots);
  const day = (groups[date] || []).slice().sort((a,b) => a.timestamp.localeCompare(b.timestamp));
  if (!day.length) { sel.innerHTML = '<option>—</option>'; return; }
  sel.innerHTML = day.map(s =>
    `<option value="${s.timestamp}">${s.time} · spot ${fmt2(s.spot)} · pcr ${fmt2(s.pcr)}</option>`
  ).join('');
  // Try to keep the previous selection if its timestamp is still present
  const stillThere = day.find(s => s.timestamp === prevValue);
  if (stillThere) sel.value = prevValue;
  else sel.value = pickFirst ? day[0].timestamp : day[day.length - 1].timestamp;
}

function updateCmpHint() {
  const aTs = $('cmpATime').value, bTs = $('cmpBTime').value;
  const a = STATE.snapshots.find(s => s.timestamp === aTs);
  const b = STATE.snapshots.find(s => s.timestamp === bTs);
  if (!a || !b) { $('cmpHint').textContent = ''; return; }
  if (aTs === bTs) {
    $('cmpHint').innerHTML = '<span style="color:var(--bear)">A and B are the same snapshot — pick different ones.</span>';
    return;
  }
  const order = aTs < bTs ? 'A is older, B is newer (deltas = B − A → forward in time)' : 'A is NEWER than B (deltas will be reversed in time)';
  $('cmpHint').textContent = order;
}

['cmpADate','cmpATime','cmpBDate','cmpBTime'].forEach(id => {
  // re-bind once selects exist
  document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', onCmpChange);
  });
});
function onCmpChange(e) {
  const id = e.target.id;
  if (id === 'cmpADate') fillTimeOptions(e.target.value, $('cmpATime'), '', true);
  if (id === 'cmpBDate') fillTimeOptions(e.target.value, $('cmpBTime'), '', false);
  updateCmpHint();
}
// Bind via delegation in case DOMContentLoaded already fired
document.body && document.body.addEventListener('change', (e) => {
  if (['cmpADate','cmpATime','cmpBDate','cmpBTime'].includes(e.target.id)) onCmpChange(e);
});

async function runCompare() {
  const aTs = $('cmpATime').value, bTs = $('cmpBTime').value;
  if (!aTs || !bTs) { alert('Pick a Date+Time for both A and B.'); return; }
  if (aTs === bTs) { alert('A and B are the same snapshot.'); return; }
  try {
    const r = await fetch(`/api/compare?symbol=${encodeURIComponent(STATE.sym)}&aTs=${encodeURIComponent(aTs)}&bTs=${encodeURIComponent(bTs)}`);
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.error || `HTTP ${r.status}`);
    }
    renderCompare(await r.json());
  } catch (e) {
    alert('Compare failed: ' + e.message);
  }
}

async function loadOIHistory() {
  try {
    const r = await fetch(`/api/oi-history?symbol=${encodeURIComponent(STATE.sym)}&top=6`);
    if (!r.ok) return;
    STATE.oiHistory = await r.json();
    if (STATE.tab === 'analytics') renderOIHistory();
  } catch {}
}

async function loadStraddleHistory() {
  try {
    const r = await fetch(`/api/straddle-history?symbol=${encodeURIComponent(STATE.sym)}`);
    if (!r.ok) return;
    const j = await r.json();
    STATE.straddleSeries = j.series || [];
    if (STATE.tab === 'vol') renderStraddleHistory();
  } catch {}
}

async function loadMacro() {
  const now = Date.now();
  if (now - STATE.macroLastFetch < 60000 && STATE.vixData) { renderMacro(); return; }
  STATE.macroLastFetch = now;
  $('vixVal').textContent = '…';
  $('fiiDiiBody').innerHTML = '<div style="color:var(--text-faint);font-size:12px;padding:8px 0">Loading…</div>';
  $('partOiBody').innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-faint);padding:14px">Loading…</td></tr>';
  const safe = (p) => p.then(r => r.ok ? r.json() : null).catch(() => null);
  const [vix, fii, part] = await Promise.all([
    safe(fetch('/api/vix')),
    safe(fetch('/api/fii-dii')),
    safe(fetch('/api/participant-oi')),
  ]);
  STATE.vixData = vix; STATE.fiiDiiData = fii; STATE.partOiData = part;
  renderMacro();
}

async function loadMulti() {
  const now = Date.now();
  if (now - STATE.multiLastFetch < 30000 && STATE.multiData) { renderMulti(); return; }
  STATE.multiLastFetch = now;
  $('multiGrid').innerHTML = '<div class="mini-card"><div style="color:var(--text-faint);font-size:12px">Loading NIFTY…</div></div><div class="mini-card"><div style="color:var(--text-faint);font-size:12px">Loading BANKNIFTY…</div></div><div class="mini-card"><div style="color:var(--text-faint);font-size:12px">Loading FINNIFTY…</div></div>';
  try {
    const r = await fetch('/api/multi?symbols=NIFTY,BANKNIFTY,FINNIFTY');
    if (!r.ok) throw new Error('fetch failed');
    STATE.multiData = await r.json();
    renderMulti();
  } catch (e) {
    $('multiGrid').innerHTML = `<div class="mini-card"><div style="color:var(--red)">Failed: ${escapeHTML(e.message)}</div></div>`;
  }
}

async function loadOIChange() {
  try {
    const r = await fetch(`/api/oi-change?symbol=${encodeURIComponent(STATE.sym)}&windowMin=${STATE.oiChangeWindowMin}`);
    if (!r.ok) return;
    STATE.oiChange = await r.json();
    if (STATE.tab === 'trends') renderOIChange();
  } catch {}
}

async function loadMultiStrike() {
  // First call: let backend pick top 6. Subsequent: send our selection.
  const w = STATE.multiStrikeWindowMin;
  const wParam = w > 0 ? `&windowMin=${w}` : '';
  let url = `/api/oi-history?symbol=${encodeURIComponent(STATE.sym)}&top=6${wParam}`;
  if (STATE.multiStrikeSelected.size > 0) {
    url = `/api/oi-history?symbol=${encodeURIComponent(STATE.sym)}&strikes=${[...STATE.multiStrikeSelected].join(',')}${wParam}`;
  }
  try {
    const r = await fetch(url);
    if (!r.ok) return;
    STATE.multiStrikeData = await r.json();
    if (STATE.multiStrikeSelected.size === 0 && STATE.multiStrikeData.strikes) {
      STATE.multiStrikeData.strikes.forEach(s => STATE.multiStrikeSelected.add(s));
    }
    if (STATE.tab === 'trends') { renderStrikePicker(); renderMultiStrike(); }
  } catch {}
}

async function loadDailyAgg() {
  try {
    const days = STATE.dailyOIDays || 30;
    const r = await fetch(`/api/daily-aggregate?symbol=${encodeURIComponent(STATE.sym)}&days=${days}`);
    if (!r.ok) return;
    STATE.dailyAgg = await r.json();
    if (STATE.tab === 'trends') renderDailyOI();
  } catch {}
}

async function loadIntradayFlow() {
  try {
    const r = await fetch(`/api/intraday-flow?symbol=${encodeURIComponent(STATE.sym)}&limit=500`);
    if (!r.ok) return;
    STATE.intradayFlow = await r.json();
    if (STATE.tab === 'trends') renderCumOI();
    if (STATE.tab === 'pulse') { populatePulseDateSelect(); renderPulse(); }
  } catch {}
}

async function loadComboData() {
  if (!STATE.comboStrike) return;
  try {
    const r = await fetch(`/api/strike-detail?symbol=${encodeURIComponent(STATE.sym)}&strike=${STATE.comboStrike}`);
    if (!r.ok) return;
    STATE.comboData = await r.json();
    if (STATE.tab === 'trends') renderComboChart();
  } catch {}
}

function populateComboStrikeSelector() {
  const sel = $('comboStrikeSel');
  if (!STATE.chain.length) { sel.innerHTML = '<option>—</option>'; return; }
  const sorted = [...STATE.chain].sort((a,b) => (b.ceOI + b.peOI) - (a.ceOI + a.peOI)).slice(0, 14);
  sorted.sort((a,b) => a.strike - b.strike);
  const cur = sel.value;
  sel.innerHTML = sorted.map(r => `<option value="${r.strike}">${fmt0(r.strike)}</option>`).join('');
  if (cur && sorted.find(r => r.strike == cur)) {
    sel.value = cur;
  } else if (!STATE.comboStrike) {
    const atm = nearestATM();
    if (atm) {
      STATE.comboStrike = atm;
      sel.value = atm;
      loadComboData();
    }
  } else {
    sel.value = STATE.comboStrike;
  }
}

/* ---------- RENDER ---------- */

function render() {
  renderStats();
  if (STATE.tab === 'chain') renderChain();
  if (STATE.tab === 'oi') { renderOIChart(); renderGammaChart(); }
  if (STATE.tab === 'vol') { renderIVSkew(); renderStraddleHistory(); renderPCRComparison(); renderPremiumSkew(); renderStraddleLadder(); }
  if (STATE.tab === 'trends') { populateComboStrikeSelector(); renderOIChange(); renderStrikePicker(); renderMultiStrike(); renderDailyOI(); renderCumOI(); renderComboChart(); }
  if (STATE.tab === 'analytics') renderAnalytics();
  if (STATE.tab === 'macro') renderMacro();
  if (STATE.tab === 'multi') renderMulti();
  if (STATE.tab === 'pulse') renderPulse();
}

function renderStats() {
  // Animated number transitions for the headline stats
  if (STATE.fetchCount > 1 && STATE.prev.spot && STATE.spot !== STATE.prev.spot) {
    animateNumber($('vSpot'), STATE.prev.spot, STATE.spot, fmt2);
    flashStat($('vSpot').closest('.stat'));
  } else {
    $('vSpot').textContent = fmt2(STATE.spot);
  }

  // Sparklines
  drawSparkline('sparkSpot', STATE.spotHistory, '#06b6d4');
  drawSparkline('sparkPCR', STATE.pcrHistory, '#8b5cf6');
  drawSparkline('sparkVolPCR', STATE.volPcrHistory, '#06b6d4');

  $('vMP').textContent = fmt0(STATE.mp);
  if (STATE.spot && STATE.mp) {
    const diff = Math.round(STATE.mp - STATE.spot);
    const cls = diff >= 0 ? 'delta-pos' : 'delta-neg';
    $('vMPSub').innerHTML = `<span class="${cls}">${diff >= 0 ? '+' : ''}${diff}</span> from spot`;
  } else $('vMPSub').textContent = '';

  $('vPCR').textContent = fmt2(STATE.pcr);
  const pcrStat = $('pcrStat');
  pcrStat.classList.remove('pcr-bull','pcr-bear','pcr-neutral');
  if (STATE.pcr > 1.2) { pcrStat.classList.add('pcr-bull'); $('vPCRSub').textContent = 'Bullish'; }
  else if (STATE.pcr < 0.8) { pcrStat.classList.add('pcr-bear'); $('vPCRSub').textContent = 'Bearish'; }
  else { pcrStat.classList.add('pcr-neutral'); $('vPCRSub').textContent = 'Neutral'; }

  $('vVolPCR').textContent = fmt2(STATE.volPcr);
  const volStat = $('volPcrStat');
  volStat.classList.remove('pcr-bull','pcr-bear','pcr-neutral');
  if (STATE.volPcr > 1.2) volStat.classList.add('pcr-bull');
  else if (STATE.volPcr < 0.8) volStat.classList.add('pcr-bear');
  else volStat.classList.add('pcr-neutral');
  if (STATE.pcr && STATE.volPcr) {
    const div = STATE.volPcr - STATE.pcr;
    const cls = div > 0 ? 'delta-pos' : 'delta-neg';
    $('vVolPCRSub').innerHTML = `<span class="${cls}">${div >= 0 ? '+' : ''}${div.toFixed(2)}</span> vs OI`;
  } else $('vVolPCRSub').textContent = '';

  if (STATE.chain.length) {
    let res = STATE.chain[0], sup = STATE.chain[0];
    for (const r of STATE.chain) {
      if (r.ceOI > res.ceOI) res = r;
      if (r.peOI > sup.peOI) sup = r;
    }
    $('vRes').textContent = fmt0(res.strike);
    $('vResSub').textContent = fmt(res.ceOI) + ' OI';
    $('vSup').textContent = fmt0(sup.strike);
    $('vSupSub').textContent = fmt(sup.peOI) + ' OI';
  }

  $('vTCE').textContent = fmt(STATE.tce);
  $('vTPE').textContent = fmt(STATE.tpe);

  // WPCR
  $('vWPCR').textContent = fmt2(STATE.wpcr);
  const wpcrStat = $('wpcrStat');
  wpcrStat.classList.remove('pcr-bull','pcr-bear','pcr-neutral');
  if (STATE.wpcr > 1.2) wpcrStat.classList.add('pcr-bull');
  else if (STATE.wpcr > 0 && STATE.wpcr < 0.8) wpcrStat.classList.add('pcr-bear');
  else wpcrStat.classList.add('pcr-neutral');
  if (STATE.tce && STATE.wpcr) {
    const cross = STATE.tpe > STATE.tce ? 'PE > CE' : 'CE > PE';
    const crossCls = STATE.tpe > STATE.tce ? 'delta-pos' : 'delta-neg';
    $('vWPCRSub').innerHTML = `<span class="${crossCls}">${cross}</span>`;
  } else $('vWPCRSub').textContent = '';

  // Lot-size tag on the OI/Gamma chart header
  const lotTagText = `lot ${STATE.lotSize} (${STATE.sym})`;
  const lTag = $('oiLotTag'); if (lTag) lTag.textContent = lotTagText;
}

function nearestATM() {
  if (!STATE.chain.length || !STATE.spot) return null;
  let best = STATE.chain[0], bd = Math.abs(STATE.chain[0].strike - STATE.spot);
  for (const r of STATE.chain) {
    const d = Math.abs(r.strike - STATE.spot);
    if (d < bd) { bd = d; best = r; }
  }
  return best.strike;
}

function renderChain() {
  const tb = $('chainBody');
  if (!STATE.chain.length) {
    let skel = '';
    for (let i = 0; i < 14; i++) {
      skel += '<tr><td colspan="11" style="padding:0"><div class="skel-row">' +
        '<div class="skel-cell"></div>'.repeat(11) + '</div></td></tr>';
    }
    tb.innerHTML = skel;
    return;
  }
  const atm = nearestATM();

  // Apply ATM range filter
  let filtered = STATE.chain;
  if (STATE.atmRange > 0 && atm) {
    filtered = STATE.chain.filter(r => Math.abs(r.strike - atm) <= STATE.atmRange);
  }
  // Apply buildup filter
  if (STATE.buildupFilter !== 'all') {
    filtered = filtered.filter(r => {
      switch (STATE.buildupFilter) {
        case 'ce-build': return r.ceChg > 0;
        case 'ce-cover': return r.ceChg < 0;
        case 'pe-build': return r.peChg > 0;
        case 'pe-unwind': return r.peChg < 0;
        case 'any-build': return r.ceChg !== 0 || r.peChg !== 0;
        default: return true;
      }
    });
  }

  $('chainCountTag').textContent = `${filtered.length} of ${STATE.chain.length} strikes`;

  const maxOI = Math.max(...filtered.flatMap(r => [r.ceOI, r.peOI]), 1);
  const topCEOI = _topRanks(filtered, 'ceOI', 5);
  const topCEChg = _topRanks(filtered, 'ceChg', 5, true);
  const topPEOI = _topRanks(filtered, 'peOI', 5);
  const topPEChg = _topRanks(filtered, 'peChg', 5, true);
  const html = filtered.map(r => {
    const isATM = r.strike === atm;
    const isITMce = STATE.spot && r.strike < STATE.spot;
    const isITMpe = STATE.spot && r.strike > STATE.spot;
    const ceBar = `<span class="oibar ce" style="width:${(r.ceOI/maxOI*40).toFixed(1)}px"></span>`;
    const peBar = `<span class="oibar pe" style="width:${(r.peOI/maxOI*40).toFixed(1)}px"></span>`;
    const dCls = (n) => n > 0 ? 'delta-pos' : (n < 0 ? 'delta-neg' : '');
    const dTxt = (n) => (n > 0 ? '+' : '') + fmt(n);
    const tag = (mp, k) => mp.has(k) ? ` top-oi" data-rank="${mp.get(k)}` : '';
    return `<tr class="${isATM ? 'atm' : ''}" data-strike="${r.strike}">
      <td class="ce-cell ${isITMce ? 'itm' : ''}${tag(topCEOI, r.strike)}">${fmt(r.ceOI)}${ceBar}</td>
      <td class="ce-cell ${dCls(r.ceChg)}${tag(topCEChg, r.strike)}">${dTxt(r.ceChg)}</td>
      <td class="ce-cell">${fmt(r.ceVol)}</td>
      <td class="ce-cell">${r.ceIV ? r.ceIV.toFixed(2) : '—'}</td>
      <td class="ce-cell">${r.ceLTP ? r.ceLTP.toFixed(2) : '—'}</td>
      <td class="strike">${fmt0(r.strike)}</td>
      <td class="pe-cell">${r.peLTP ? r.peLTP.toFixed(2) : '—'}</td>
      <td class="pe-cell">${r.peIV ? r.peIV.toFixed(2) : '—'}</td>
      <td class="pe-cell">${fmt(r.peVol)}</td>
      <td class="pe-cell ${dCls(r.peChg)}${tag(topPEChg, r.strike)}">${dTxt(r.peChg)}</td>
      <td class="pe-cell ${isITMpe ? 'itm' : ''}${tag(topPEOI, r.strike)}">${fmt(r.peOI)}${peBar}</td>
    </tr>`;
  }).join('');
  tb.innerHTML = html;

  if (STATE.fetchCount <= 1) {
    requestAnimationFrame(() => {
      const row = tb.querySelector(`tr[data-strike="${atm}"]`);
      if (row) row.scrollIntoView({ block: 'center' });
    });
  }
}

function renderOIChart() {
  renderOIBars('oiChart', STATE.oiChartMode);
}

/* Map a real strike value to an SVG x-coordinate on a strike-sequence chart.
   Returns null if the strike is outside the visible window. Linearly
   interpolates between adjacent strikes so spot/max-pain markers slot
   between bars instead of snapping to the nearest bar centre. */
function _strikeToX(strike, data, padL, groupW) {
  if (!strike || !data.length) return null;
  const lo = data[0].strike, hi = data[data.length - 1].strike;
  if (strike < lo || strike > hi) return null;
  // findIndex(>=) gives the first strike at or beyond the target.
  let i = data.findIndex(r => r.strike >= strike);
  if (i <= 0) {
    // Either exactly on or below the first strike — pin to its centre.
    return padL + (i < 0 ? data.length - 1 : 0) * groupW + groupW / 2;
  }
  const a = data[i - 1].strike, b = data[i].strike;
  const t = (strike - a) / Math.max(b - a, 1e-9);
  return padL + (i - 1 + t) * groupW + groupW / 2;
}

/* Render a vertical reference line (spot / max-pain / γ-flip) on a chart.
   `label` shows above-top (top=true) or below-axis. Centralised so all
   three OI/Gamma charts get consistent styling. */
function _vline(x, padT, innerH, color, dasharray, label, top, padB, H) {
  if (x == null) return '';
  const ly = top ? padT - 8 : H - padB + 62;
  return `<line x1="${x}" y1="${padT}" x2="${x}" y2="${padT+innerH}" stroke="${color}" stroke-width="1.5" stroke-dasharray="${dasharray}"/>
    <text x="${x}" y="${ly}" fill="${color}" font-size="10" text-anchor="middle" font-family="DM Sans" font-weight="600">${label}</text>`;
}

/* Window-slice helper: returns rows within ATM ± `range`. range === 0 → all rows. */
function _sliceAroundATM(rows, range) {
  if (!rows.length) return [];
  if (!range || range <= 0) return rows.slice();
  const atm = nearestATM();
  if (atm == null) return rows.slice();
  const center = rows.findIndex(r => r.strike === atm);
  if (center < 0) return rows.slice();
  return rows.slice(Math.max(0, center - range), Math.min(rows.length, center + range + 1));
}

function renderOIBars(svgId, mode) {
  const svg = $(svgId);
  if (!svg) return;
  if (!STATE.chain.length) { svg.innerHTML = ''; return; }
  const atm = nearestATM();
  const data = _sliceAroundATM(STATE.chain, STATE.chartRange);
  if (!data.length) { svg.innerHTML = ''; return; }

  // Pull values per mode. Value modes multiply by the per-symbol lot size to
  // convert contract count → actual ₹ capital.
  const lot = STATE.lotSize || 1;
  const valOf = (r) => {
    if (mode === 'value') return { ce: (r.ceOI || 0) * (r.ceLTP || 0) * lot, pe: (r.peOI || 0) * (r.peLTP || 0) * lot };
    if (mode === 'chg')   return { ce: r.ceChg || 0, pe: r.peChg || 0 };
    if (mode === 'chgvalue') return { ce: (r.ceChg || 0) * (r.ceLTP || 0) * lot, pe: (r.peChg || 0) * (r.peLTP || 0) * lot };
    return { ce: r.ceOI || 0, pe: r.peOI || 0 };
  };
  const isDiverging = mode === 'chg' || mode === 'chgvalue';

  const W = 1000, H = 480, padL = 70, padR = 20, padT = 30, padB = 90;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const allVals = data.flatMap(r => { const v = valOf(r); return [v.ce, v.pe]; });
  const maxAbs = Math.max(...allVals.map(Math.abs), 1);
  const zeroY = isDiverging ? padT + innerH / 2 : padT + innerH;
  const groupW = innerW / data.length;
  const barW = (groupW - 4) / 2;

  const ceGradId = `ceGrad_${svgId}`, peGradId = `peGrad_${svgId}`;
  const defs = `<defs>
    <linearGradient id="${ceGradId}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.6"/>
    </linearGradient>
    <linearGradient id="${peGradId}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ef4444" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#ef4444" stop-opacity="0.6"/>
    </linearGradient>
  </defs>`;

  const valFmt = (v) => (mode === 'value' || mode === 'chgvalue') ? '₹' + fmt(v) : fmt(v);

  const grid = [];
  if (isDiverging) {
    for (let i = -2; i <= 2; i++) {
      const y = zeroY - (i / 2) * (innerH / 2);
      const v = (i / 2) * maxAbs;
      grid.push(`<line x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}" stroke="rgba(255,255,255,0.04)"/>
        <text x="${padL-8}" y="${y+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${v >= 0 ? '+' : ''}${valFmt(v)}</text>`);
    }
  } else {
    for (let i = 0; i <= 5; i++) {
      const v = (maxAbs / 5) * i;
      const y = padT + innerH - (v / maxAbs) * innerH;
      grid.push(`<line x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}" stroke="rgba(255,255,255,0.04)"/>
        <text x="${padL-8}" y="${y+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${valFmt(v)}</text>`);
    }
  }

  const bars = data.map((r, i) => {
    const v = valOf(r);
    const xL = padL + i * groupW + 2;
    const isATM = r.strike === atm;
    const atmBg = isATM ? `<rect x="${xL-2}" y="${padT}" width="${groupW}" height="${innerH}" fill="rgba(139,92,246,0.08)" rx="4"/>` : '';
    let ceRect, peRect;
    if (isDiverging) {
      const ceH = Math.abs(v.ce) / maxAbs * (innerH / 2);
      const peH = Math.abs(v.pe) / maxAbs * (innerH / 2);
      const ceY = v.ce >= 0 ? zeroY - ceH : zeroY;
      const peY = v.pe >= 0 ? zeroY - peH : zeroY;
      // solid for additions (positive), hollow for unwinding (negative)
      const ceFillStyle = v.ce >= 0 ? 'fill="#3b82f6" opacity="0.85"' : 'fill="none" stroke="#3b82f6" stroke-width="2"';
      const peFillStyle = v.pe >= 0 ? 'fill="#ef4444" opacity="0.85"' : 'fill="none" stroke="#ef4444" stroke-width="2"';
      ceRect = `<rect x="${xL}" y="${ceY}" width="${barW}" height="${ceH}" rx="2" ${ceFillStyle}><title>CE ${fmt0(r.strike)} ${v.ce >= 0 ? '+' : ''}${valFmt(v.ce)}</title></rect>`;
      peRect = `<rect x="${xL+barW+2}" y="${peY}" width="${barW}" height="${peH}" rx="2" ${peFillStyle}><title>PE ${fmt0(r.strike)} ${v.pe >= 0 ? '+' : ''}${valFmt(v.pe)}</title></rect>`;
    } else {
      const ceH = (v.ce / maxAbs) * innerH;
      const peH = (v.pe / maxAbs) * innerH;
      ceRect = `<rect x="${xL}" y="${padT+innerH-ceH}" width="${barW}" height="${ceH}" fill="url(#${ceGradId})" rx="2"><title>CE ${fmt0(r.strike)} ${valFmt(v.ce)}</title></rect>`;
      peRect = `<rect x="${xL+barW+2}" y="${padT+innerH-peH}" width="${barW}" height="${peH}" fill="url(#${peGradId})" rx="2"><title>PE ${fmt0(r.strike)} ${valFmt(v.pe)}</title></rect>`;
    }
    const labelColor = isATM ? '#a78bfa' : '#8b91a8';
    const lx = xL + barW + 1, ly = H - padB + 16;
    return `${atmBg}${ceRect}${peRect}
      <text x="${lx}" y="${ly}" fill="${labelColor}" font-size="9" text-anchor="end" font-family="JetBrains Mono" font-weight="${isATM?700:400}" transform="rotate(-45 ${lx} ${ly})">${fmt0(r.strike)}</text>
      ${isATM ? `<text x="${lx}" y="${H-padB+62}" fill="#a78bfa" font-size="9" text-anchor="middle" font-family="DM Sans" font-weight="700" letter-spacing="0.05em">ATM</text>` : ''}`;
  }).join('');

  // Reference lines: SPOT (top label, cyan), MAX PAIN (bottom label, violet-soft)
  let markers = _vline(_strikeToX(STATE.spot, data, padL, groupW),
                       padT, innerH, '#06b6d4', '4,4',
                       `SPOT ${fmt2(STATE.spot)}`, true, padB, H);
  markers += _vline(_strikeToX(STATE.mp, data, padL, groupW),
                    padT, innerH, '#a78bfa', '2,3',
                    `MP ${fmt0(STATE.mp)}`, false, padB, H);
  if (isDiverging) {
    markers += `<line x1="${padL}" y1="${zeroY}" x2="${W-padR}" y2="${zeroY}" stroke="rgba(255,255,255,0.18)"/>`;
  }
  svg.innerHTML = defs + grid.join('') + bars + markers;
}

function renderGammaChart() {
  const svg = $('gammaChart');
  if (!STATE.gex.length) { svg.innerHTML = ''; $('gammaFlipTag').textContent = 'flip —'; return; }
  const atm = nearestATM();
  const data = _sliceAroundATM(STATE.gex, STATE.chartRange);
  if (!data.length) { svg.innerHTML = ''; return; }

  const W = 1000, H = 380, padL = 70, padR = 20, padT = 30, padB = 80;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const maxAbs = Math.max(...data.map(r => Math.abs(r.gex)), 0.001);
  const zeroY = padT + innerH / 2;
  const groupW = innerW / data.length;
  const barW = groupW * 0.7;

  $('gammaFlipTag').textContent = STATE.gammaFlip ? `flip ≈ ${fmt0(STATE.gammaFlip)}` : 'flip —';

  // Y-axis grid
  const grid = [];
  for (let i = -2; i <= 2; i++) {
    const y = zeroY - (i / 2) * (innerH / 2);
    const v = (i / 2) * maxAbs;
    grid.push(`<line x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${y+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${v.toFixed(1)}</text>`);
  }

  const bars = data.map((r, i) => {
    const xL = padL + i * groupW + (groupW - barW) / 2;
    const h = Math.abs(r.gex) / maxAbs * (innerH / 2);
    const y = r.gex >= 0 ? zeroY - h : zeroY;
    const fill = r.gex >= 0 ? '#ef4444' : '#3b82f6';
    const isATM = r.strike === atm;
    const atmBg = isATM ? `<rect x="${padL + i * groupW}" y="${padT}" width="${groupW}" height="${innerH}" fill="rgba(139,92,246,0.08)" rx="4"/>` : '';
    const lx = xL + barW/2, ly = H - padB + 14;
    return `${atmBg}<rect x="${xL}" y="${y}" width="${barW}" height="${h}" fill="${fill}" opacity="0.85" rx="2"><title>${fmt0(r.strike)}: ${r.gex >= 0 ? '+' : ''}${r.gex.toFixed(2)}</title></rect>
      <text x="${lx}" y="${ly}" fill="${isATM?'#a78bfa':'#8b91a8'}" font-size="9" text-anchor="end" font-family="JetBrains Mono" font-weight="${isATM?700:400}" transform="rotate(-45 ${lx} ${ly})">${fmt0(r.strike)}</text>`;
  }).join('');

  // Reference lines: SPOT (cyan), γ FLIP (amber), MAX PAIN (violet-soft)
  let markers = _vline(_strikeToX(STATE.spot, data, padL, groupW),
                       padT, innerH, '#06b6d4', '4,4',
                       `SPOT ${fmt2(STATE.spot)}`, true, padB, H);
  markers += _vline(_strikeToX(STATE.gammaFlip, data, padL, groupW),
                    padT, innerH, '#f59e0b', '3,3',
                    `γ FLIP ${STATE.gammaFlip ? fmt0(STATE.gammaFlip) : ''}`, false, padB, H);
  markers += _vline(_strikeToX(STATE.mp, data, padL, groupW),
                    padT, innerH, '#a78bfa', '2,3',
                    `MP ${fmt0(STATE.mp || 0)}`, false, padB, H);
  // Zero baseline
  markers += `<line x1="${padL}" y1="${zeroY}" x2="${W-padR}" y2="${zeroY}" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>`;

  svg.innerHTML = grid.join('') + bars + markers;
}

/* ---------- VOL & SKEW ---------- */
function renderIVSkew() {
  const svg = $('ivSkewChart');
  if (!STATE.chain.length) { svg.innerHTML = ''; return; }
  const atm = nearestATM();
  const data = _sliceAroundATM(STATE.chain, STATE.chartRangeVol).filter(r => (r.ceIV || 0) > 0 || (r.peIV || 0) > 0);
  if (!data.length) { svg.innerHTML = `<text x="500" y="180" fill="#555a73" text-anchor="middle" font-family="DM Sans">No IV data available</text>`; return; }

  const W = 1000, H = 360, padL = 60, padR = 20, padT = 24, padB = 50;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const ivs = data.flatMap(r => [r.ceIV, r.peIV].filter(v => v > 0));
  const minIV = Math.max(0, Math.min(...ivs) - 2);
  const maxIV = Math.max(...ivs) + 2;
  const range = Math.max(maxIV - minIV, 1);

  const x = (i) => padL + (data.length === 1 ? innerW/2 : (i / (data.length - 1)) * innerW);
  const y = (v) => padT + innerH - ((v - minIV) / range) * innerH;

  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const yy = padT + (innerH / 4) * i;
    const vv = maxIV - (range / 4) * i;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${yy+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${vv.toFixed(1)}</text>`);
  }

  const cePath = data.map((r, i) => `${i===0?'M':'L'} ${x(i)} ${y(r.ceIV || minIV)}`).join(' ');
  const pePath = data.map((r, i) => `${i===0?'M':'L'} ${x(i)} ${y(r.peIV || minIV)}`).join(' ');
  const ceDots = data.map((r, i) => r.ceIV > 0 ? `<circle cx="${x(i)}" cy="${y(r.ceIV)}" r="3" fill="#3b82f6"><title>CE ${fmt0(r.strike)}: ${r.ceIV.toFixed(2)}%</title></circle>` : '').join('');
  const peDots = data.map((r, i) => r.peIV > 0 ? `<circle cx="${x(i)}" cy="${y(r.peIV)}" r="3" fill="#ef4444"><title>PE ${fmt0(r.strike)}: ${r.peIV.toFixed(2)}%</title></circle>` : '').join('');

  // Strike labels
  const labels = data.map((r, i) => {
    if (i % 3 !== 0 && r.strike !== atm) return '';
    const isATM = r.strike === atm;
    return `<text x="${x(i)}" y="${H-padB+18}" fill="${isATM?'#a78bfa':'#8b91a8'}" font-size="10" text-anchor="middle" font-family="JetBrains Mono" font-weight="${isATM?700:400}">${fmt0(r.strike)}</text>`;
  }).join('');

  // ATM vertical
  const atmIdx = data.findIndex(r => r.strike === atm);
  const atmLine = atmIdx >= 0 ? `<line x1="${x(atmIdx)}" y1="${padT}" x2="${x(atmIdx)}" y2="${padT+innerH}" stroke="#8b5cf6" stroke-width="1" stroke-dasharray="4,4" opacity="0.7"/>` : '';

  // Skew metric: avg PE OTM IV - avg CE OTM IV
  let ceSum = 0, ceN = 0, peSum = 0, peN = 0;
  for (const r of data) {
    if (r.strike < (atm || 0) && r.peIV > 0) { peSum += r.peIV; peN++; }
    if (r.strike > (atm || 0) && r.ceIV > 0) { ceSum += r.ceIV; ceN++; }
  }
  const peAvg = peN ? peSum / peN : 0;
  const ceAvg = ceN ? ceSum / ceN : 0;
  const skew = peAvg - ceAvg;
  const skewLab = skew > 1 ? 'PUT skew (bearish hedging)' : skew < -1 ? 'CALL skew (squeeze risk)' : 'Flat';
  const skewCls = skew > 1 ? 'bear' : skew < -1 ? 'bull' : 'neutral';
  $('skewTag').className = `tag ${skewCls}`;
  $('skewTag').textContent = `Δ ${skew >= 0 ? '+' : ''}${skew.toFixed(2)} · ${skewLab}`;

  svg.innerHTML = grid.join('') + atmLine +
    `<path d="${cePath}" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linejoin="round"/>` +
    `<path d="${pePath}" fill="none" stroke="#ef4444" stroke-width="2" stroke-linejoin="round"/>` +
    ceDots + peDots + labels;
}

function renderStraddleHistory() {
  const svg = $('straddleChart');
  const series = STATE.straddleSeries.filter(s => s.straddle > 0);
  if (STATE.atmStraddle && STATE.atmStrike) {
    $('straddleCurrent').innerHTML = `<span style="color:var(--violet-soft)">${fmt2(STATE.atmStraddle)}</span> <span style="font-size:13px;color:var(--text-faint);font-weight:500">at ${fmt0(STATE.atmStrike)}</span>`;
    const pct = STATE.spot ? (STATE.atmStraddle / STATE.spot * 100) : 0;
    $('straddleTag').textContent = `${pct.toFixed(2)}% of spot`;
  }
  if (!series.length) {
    svg.innerHTML = `<text x="300" y="110" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">No history yet — snapshots arrive every 3 min during market hours</text>`;
    return;
  }
  const W = 600, H = 220, padL = 50, padR = 14, padT = 14, padB = 24;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const vals = series.map(s => s.straddle);
  let mn = Math.min(...vals), mx = Math.max(...vals);
  if (mn === mx) { mn -= 1; mx += 1; }
  const range = mx - mn;
  const x = (i) => padL + (series.length === 1 ? innerW/2 : (i / (series.length - 1)) * innerW);
  const y = (v) => padT + innerH - ((v - mn) / range) * innerH;
  const path = series.map((s,i) => `${i===0?'M':'L'} ${x(i)} ${y(s.straddle)}`).join(' ');
  const area = path + ` L ${x(series.length-1)} ${padT+innerH} L ${x(0)} ${padT+innerH} Z`;
  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const yy = padT + (innerH / 4) * i;
    const vv = mx - (range / 4) * i;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-6}" y="${yy+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${vv.toFixed(0)}</text>`);
  }
  const last = series[series.length-1];
  svg.innerHTML = `
    <defs><linearGradient id="strGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#8b5cf6" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#8b5cf6" stop-opacity="0"/>
    </linearGradient></defs>
    ${grid.join('')}
    <path d="${area}" fill="url(#strGrad)"/>
    <path d="${path}" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-linejoin="round"/>
    <circle cx="${x(series.length-1)}" cy="${y(last.straddle)}" r="3" fill="#8b5cf6"/>`;
}

function renderPCRComparison() {
  const svg = $('pcrCmpChart');
  if (!STATE.pcrHistory.length) {
    svg.innerHTML = `<text x="300" y="110" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">Need at least 2 snapshots</text>`;
    return;
  }
  const len = Math.min(STATE.pcrHistory.length, STATE.volPcrHistory.length, STATE.wpcrHistory.length);
  if (len < 1) { svg.innerHTML = ''; return; }
  const oi = STATE.pcrHistory.slice(-len);
  const vol = STATE.volPcrHistory.slice(-len);
  const wp = STATE.wpcrHistory.slice(-len);

  const W = 600, H = 220, padL = 50, padR = 14, padT = 14, padB = 24;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const all = [...oi.map(s => s.v), ...vol.map(s => s.v), ...wp.map(s => s.v)].filter(v => v > 0);
  let mn = Math.min(...all), mx = Math.max(...all);
  if (mn === mx) { mn -= 0.2; mx += 0.2; }
  const range = mx - mn;
  const x = (i) => padL + (len === 1 ? innerW/2 : (i / (len - 1)) * innerW);
  const y = (v) => padT + innerH - ((v - mn) / range) * innerH;
  const mkPath = (s) => s.map((p,i) => `${i===0?'M':'L'} ${x(i)} ${y(p.v)}`).join(' ');

  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const yy = padT + (innerH / 4) * i;
    const vv = mx - (range / 4) * i;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-6}" y="${yy+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${vv.toFixed(2)}</text>`);
  }
  const refs = [0.8, 1.2].map(v => {
    if (v >= mn && v <= mx) {
      const yy = y(v);
      const c = v > 1 ? '#ef4444' : '#3b82f6';
      return `<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="${c}" stroke-width="1" stroke-dasharray="3,3" opacity="0.4"/>`;
    }
    return '';
  }).join('');
  svg.innerHTML = grid.join('') + refs +
    `<path d="${mkPath(oi)}" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-linejoin="round"/>` +
    `<path d="${mkPath(vol)}" fill="none" stroke="#06b6d4" stroke-width="2" stroke-linejoin="round"/>` +
    `<path d="${mkPath(wp)}" fill="none" stroke="#f59e0b" stroke-width="1.6" stroke-linejoin="round" stroke-dasharray="4,3"/>` +
    `<circle cx="${x(len-1)}" cy="${y(oi[len-1].v)}" r="3" fill="#8b5cf6"/>` +
    `<circle cx="${x(len-1)}" cy="${y(vol[len-1].v)}" r="3" fill="#06b6d4"/>` +
    (wp[len-1].v > 0 ? `<circle cx="${x(len-1)}" cy="${y(wp[len-1].v)}" r="3" fill="#f59e0b"/>` : '');
}

function renderPremiumSkew() {
  const svg = $('premiumSkewChart');
  if (!STATE.chain.length) { svg.innerHTML = ''; return; }
  const atm = nearestATM();
  const data = _sliceAroundATM(STATE.chain, STATE.chartRangeVol).filter(r => r.ceLTP > 0 || r.peLTP > 0);
  if (!data.length) { svg.innerHTML = ''; return; }

  const W = 1000, H = 320, padL = 60, padR = 20, padT = 24, padB = 44;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const ltps = data.flatMap(r => [r.ceLTP, r.peLTP]).filter(v => v > 0);
  const mx = Math.max(...ltps);
  const x = (i) => padL + (data.length === 1 ? innerW/2 : (i / (data.length - 1)) * innerW);
  const y = (v) => padT + innerH - (v / mx) * innerH;
  const cePath = data.map((r,i) => `${i===0?'M':'L'} ${x(i)} ${y(r.ceLTP || 0)}`).join(' ');
  const pePath = data.map((r,i) => `${i===0?'M':'L'} ${x(i)} ${y(r.peLTP || 0)}`).join(' ');

  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const yy = padT + (innerH/4) * i;
    const vv = mx - (mx/4) * i;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${yy+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${vv.toFixed(0)}</text>`);
  }
  const labels = data.map((r,i) => {
    const isATM = r.strike === atm;
    if (i % 3 !== 0 && !isATM) return '';
    return `<text x="${x(i)}" y="${H-padB+18}" fill="${isATM?'#a78bfa':'#8b91a8'}" font-size="10" text-anchor="middle" font-family="JetBrains Mono" font-weight="${isATM?700:400}">${fmt0(r.strike)}</text>`;
  }).join('');
  const atmIdx = data.findIndex(r => r.strike === atm);
  const atmLine = atmIdx >= 0 ? `<line x1="${x(atmIdx)}" y1="${padT}" x2="${x(atmIdx)}" y2="${padT+innerH}" stroke="#8b5cf6" stroke-width="1" stroke-dasharray="4,4" opacity="0.7"/>` : '';

  svg.innerHTML = grid.join('') + atmLine +
    `<path d="${cePath}" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linejoin="round"/>` +
    `<path d="${pePath}" fill="none" stroke="#ef4444" stroke-width="2" stroke-linejoin="round"/>` +
    data.map((r,i) => (r.ceLTP > 0 ? `<circle cx="${x(i)}" cy="${y(r.ceLTP)}" r="2.5" fill="#3b82f6"><title>CE ${fmt0(r.strike)}: ${r.ceLTP.toFixed(2)}</title></circle>` : '')).join('') +
    data.map((r,i) => (r.peLTP > 0 ? `<circle cx="${x(i)}" cy="${y(r.peLTP)}" r="2.5" fill="#ef4444"><title>PE ${fmt0(r.strike)}: ${r.peLTP.toFixed(2)}</title></circle>` : '')).join('') +
    labels;
}

function renderStraddleLadder() {
  const svg = $('straddleLadderChart');
  if (!STATE.chain.length) { svg.innerHTML = ''; return; }
  const atm = nearestATM();
  // Straddle ladder defaults to a tighter view than IV/premium — cap at 10 either side
  // unless the user has explicitly asked for "All".
  const range = STATE.chartRangeVol === 0 ? 0 : Math.min(STATE.chartRangeVol, 10);
  const data = _sliceAroundATM(STATE.chain, range);
  if (!data.length) { svg.innerHTML = ''; return; }

  const W = 1000, H = 360, padL = 70, padR = 20, padT = 30, padB = 60;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const totals = data.map(r => (r.ceLTP || 0) + (r.peLTP || 0));
  const mx = Math.max(...totals, 1);
  const groupW = innerW / data.length;
  const barW = groupW * 0.65;

  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const v = (mx / 4) * i;
    const y = padT + innerH - (v / mx) * innerH;
    grid.push(`<line x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${y+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${v.toFixed(0)}</text>`);
  }
  const bars = data.map((r, i) => {
    const xL = padL + i * groupW + (groupW - barW) / 2;
    const ce = r.ceLTP || 0, pe = r.peLTP || 0;
    const total = ce + pe;
    const ceH = (ce / mx) * innerH;
    const peH = (pe / mx) * innerH;
    const isATM = r.strike === atm;
    const labelColor = isATM ? '#a78bfa' : '#8b91a8';
    return `<rect x="${xL}" y="${padT+innerH-ceH}" width="${barW}" height="${ceH}" fill="#3b82f6" rx="2" opacity="0.85"><title>CE ${fmt0(r.strike)} ${ce.toFixed(2)}</title></rect>
      <rect x="${xL}" y="${padT+innerH-ceH-peH}" width="${barW}" height="${peH}" fill="#ef4444" rx="2" opacity="0.85"><title>PE ${fmt0(r.strike)} ${pe.toFixed(2)}</title></rect>
      <text x="${xL+barW/2}" y="${padT+innerH-ceH-peH-6}" fill="#a78bfa" font-size="11" text-anchor="middle" font-family="JetBrains Mono" font-weight="600">${total.toFixed(0)}</text>
      <text x="${xL+barW/2}" y="${H-padB+18}" fill="${labelColor}" font-size="10" text-anchor="middle" font-family="JetBrains Mono" font-weight="${isATM?700:400}">${fmt0(r.strike)}</text>
      ${isATM ? `<text x="${xL+barW/2}" y="${H-padB+34}" fill="#a78bfa" font-size="9" text-anchor="middle" font-family="DM Sans" font-weight="700" letter-spacing="0.05em">ATM</text>` : ''}`;
  }).join('');

  svg.innerHTML = grid.join('') + bars;
}

function renderCumOI() {
  const svg = $('cumOIChart');
  const f = STATE.intradayFlow;
  if (!f || !f.series || f.series.length < 2) {
    svg.innerHTML = `<text x="500" y="160" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">Need at least 2 snapshots — they accumulate every 3 min during market hours</text>`;
    return;
  }
  const series = f.series;
  const W = 1000, H = 320, padL = 70, padR = 20, padT = 24, padB = 50;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const allVals = series.flatMap(s => [s.totalCeChg, s.totalPeChg, s.netChg]);
  const maxAbs = Math.max(...allVals.map(Math.abs), 1);
  const zeroY = padT + innerH / 2;
  const x = (i) => padL + (series.length === 1 ? innerW/2 : (i / (series.length - 1)) * innerW);
  const y = (v) => zeroY - (v / maxAbs) * (innerH / 2);

  const grid = [];
  for (let i = -2; i <= 2; i++) {
    const yy = zeroY - (i / 2) * (innerH / 2);
    const v = (i / 2) * maxAbs;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${yy+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${v >= 0 ? '+' : ''}${fmt(v)}</text>`);
  }

  const peArea = series.map((s,i) => `${i===0?'M':'L'} ${x(i)} ${y(s.totalPeChg)}`).join(' ') + ` L ${x(series.length-1)} ${zeroY} L ${x(0)} ${zeroY} Z`;
  const ceArea = series.map((s,i) => `${i===0?'M':'L'} ${x(i)} ${y(s.totalCeChg)}`).join(' ') + ` L ${x(series.length-1)} ${zeroY} L ${x(0)} ${zeroY} Z`;
  const pePath = series.map((s,i) => `${i===0?'M':'L'} ${x(i)} ${y(s.totalPeChg)}`).join(' ');
  const cePath = series.map((s,i) => `${i===0?'M':'L'} ${x(i)} ${y(s.totalCeChg)}`).join(' ');
  const netPath = series.map((s,i) => `${i===0?'M':'L'} ${x(i)} ${y(s.netChg)}`).join(' ');

  const tickEvery = Math.max(1, Math.floor(series.length / 6));
  const xLabels = series.map((s,i) => i % tickEvery === 0 || i === series.length-1
    ? `<text x="${x(i)}" y="${H-padB+16}" fill="#555a73" font-size="10" text-anchor="middle" font-family="JetBrains Mono">${escapeHTML(s.time)}</text>` : '').join('');

  const baseline = `<line x1="${padL}" y1="${zeroY}" x2="${W-padR}" y2="${zeroY}" stroke="rgba(255,255,255,0.18)"/>`;

  svg.innerHTML = `
    <defs>
      <linearGradient id="peCumGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ef4444" stop-opacity="0.25"/><stop offset="100%" stop-color="#ef4444" stop-opacity="0"/></linearGradient>
      <linearGradient id="ceCumGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#3b82f6" stop-opacity="0.25"/><stop offset="100%" stop-color="#3b82f6" stop-opacity="0"/></linearGradient>
    </defs>
    ${grid.join('')}
    <path d="${peArea}" fill="url(#peCumGrad)"/>
    <path d="${ceArea}" fill="url(#ceCumGrad)"/>
    <path d="${pePath}" fill="none" stroke="#ef4444" stroke-width="2" stroke-linejoin="round"/>
    <path d="${cePath}" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linejoin="round"/>
    <path d="${netPath}" fill="none" stroke="#8b5cf6" stroke-width="1.6" stroke-linejoin="round" stroke-dasharray="4,3"/>
    ${baseline}
    ${xLabels}`;
}

/* ---------- PULSE: Spot vs CE/PE ΔOI (3 lines, dual Y-axis) ---------- */
function populatePulseDateSelect() {
  const sel = $('pulseDateSel');
  const f = STATE.intradayFlow;
  if (!sel || !f || !f.series || !f.series.length) return;
  const dates = [...new Set(f.series.map(s => (s.timestamp || '').slice(0, 10)).filter(Boolean))].sort();
  const prev = STATE.pulseDate;
  const latest = dates[dates.length - 1];
  const chosen = (prev && dates.includes(prev)) ? prev : latest;
  // Render in reverse chronological order (most-recent first)
  sel.innerHTML = dates.slice().reverse().map(d => {
    const dt = new Date(d + 'T00:00:00');
    const label = dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit', weekday: 'short' });
    return `<option value="${d}" ${d === chosen ? 'selected' : ''}>${label}</option>`;
  }).join('');
  STATE.pulseDate = chosen;
  syncPulseSlider();
}

function _pulseSeriesForDate(allSeries, date) {
  if (!date) return [];
  return allSeries.filter(s => (s.timestamp || '').slice(0, 10) === date);
}

function _tsToMinFrom915(ts) {
  // Return minutes since 09:15 on that date based on the timestamp's HH:MM in IST
  // The timestamp is in IST already (e.g. 2026-05-04T13:18:00+05:30)
  const m = String(ts).match(/T(\d{2}):(\d{2})/);
  if (!m) return null;
  const h = parseInt(m[1], 10);
  const mn = parseInt(m[2], 10);
  return h * 60 + mn - (9 * 60 + 15);
}

function renderPulse() {
  const svg = $('pulseChart');
  const f = STATE.intradayFlow;
  if (!svg) return;
  if (!f || !f.series || f.series.length < 2) {
    svg.innerHTML = `<text x="500" y="190" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">Need at least 2 snapshots — they accumulate every 3 min during market hours</text>`;
    return;
  }

  // Pick the date if not yet chosen (first render)
  if (!STATE.pulseDate) {
    const dates = [...new Set(f.series.map(s => (s.timestamp || '').slice(0, 10)).filter(Boolean))].sort();
    STATE.pulseDate = dates[dates.length - 1] || null;
  }

  // Filter to chosen date, then to time range
  let series = _pulseSeriesForDate(f.series, STATE.pulseDate);
  series = series.filter(s => {
    const min = _tsToMinFrom915(s.timestamp);
    if (min === null) return true;
    return min >= STATE.pulseStartMin && min <= STATE.pulseEndMin;
  });
  if (series.length < 2) {
    svg.innerHTML = `<text x="500" y="190" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">No data in this window for ${escapeHTML(STATE.pulseDate || '—')} — widen the slider or pick another date</text>`;
    return;
  }

  // ΔOI baseline rebasing per STATE.pulseRefMode
  // 'prev'   = no rebase (raw totalCeChg/totalPeChg are already cumulative since prior close)
  // 'day'    = subtract first snapshot of the chosen DATE (across full day, even outside slider)
  // 'window' = subtract first snapshot in the visible WINDOW (after date+time filtering)
  const ref = STATE.pulseRefMode || 'prev';
  let baseCe = 0, basePe = 0, refLabel = 'vs prior close';
  if (ref === 'day') {
    const dayPoints = _pulseSeriesForDate(f.series, STATE.pulseDate);
    if (dayPoints.length) {
      baseCe = dayPoints[0].totalCeChg || 0;
      basePe = dayPoints[0].totalPeChg || 0;
      refLabel = `vs day start (${dayPoints[0].time})`;
    }
  } else if (ref === 'window' && series.length) {
    baseCe = series[0].totalCeChg || 0;
    basePe = series[0].totalPeChg || 0;
    refLabel = `vs window start (${series[0].time})`;
  }
  const ceAt = (s) => (s.totalCeChg || 0) - baseCe;
  const peAt = (s) => (s.totalPeChg || 0) - basePe;
  const hint = $('pulseRefHint'); if (hint) hint.textContent = refLabel;

  const W = 1000, H = 380, padL = 70, padR = 80, padT = 28, padB = 50;
  const innerW = W - padL - padR, innerH = H - padT - padB;

  // Left axis: spot
  const spots = series.map(s => s.spot).filter(v => v > 0);
  let sMn = Math.min(...spots), sMx = Math.max(...spots);
  if (sMn === sMx) { sMn -= 1; sMx += 1; }
  const sPad = Math.max((sMx - sMn) * 0.15, sMx * 0.0005);
  sMn -= sPad; sMx += sPad;

  // Right axis: ΔOI, symmetric around zero (uses rebased values)
  const oiVals = series.flatMap(s => [ceAt(s), peAt(s)]);
  const oiMaxAbs = Math.max(...oiVals.map(Math.abs), 1);

  const x = (i) => padL + (series.length === 1 ? innerW / 2 : (i / (series.length - 1)) * innerW);
  const ySpot = (v) => padT + innerH - ((v - sMn) / (sMx - sMn)) * innerH;
  const zeroY = padT + innerH / 2;
  const yOI = (v) => zeroY - (v / oiMaxAbs) * (innerH / 2);

  // Gridlines + dual-axis labels
  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const yy = padT + (innerH / 4) * i;
    const sv = sMx - ((sMx - sMn) / 4) * i;
    const ov = oiMaxAbs - (oiMaxAbs * 2 / 4) * i;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${yy+4}" fill="#f0b429" font-size="10" text-anchor="end" font-family="JetBrains Mono">${sv.toFixed(0)}</text>
      <text x="${W-padR+8}" y="${yy+4}" fill="#9ca3af" font-size="10" text-anchor="start" font-family="JetBrains Mono">${ov >= 0 ? '+' : ''}${fmt(ov)}</text>`);
  }

  // Paths
  const spotPath = series.map((s, i) => `${i===0?'M':'L'} ${x(i)} ${ySpot(s.spot)}`).join(' ');
  const spotArea = spotPath + ` L ${x(series.length-1)} ${padT+innerH} L ${x(0)} ${padT+innerH} Z`;
  const cePath = series.map((s, i) => `${i===0?'M':'L'} ${x(i)} ${yOI(ceAt(s))}`).join(' ');
  const pePath = series.map((s, i) => `${i===0?'M':'L'} ${x(i)} ${yOI(peAt(s))}`).join(' ');

  // X-axis time ticks
  const tickEvery = Math.max(1, Math.floor(series.length / 6));
  const xLabels = series.map((s, i) =>
    (i % tickEvery === 0 || i === series.length - 1)
      ? `<text x="${x(i)}" y="${H-padB+16}" fill="#555a73" font-size="10" text-anchor="middle" font-family="JetBrains Mono">${escapeHTML(s.time)}</text>`
      : ''
  ).join('');

  const zeroLine = `<line x1="${padL}" y1="${zeroY}" x2="${W-padR}" y2="${zeroY}" stroke="rgba(255,255,255,0.18)" stroke-dasharray="3,3"/>`;

  // Last-point dots for visual anchor
  const last = series[series.length - 1];
  const lastDots = `
    <circle cx="${x(series.length-1)}" cy="${ySpot(last.spot)}" r="3.5" fill="#f0b429"/>
    <circle cx="${x(series.length-1)}" cy="${yOI(ceAt(last))}" r="3" fill="#3b82f6"/>
    <circle cx="${x(series.length-1)}" cy="${yOI(peAt(last))}" r="3" fill="#ef4444"/>`;

  svg.innerHTML = `
    <defs>
      <linearGradient id="pulseSpotGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#f0b429" stop-opacity="0.15"/>
        <stop offset="100%" stop-color="#f0b429" stop-opacity="0"/>
      </linearGradient>
    </defs>
    ${grid.join('')}
    <path d="${spotArea}" fill="url(#pulseSpotGrad)"/>
    <path d="${spotPath}" fill="none" stroke="#f0b429" stroke-width="2.4" stroke-linejoin="round"/>
    <path d="${cePath}" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linejoin="round"/>
    <path d="${pePath}" fill="none" stroke="#ef4444" stroke-width="2" stroke-linejoin="round"/>
    ${zeroLine}
    ${xLabels}
    ${lastDots}
    <text x="${padL}" y="16" fill="#f0b429" font-size="10" font-family="JetBrains Mono" font-weight="600">SPOT (₹)</text>
    <text x="${W-padR}" y="16" fill="#9ca3af" font-size="10" text-anchor="end" font-family="JetBrains Mono" font-weight="600">ΔOI (contracts)</text>
    <g id="pulseCrosshair" pointer-events="none"></g>`;

  // Hover crosshair — vertical line + tooltip showing time, spot, CE ΔOI, PE ΔOI at nearest point
  const renderCrosshair = (idx) => {
    const ch = $('pulseCrosshair');
    if (!ch) return;
    if (idx < 0 || idx >= series.length) { ch.innerHTML = ''; return; }
    const s = series[idx];
    const cx = x(idx);
    const ceV = ceAt(s), peV = peAt(s);
    const spotY = ySpot(s.spot), ceY = yOI(ceV), peY = yOI(peV);
    const ttW = 158, ttH = 76;
    const ttX = (cx + ttW + 12 > W - padR) ? (cx - ttW - 10) : (cx + 10);
    const ttY = padT + 6;
    const sign = (n) => n > 0 ? '+' : '';
    ch.innerHTML = `
      <line x1="${cx}" y1="${padT}" x2="${cx}" y2="${padT + innerH}" stroke="rgba(255,255,255,0.35)" stroke-width="1" stroke-dasharray="3,3"/>
      <circle cx="${cx}" cy="${spotY}" r="4.5" fill="#f0b429" stroke="#0b0e14" stroke-width="2"/>
      <circle cx="${cx}" cy="${ceY}"   r="4"   fill="#3b82f6" stroke="#0b0e14" stroke-width="2"/>
      <circle cx="${cx}" cy="${peY}"   r="4"   fill="#ef4444" stroke="#0b0e14" stroke-width="2"/>
      <g transform="translate(${ttX} ${ttY})">
        <rect x="0" y="0" width="${ttW}" height="${ttH}" rx="6"
              fill="rgba(11,14,20,0.95)" stroke="rgba(255,255,255,0.18)"/>
        <text x="10" y="16" fill="#c8cdd8" font-size="10" font-family="JetBrains Mono" font-weight="600">${escapeHTML(s.time)}</text>
        <text x="10" y="32" fill="#f0b429" font-size="10.5" font-family="JetBrains Mono">SPOT ${fmt2(s.spot)}</text>
        <text x="10" y="48" fill="#3b82f6" font-size="10.5" font-family="JetBrains Mono">CE  ${sign(ceV)}${fmt(ceV)}</text>
        <text x="10" y="64" fill="#ef4444" font-size="10.5" font-family="JetBrains Mono">PE  ${sign(peV)}${fmt(peV)}</text>
      </g>`;
  };
  svg.onmousemove = (e) => {
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const xPx = ((e.clientX - rect.left) / rect.width) * W;
    if (xPx < padL - 4 || xPx > W - padR + 4) { renderCrosshair(-1); return; }
    let bestIdx = 0, bestD = Infinity;
    for (let i = 0; i < series.length; i++) {
      const d = Math.abs(x(i) - xPx);
      if (d < bestD) { bestD = d; bestIdx = i; }
    }
    renderCrosshair(bestIdx);
  };
  svg.onmouseleave = () => renderCrosshair(-1);
  svg.style.cursor = 'crosshair';
}

function renderComboChart() {
  const svg = $('comboChart');
  const d = STATE.comboData;
  if (!d || !d.series || d.series.length < 2) {
    svg.innerHTML = `<text x="500" y="180" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">Pick a strike above and wait for ≥2 snapshots</text>`;
    $('comboTag').textContent = 'pick a strike';
    return;
  }
  const side = STATE.comboSide;
  const series = d.series;
  $('comboTag').textContent = `${fmt0(d.strike)} ${side} · premium + OI over time`;

  const ltps = series.map(s => side === 'CE' ? s.ceLTP : s.peLTP);
  const ois  = series.map(s => side === 'CE' ? s.ceOI  : s.peOI);
  const spots = series.map(s => s.spot);

  const W = 1000, H = 360, padL = 70, padR = 80, padT = 24, padB = 50;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  let ltpMx = Math.max(...ltps, 1), ltpMn = Math.min(...ltps, 0);
  if (ltpMn === ltpMx) ltpMx = ltpMn + 1;
  let oiMx = Math.max(...ois, 1);

  const x = (i) => padL + (series.length === 1 ? innerW/2 : (i / (series.length - 1)) * innerW);
  const yL = (v) => padT + innerH - ((v - ltpMn) / Math.max(ltpMx - ltpMn, 1)) * innerH;
  const yR = (v) => padT + innerH - (v / oiMx) * innerH;

  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const yy = padT + (innerH/4) * i;
    const lv = ltpMx - ((ltpMx - ltpMn)/4) * i;
    const rv = oiMx - (oiMx/4) * i;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${yy+4}" fill="#a78bfa" font-size="10" text-anchor="end" font-family="JetBrains Mono">${lv.toFixed(1)}</text>
      <text x="${W-padR+8}" y="${yy+4}" fill="#06b6d4" font-size="10" text-anchor="start" font-family="JetBrains Mono">${fmt(rv)}</text>`);
  }

  const ltpPath = series.map((s,i) => `${i===0?'M':'L'} ${x(i)} ${yL(side === 'CE' ? s.ceLTP : s.peLTP)}`).join(' ');
  const oiPath  = series.map((s,i) => `${i===0?'M':'L'} ${x(i)} ${yR(side === 'CE' ? s.ceOI  : s.peOI )}`).join(' ');
  // Spot line on its own normalized scale (overlaid)
  const spotMn = Math.min(...spots), spotMx = Math.max(...spots);
  const ySpot = (v) => padT + innerH - ((v - spotMn) / Math.max(spotMx - spotMn, 1)) * innerH;
  const spotPath = series.map((s,i) => `${i===0?'M':'L'} ${x(i)} ${ySpot(s.spot)}`).join(' ');

  const tickEvery = Math.max(1, Math.floor(series.length / 6));
  const xLabels = series.map((s,i) => i % tickEvery === 0 || i === series.length-1
    ? `<text x="${x(i)}" y="${H-padB+16}" fill="#555a73" font-size="10" text-anchor="middle" font-family="JetBrains Mono">${escapeHTML(s.time)}</text>` : '').join('');

  svg.innerHTML = grid.join('') +
    `<path d="${spotPath}" fill="none" stroke="#9ca3af" stroke-width="1.5" stroke-linejoin="round" opacity="0.5"/>` +
    `<path d="${oiPath}"  fill="none" stroke="#06b6d4" stroke-width="2" stroke-linejoin="round"/>` +
    `<path d="${ltpPath}" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-linejoin="round"/>` +
    `<text x="${padL-50}" y="${padT-8}" fill="#a78bfa" font-size="10" font-family="DM Sans" font-weight="600">LTP</text>` +
    `<text x="${W-padR+50}" y="${padT-8}" fill="#06b6d4" font-size="10" font-family="DM Sans" font-weight="600" text-anchor="end">OI</text>` +
    xLabels;
}

/* ---------- ANALYTICS ---------- */
function renderAnalytics() {
  renderSynopsis();
  renderPCRGauge();
  renderLineChart('pcrChart', STATE.pcrHistory, '#8b5cf6', STATE.pcrSmaOn ? 5 : 0);
  renderLineChart('spotChart', STATE.spotHistory, '#06b6d4');
  renderOIHistory();
  renderSpurts();
  renderBuildup();
  renderActivityScanner();
  renderZScore();
  renderTrap();
}

function classifyRegime() {
  // Multi-signal regime classifier
  const signals = [];
  if (STATE.pcr > 1.2) signals.push('bull');
  else if (STATE.pcr < 0.8) signals.push('bear');
  if (STATE.volPcr > 1.2) signals.push('bull');
  else if (STATE.volPcr > 0 && STATE.volPcr < 0.8) signals.push('bear');
  if (STATE.wpcr > 1.2) signals.push('bull');
  else if (STATE.wpcr > 0 && STATE.wpcr < 0.8) signals.push('bear');
  if (STATE.gammaFlip && STATE.spot) {
    if (STATE.spot > STATE.gammaFlip) signals.push('bull');
    else signals.push('bear');
  }
  // OI behavior — net put-write minus net call-write
  let netPe = 0, netCe = 0;
  for (const r of STATE.chain) { netPe += r.peChg || 0; netCe += r.ceChg || 0; }
  if (netPe - netCe > 100000) signals.push('bull');
  else if (netCe - netPe > 100000) signals.push('bear');

  const bulls = signals.filter(s => s === 'bull').length;
  const bears = signals.filter(s => s === 'bear').length;
  const total = signals.length || 1;
  if (bulls / total >= 0.7) return { regime: 'Bullish', cls: 'bull' };
  if (bears / total >= 0.7) return { regime: 'Bearish', cls: 'bear' };
  if (Math.abs(bulls - bears) <= 1) return { regime: 'Neutral / Mixed', cls: 'neutral' };
  return bulls > bears ? { regime: 'Lean Bullish', cls: 'warn' } : { regime: 'Lean Bearish', cls: 'warn' };
}

function renderSynopsis() {
  const grid = $('synopsisGrid');
  const reg = classifyRegime();
  $('regimeBadge').innerHTML = `<span class="regime-badge ${reg.cls}">●  ${reg.regime}</span>`;
  $('regimeTagInline').textContent = reg.regime;
  $('regimeTagInline').className = `tag ${reg.cls === 'bull' ? 'bull' : reg.cls === 'bear' ? 'bear' : 'neutral'}`;

  const cell = (lab, val, ctx, cls) =>
    `<div class="syno-cell ${cls}"><span class="lab">${lab}</span><span class="val">${val}</span><span class="ctx">${ctx}</span></div>`;

  const pcrCls = STATE.pcr > 1.2 ? 'bull' : STATE.pcr > 0 && STATE.pcr < 0.8 ? 'bear' : 'neutral';
  const volCls = STATE.volPcr > 1.2 ? 'bull' : STATE.volPcr > 0 && STATE.volPcr < 0.8 ? 'bear' : 'neutral';
  const wpcrCls = STATE.wpcr > 1.2 ? 'bull' : STATE.wpcr > 0 && STATE.wpcr < 0.8 ? 'bear' : 'neutral';
  const mpDiff = STATE.spot && STATE.mp ? Math.round(STATE.mp - STATE.spot) : 0;
  const mpCls = mpDiff > 0 ? 'bull' : mpDiff < 0 ? 'bear' : 'neutral';
  const gammaCls = (STATE.gammaFlip && STATE.spot)
    ? (STATE.spot > STATE.gammaFlip ? 'bull' : 'bear')
    : 'neutral';
  const xover = STATE.tpe > STATE.tce ? 'PE > CE' : 'CE > PE';
  const xoverCls = STATE.tpe > STATE.tce ? 'bull' : 'bear';

  // VIX regime
  let vixCell = cell('VIX', '—', 'open Macro', 'neutral');
  const vd = STATE.vixData?.data;
  if (vd) {
    const v = vd.last ?? vd.lastValue ?? vd.LTP ?? 0;
    const cls = v < 12 ? 'bull' : v > 20 ? 'bear' : 'warn';
    const lab = v < 12 ? 'Calm' : v > 20 ? 'Fear' : 'Normal';
    vixCell = cell('India VIX', fmt2(v), lab, cls);
  }

  grid.innerHTML = [
    cell('OI PCR', fmt2(STATE.pcr), pcrCls === 'bull' ? 'Bullish' : pcrCls === 'bear' ? 'Bearish' : 'Neutral', pcrCls),
    cell('Vol PCR', fmt2(STATE.volPcr), 'today\'s flow', volCls),
    cell('WPCR ₹', fmt2(STATE.wpcr), 'capital weighted', wpcrCls),
    cell('Max Pain', fmt0(STATE.mp), `${mpDiff >= 0 ? '+' : ''}${mpDiff} from spot`, mpCls),
    cell('γ Flip', STATE.gammaFlip ? fmt0(STATE.gammaFlip) : '—',
         (STATE.gammaFlip && STATE.spot) ? (STATE.spot > STATE.gammaFlip ? 'Spot above flip' : 'Spot below flip') : '—',
         gammaCls),
    cell('OI Crossover', xover, STATE.tpe > STATE.tce ? 'PE-heavy book' : 'CE-heavy book', xoverCls),
    cell('Total CE OI', fmt(STATE.tce), 'contract count', 'neutral'),
    cell('Total PE OI', fmt(STATE.tpe), 'contract count', 'neutral'),
    vixCell,
  ].join('');
}

function strengthOf(absChg) {
  if (absChg >= 200000) return ['strong', 'STRONG'];
  if (absChg >= 80000)  return ['mod', 'MOD'];
  return ['weak', 'WEAK'];
}

function renderActivityScanner() {
  const tb = $('activityBody');
  if (!STATE.chain.length) { tb.innerHTML = ''; return; }
  const list = STATE.chain.flatMap(r => {
    const out = [];
    if (Math.abs(r.ceChg) > 10000) out.push({ side: 'CE', strike: r.strike, chg: r.ceChg, oi: r.ceOI, vol: r.ceVol });
    if (Math.abs(r.peChg) > 10000) out.push({ side: 'PE', strike: r.strike, chg: r.peChg, oi: r.peOI, vol: r.peVol });
    return out;
  }).sort((a,b) => Math.abs(b.chg) - Math.abs(a.chg)).slice(0, 14);
  if (!list.length) { tb.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-faint);padding:14px">No significant activity yet</td></tr>'; return; }
  tb.innerHTML = list.map(s => {
    const [sCls, sLab] = strengthOf(Math.abs(s.chg));
    const cls = s.chg > 0 ? 'delta-pos' : 'delta-neg';
    const sign = s.chg > 0 ? '+' : '';
    return `<tr>
      <td class="label-cell">${fmt0(s.strike)}</td>
      <td>${s.side}</td>
      <td class="${cls}">${sign}${fmt(s.chg)} <span class="strength-tag ${sCls}">${sLab}</span></td>
      <td>${fmt(s.oi)}</td>
      <td>${fmt(s.vol)}</td>
    </tr>`;
  }).join('');
}

function renderZScore() {
  const tb = $('zScoreBody');
  // Build per-strike OI mean from oiHistory or chain. Use straddleSeries-like: pull from STATE.snapshots (we have meta only — totals not per-strike).
  // Instead, use the raw chain OI vs the mean across the recent multi-strike data if available.
  // Simpler heuristic: compute z-score of each strike's OI vs the mean+std of all strikes' OI in current chain.
  if (!STATE.chain.length) { tb.innerHTML = ''; return; }
  const ceVals = STATE.chain.map(r => r.ceOI).filter(v => v > 0);
  const peVals = STATE.chain.map(r => r.peOI).filter(v => v > 0);
  const stat = (arr) => {
    const m = arr.reduce((a,b) => a+b, 0) / arr.length;
    const v = arr.reduce((a,b) => a + (b-m)*(b-m), 0) / arr.length;
    return { m, sd: Math.sqrt(v) };
  };
  const ce = ceVals.length ? stat(ceVals) : { m:0, sd:0 };
  const pe = peVals.length ? stat(peVals) : { m:0, sd:0 };
  const rows = [];
  for (const r of STATE.chain) {
    if (r.ceOI > 0 && ce.sd > 0) {
      const z = (r.ceOI - ce.m) / ce.sd;
      if (Math.abs(z) >= 2) rows.push({ strike: r.strike, side: 'CE', oi: r.ceOI, m: ce.m, z });
    }
    if (r.peOI > 0 && pe.sd > 0) {
      const z = (r.peOI - pe.m) / pe.sd;
      if (Math.abs(z) >= 2) rows.push({ strike: r.strike, side: 'PE', oi: r.peOI, m: pe.m, z });
    }
  }
  rows.sort((a,b) => Math.abs(b.z) - Math.abs(a.z));
  if (!rows.length) { tb.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-faint);padding:14px">No strikes with |z| ≥ 2 yet</td></tr>'; return; }
  tb.innerHTML = rows.slice(0, 10).map(r => {
    const cls = r.z > 0 ? 'delta-pos' : 'delta-neg';
    return `<tr>
      <td class="label-cell">${fmt0(r.strike)}</td>
      <td>${r.side}</td>
      <td>${fmt(r.oi)}</td>
      <td>${fmt(r.m)}</td>
      <td class="${cls}">${r.z >= 0 ? '+' : ''}${r.z.toFixed(2)}σ</td>
    </tr>`;
  }).join('');
}

function renderTrap() {
  const wrap = $('trapBody');
  if (!STATE.chain.length) { wrap.innerHTML = ''; return; }
  // Heuristic: high LTP × premium spike (proxied by OI dropping fast — short covering)
  const candidates = STATE.chain
    .filter(r => Math.abs(r.ceChg) > 30000 && r.ceLTP > 0)
    .map(r => ({ side: 'CE', strike: r.strike, chg: r.ceChg, ltp: r.ceLTP, oi: r.ceOI }))
    .concat(
      STATE.chain
        .filter(r => Math.abs(r.peChg) > 30000 && r.peLTP > 0)
        .map(r => ({ side: 'PE', strike: r.strike, chg: r.peChg, ltp: r.peLTP, oi: r.peOI }))
    )
    .filter(r => r.chg < 0)  // OI dropping = covering
    .sort((a,b) => a.chg - b.chg)
    .slice(0, 6);
  if (!candidates.length) {
    wrap.innerHTML = '<div style="color:var(--text-faint);font-size:12px;padding:8px 0">No trapped writers detected.</div>';
    return;
  }
  wrap.innerHTML = '<div class="badges">' + candidates.map(c => {
    const dir = c.side === 'CE' ? 'CALL writers covering ↑' : 'PUT writers covering ↓';
    const cls = c.side === 'CE' ? 'pe-up' : 'pe-dn';
    return `<span class="badge ${cls}"><span class="lab">${c.side}</span><strong>${fmt0(c.strike)}</strong>ΔOI ${fmt(c.chg)} · LTP ${fmt2(c.ltp)}</span>`;
  }).join('') + '</div>' +
  '<div style="font-size:11px;color:var(--text-dim);margin-top:8px">' +
  candidates.slice(0, 1).map(c => `<strong>${c.side === 'CE' ? 'Calls' : 'Puts'} at ${fmt0(c.strike)}</strong> are being closed aggressively — ${c.side === 'CE' ? 'spot likely pushing up through resistance' : 'spot likely breaking down through support'}.`).join('') +
  '</div>';
}

function renderPCRGauge() {
  const svg = $('pcrGauge');
  const v = STATE.pcr || 0;
  const frac = Math.max(0, Math.min(1, v / 2));
  const cx = 120, cy = 120, r = 90;
  const start = Math.PI;
  const end = Math.PI + Math.PI * frac;
  const x1 = cx + r * Math.cos(start), y1 = cy + r * Math.sin(start);
  const x2 = cx + r * Math.cos(end), y2 = cy + r * Math.sin(end);
  const large = frac > 0.5 ? 1 : 0;
  const color = v > 1.2 ? '#ef4444' : v < 0.8 ? '#3b82f6' : '#f59e0b';
  svg.innerHTML = `
    <defs>
      <linearGradient id="gaugeFill" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="${color}" stop-opacity="0.5"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="1"/>
      </linearGradient>
    </defs>
    <path d="M ${cx-r} ${cy} A ${r} ${r} 0 0 1 ${cx+r} ${cy}" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="14" stroke-linecap="round"/>
    <path d="M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}" fill="none" stroke="url(#gaugeFill)" stroke-width="14" stroke-linecap="round"/>
    <text x="${cx-r}" y="${cy+24}" fill="#555a73" font-size="11" font-family="JetBrains Mono">0.0</text>
    <text x="${cx}" y="${cy-r-6}" fill="#555a73" font-size="11" font-family="JetBrains Mono" text-anchor="middle">1.0</text>
    <text x="${cx+r}" y="${cy+24}" fill="#555a73" font-size="11" font-family="JetBrains Mono" text-anchor="end">2.0</text>`;
  $('gaugePCR').textContent = fmt2(v);
  $('gaugePCR').style.color = color;
}

function smaSeries(series, win) {
  if (!win || win < 2 || series.length < win) return null;
  const out = [];
  for (let i = win - 1; i < series.length; i++) {
    let s = 0;
    for (let j = i - win + 1; j <= i; j++) s += series[j].v;
    out.push({ t: series[i].t, v: s / win, idx: i });
  }
  return out;
}

function renderLineChart(id, series, color, smaWin) {
  const svg = $(id);
  if (!series.length) {
    svg.innerHTML = `<text x="300" y="100" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">No data yet — waiting for snapshots</text>`;
    return;
  }
  const W = 600, H = id === 'pcrChart' ? 200 : 280;
  const padL = 50, padR = 14, padT = 14, padB = 30;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const vals = series.map(s => s.v);
  let mn = Math.min(...vals), mx = Math.max(...vals);
  if (mn === mx) { mn -= 1; mx += 1; }
  const range = mx - mn;
  const x = (i) => padL + (series.length === 1 ? innerW/2 : (i / (series.length - 1)) * innerW);
  const y = (v) => padT + innerH - ((v - mn) / range) * innerH;
  const path = series.map((s,i) => `${i===0?'M':'L'} ${x(i)} ${y(s.v)}`).join(' ');
  const area = path + ` L ${x(series.length-1)} ${padT+innerH} L ${x(0)} ${padT+innerH} Z`;
  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const yy = padT + (innerH / 4) * i;
    const vv = mx - (range / 4) * i;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${yy+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${fmt2(vv)}</text>`);
  }
  const lastX = x(series.length-1), lastY = y(series[series.length-1].v);
  const gradId = `g_${id}`;
  const sma = smaSeries(series, smaWin);
  let smaPath = '';
  if (sma && sma.length) {
    smaPath = `<path d="${sma.map((p,i) => `${i===0?'M':'L'} ${x(p.idx)} ${y(p.v)}`).join(' ')}" fill="none" stroke="#f0b429" stroke-width="1.6" stroke-dasharray="5,4" stroke-linejoin="round"/>`;
  }
  svg.innerHTML = `
    <defs>
      <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${color}" stop-opacity="0.4"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
      </linearGradient>
    </defs>
    ${grid.join('')}
    <path d="${area}" fill="url(#${gradId})"/>
    <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
    ${smaPath}
    <circle cx="${lastX}" cy="${lastY}" r="5" fill="${color}" opacity="0.3"/>
    <circle cx="${lastX}" cy="${lastY}" r="3" fill="${color}"/>`;
}

const STRIKE_COLORS = {
  ce: ['#3b82f6', '#60a5fa', '#8b5cf6', '#a78bfa', '#0ea5e9', '#06b6d4'],
  pe: ['#ef4444', '#f56565', '#f87171', '#f0b429', '#f59e0b', '#fb923c'],
};

function renderOIHistory() {
  const svg = $('oiHistoryChart');
  const legendEl = $('oiHistoryLegend');
  const h = STATE.oiHistory;
  if (!h || !h.series || h.series.length < 2) {
    svg.innerHTML = `<text x="500" y="180" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">Need at least 2 snapshots — they accumulate every 3 min during market hours</text>`;
    legendEl.innerHTML = '';
    return;
  }
  const strikes = h.strikes;
  const series = h.series;

  const allVals = [];
  for (const pt of series) {
    for (const s of strikes) {
      const r = pt.strikes[String(s)];
      if (r) { allVals.push(r.ceOI, r.peOI); }
    }
  }
  let mx = Math.max(...allVals, 1);

  const W = 1000, H = 360, padL = 70, padR = 110, padT = 20, padB = 40;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const x = (i) => padL + (series.length === 1 ? innerW/2 : (i / (series.length - 1)) * innerW);
  const y = (v) => padT + innerH - (v / mx) * innerH;

  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const yy = padT + (innerH / 4) * i;
    const vv = mx - (mx / 4) * i;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${yy+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${fmt(vv)}</text>`);
  }

  // X-axis time labels
  const xLabels = [];
  const tickEvery = Math.max(1, Math.floor(series.length / 6));
  series.forEach((pt, i) => {
    if (i % tickEvery === 0 || i === series.length - 1) {
      xLabels.push(`<text x="${x(i)}" y="${H-padB+16}" fill="#555a73" font-size="10" text-anchor="middle" font-family="JetBrains Mono">${pt.time}</text>`);
    }
  });

  let lines = '';
  let legend = '';
  strikes.forEach((s, idx) => {
    const ceColor = STRIKE_COLORS.ce[idx % STRIKE_COLORS.ce.length];
    const peColor = STRIKE_COLORS.pe[idx % STRIKE_COLORS.pe.length];
    const cePath = series.map((pt, i) => {
      const v = (pt.strikes[String(s)] || {}).ceOI || 0;
      return `${i===0?'M':'L'} ${x(i)} ${y(v)}`;
    }).join(' ');
    const pePath = series.map((pt, i) => {
      const v = (pt.strikes[String(s)] || {}).peOI || 0;
      return `${i===0?'M':'L'} ${x(i)} ${y(v)}`;
    }).join(' ');
    lines += `<path d="${cePath}" fill="none" stroke="${ceColor}" stroke-width="1.6" stroke-linejoin="round" opacity="0.85"/>`;
    lines += `<path d="${pePath}" fill="none" stroke="${peColor}" stroke-width="1.6" stroke-linejoin="round" opacity="0.85" stroke-dasharray="0"/>`;
    legend += `<span style="display:inline-flex;gap:4px;align-items:center;margin-right:14px"><span class="sw" style="background:${ceColor}"></span>CE ${fmt0(s)} <span style="color:var(--text-faint);margin:0 4px">/</span> <span class="sw" style="background:${peColor}"></span>PE ${fmt0(s)}</span>`;
  });

  legendEl.innerHTML = legend;
  svg.innerHTML = grid.join('') + xLabels.join('') + lines;
}

function renderSpurts() {
  const wrap = $('spurts');
  const list = STATE.chain.flatMap(r => {
    const out = [];
    if (Math.abs(r.ceChg) > 50000) out.push({ side: 'CE', strike: r.strike, chg: r.ceChg });
    if (Math.abs(r.peChg) > 50000) out.push({ side: 'PE', strike: r.strike, chg: r.peChg });
    return out;
  }).sort((a,b) => Math.abs(b.chg) - Math.abs(a.chg)).slice(0, 24);
  if (!list.length) { wrap.innerHTML = '<div style="color:var(--text-faint);font-size:12px;padding:8px 0">No significant OI moves yet.</div>'; return; }
  wrap.innerHTML = list.map(s => {
    const cls = s.side === 'CE' ? (s.chg > 0 ? 'ce-up' : 'ce-dn') : (s.chg > 0 ? 'pe-up' : 'pe-dn');
    const sign = s.chg > 0 ? '+' : '';
    const [stCls, stLab] = strengthOf(Math.abs(s.chg));
    return `<span class="badge ${cls}"><span class="lab">${s.side}</span><strong>${fmt0(s.strike)}</strong>${sign}${fmt(s.chg)}<span class="strength-tag ${stCls}">${stLab}</span></span>`;
  }).join('');
}

function renderBuildup() {
  const tb = $('buildupBody');
  if (!STATE.chain.length || !STATE.spot) { tb.innerHTML = ''; return; }
  const range = STATE.buildupRange || 0;     // 0 = unrestricted
  const filtered = range > 0
    ? STATE.chain.filter(r => Math.abs(r.strike - STATE.spot) <= range)
    : STATE.chain.slice();
  const rows = [];
  for (const r of filtered) {
    if (r.ceChg !== 0) rows.push({ strike: r.strike, side: 'CE', chg: r.ceChg,
      sig: r.ceChg > 0 ? ['Short Buildup','short-build'] : ['Short Covering','short-cover'] });
    if (r.peChg !== 0) rows.push({ strike: r.strike, side: 'PE', chg: r.peChg,
      sig: r.peChg > 0 ? ['Long Buildup','long-build'] : ['Long Unwinding','long-unwind'] });
  }
  rows.sort((a,b) => Math.abs(b.chg) - Math.abs(a.chg));
  tb.innerHTML = rows.slice(0, 30).map(r => {
    const sign = r.chg > 0 ? '+' : '';
    const cls = r.chg > 0 ? 'delta-pos' : 'delta-neg';
    return `<tr>
      <td class="label-cell">${fmt0(r.strike)}</td>
      <td>${r.side}</td>
      <td class="${cls}">${sign}${fmt(r.chg)}</td>
      <td><span class="signal ${r.sig[1]}">${r.sig[0]}</span></td>
    </tr>`;
  }).join('') || '<tr><td colspan="4" style="text-align:center;color:var(--text-faint);padding:14px">No data</td></tr>';
}

/* ---------- MACRO ---------- */
function renderMacro() {
  // VIX
  const vd = STATE.vixData?.data;
  if (vd) {
    const v = vd.last ?? vd.lastValue ?? vd.LTP ?? vd.indexClose ?? 0;
    const ch = vd.change ?? vd.dayChange ?? 0;
    const pch = vd.percentChange ?? vd.percChange ?? 0;
    $('vixVal').textContent = fmt2(v);
    const chClr = ch >= 0 ? 'var(--red)' : 'var(--green)';
    $('vixChg').style.color = chClr;
    $('vixChg').textContent = `${ch >= 0 ? '+' : ''}${fmt2(ch)} (${pch >= 0 ? '+' : ''}${fmt2(pch)}%)`;
    const pct = Math.max(0, Math.min(1, v / 30));
    $('vixMarker').style.left = (pct * 100) + '%';
    let regime = 'Normal'; let rcls = 'neutral';
    if (v < 12) { regime = 'Calm'; rcls = 'bull'; }
    else if (v > 20) { regime = 'Fear'; rcls = 'bear'; }
    $('vixRegimeTag').className = `tag ${rcls}`;
    $('vixRegimeTag').textContent = regime;
    const dh = vd.dayHigh ?? vd.high; const dl = vd.dayLow ?? vd.low;
    if (dh && dl) {
      $('vixDetails').innerHTML = `<div style="display:flex;gap:14px"><span>High <strong style="font-family:'JetBrains Mono'">${fmt2(dh)}</strong></span><span>Low <strong style="font-family:'JetBrains Mono'">${fmt2(dl)}</strong></span></div>`;
    }
  } else {
    $('vixVal').textContent = '—';
    $('vixChg').textContent = 'unavailable';
  }

  // FII/DII
  const fd = STATE.fiiDiiData?.data;
  if (Array.isArray(fd) && fd.length) {
    const all = fd.flatMap(d => Array.isArray(d) ? d : [d]);
    const max = Math.max(1, ...all.map(d => Math.abs(d.netValue ?? d.net ?? 0)));
    let html = '<div class="flow-row header"><span>Category</span><span>Buy / Sell</span><span>Net (₹ Cr)</span></div>';
    for (const d of all) {
      const cat = d.category || d.clientType || d.name || '?';
      const buy = d.buyValue ?? d.buy ?? 0;
      const sell = d.sellValue ?? d.sell ?? 0;
      const net = d.netValue ?? d.net ?? (buy - sell);
      const netCls = net >= 0 ? 'delta-pos' : 'delta-neg';
      const pctW = (Math.abs(net) / max * 100).toFixed(0);
      const fillC = net >= 0 ? 'var(--green)' : 'var(--red)';
      const date = d.date || '';
      html += `<div class="flow-row">
        <span><strong>${escapeHTML(cat)}</strong>${date ? `<br><span style="color:var(--text-faint);font-size:10px">${escapeHTML(date)}</span>`:''}</span>
        <span style="color:var(--text-dim);font-size:11px">${fmt(buy)} / ${fmt(sell)}</span>
        <span class="flow-bar-wrap"><span class="${netCls}" style="min-width:70px;text-align:right">${net >= 0 ? '+' : ''}${fmt(net)}</span><span class="flow-bar"><span class="fill" style="width:${pctW}%;background:${fillC}"></span></span></span>
      </div>`;
    }
    $('fiiDiiBody').innerHTML = html;
  } else {
    $('fiiDiiBody').innerHTML = '<div style="color:var(--text-faint);font-size:12px">No FII/DII data available.</div>';
  }

  // Participant OI
  const pd = STATE.partOiData?.data;
  if (Array.isArray(pd) && pd.length) {
    const all = pd.flatMap(d => Array.isArray(d) ? d : [d]);
    const rows = all.map(d => {
      const ct = d.clientType || d.Client_Type || d.category || '?';
      const fil = +(d.futureIndexLong ?? d['Future Index Long'] ?? 0);
      const fis = +(d.futureIndexShort ?? d['Future Index Short'] ?? 0);
      const cil = +(d.optionIndexCallLong ?? d['Option Index Call Long'] ?? 0);
      const pil = +(d.optionIndexPutLong ?? d['Option Index Put Long'] ?? 0);
      const fsl = +(d.futureStockLong ?? d['Future Stock Long'] ?? 0);
      const fss = +(d.futureStockShort ?? d['Future Stock Short'] ?? 0);
      return { ct, fil, fis, fiNet: fil - fis, cil, pil, fsNet: fsl - fss };
    });
    const html = rows.map(r => {
      const fnCls = r.fiNet >= 0 ? 'delta-pos' : 'delta-neg';
      const fsnCls = r.fsNet >= 0 ? 'delta-pos' : 'delta-neg';
      return `<tr>
        <td class="label-cell">${escapeHTML(r.ct)}</td>
        <td>${fmt(r.fil)}</td>
        <td>${fmt(r.fis)}</td>
        <td class="${fnCls}">${r.fiNet >= 0 ? '+' : ''}${fmt(r.fiNet)}</td>
        <td>${fmt(r.cil)}</td>
        <td>${fmt(r.pil)}</td>
        <td class="${fsnCls}">${r.fsNet >= 0 ? '+' : ''}${fmt(r.fsNet)}</td>
      </tr>`;
    }).join('');
    $('partOiBody').innerHTML = html || '<tr><td colspan="7" style="text-align:center;color:var(--text-faint);padding:14px">No data</td></tr>';
  } else {
    $('partOiBody').innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-faint);padding:14px">No participant OI data available.</td></tr>';
  }
}

/* ---------- MULTI-INDEX ---------- */
function renderMulti() {
  const m = STATE.multiData;
  if (!m || !m.results) { return; }
  const html = m.results.map(r => {
    if (r.ok === false) {
      return `<div class="mini-card"><div class="head"><div class="sym">${escapeHTML(r.symbol)}</div></div><div style="color:var(--red);font-size:12px">${escapeHTML(r.error || 'failed')}</div></div>`;
    }
    let res = null, sup = null;
    if (Array.isArray(r.chain)) {
      for (const x of r.chain) {
        if (!res || x.ceOI > res.ceOI) res = x;
        if (!sup || x.peOI > sup.peOI) sup = x;
      }
    }
    const pcrCls = r.pcr > 1.2 ? 'pcr-bull' : r.pcr < 0.8 ? 'pcr-bear' : 'pcr-neutral';
    const mpDiff = Math.round((r.maxPain || 0) - (r.spot || 0));
    return `<div class="mini-card">
      <div class="head">
        <div class="sym">${escapeHTML(r.symbol)}</div>
        <span class="tag ${pcrCls === 'pcr-bull' ? 'bull' : pcrCls === 'pcr-bear' ? 'bear' : 'neutral'}">PCR ${fmt2(r.pcr)}</span>
      </div>
      <div class="row"><span class="lab">Spot</span><span class="val" style="color:var(--cyan)">${fmt2(r.spot)}</span></div>
      <div class="row"><span class="lab">Max Pain</span><span class="val" style="color:var(--violet-soft)">${fmt0(r.maxPain)} <span style="color:var(--text-faint);font-size:10px">(${mpDiff >= 0 ? '+' : ''}${mpDiff})</span></span></div>
      <div class="row"><span class="lab">Vol PCR</span><span class="val">${fmt2(r.volPcr)}</span></div>
      <div class="row"><span class="lab">ATM Straddle</span><span class="val">${fmt2(r.atmStraddle)}</span></div>
      <div class="row"><span class="lab">Resistance</span><span class="val" style="color:var(--red)">${res ? fmt0(res.strike) : '—'}</span></div>
      <div class="row"><span class="lab">Support</span><span class="val" style="color:var(--green)">${sup ? fmt0(sup.strike) : '—'}</span></div>
      <div class="row"><span class="lab">γ Flip</span><span class="val">${r.gammaFlip ? fmt0(r.gammaFlip) : '—'}</span></div>
      <div class="row"><span class="lab">Expiry</span><span class="val" style="font-size:11px">${escapeHTML(r.currentExpiry || '—')}</span></div>
    </div>`;
  }).join('');
  $('multiGrid').innerHTML = html;
}

/* ---------- TRENDS: OI Change by Strike ---------- */
function renderOIChange() {
  const svg = $('oiChangeChart');
  const sumEl = $('oiChangeSummary');
  const labels = {5:'5 min',10:'10 min',15:'15 min',30:'30 min',60:'1 hr',120:'2 hr',180:'3 hr',1440:'full day'};
  $('oiChangeWindowTag').textContent = `last ${labels[STATE.oiChangeWindowMin] || STATE.oiChangeWindowMin + ' min'}`;

  const d = STATE.oiChange;
  if (!d || !d.available) {
    svg.innerHTML = `<text x="500" y="200" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">Need at least 2 snapshots within this window — they accumulate every 3 min during market hours</text>`;
    sumEl.innerHTML = '';
    return;
  }

  // Slice around ATM
  const atm = nearestATM();
  let visible = d.rows.filter(r => r.ceChg !== 0 || r.peChg !== 0);
  if (atm) {
    const idx = visible.findIndex(r => r.strike >= atm);
    if (idx >= 0) {
      const start = Math.max(0, idx - 20);
      const end = Math.min(visible.length, idx + 21);
      visible = visible.slice(start, end);
    }
  }
  if (!visible.length) {
    svg.innerHTML = `<text x="500" y="200" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">No OI changes in this window</text>`;
    sumEl.innerHTML = '';
    return;
  }

  const W = 1000, H = 420, padL = 70, padR = 20, padT = 30, padB = 70;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const allVals = visible.flatMap(r => [r.ceChg, r.peChg]);
  const maxAbs = Math.max(...allVals.map(Math.abs), 1);
  const zeroY = padT + innerH / 2;
  const groupW = innerW / visible.length;
  const barW = (groupW - 4) / 2;

  const grid = [];
  for (let i = -2; i <= 2; i++) {
    const y = zeroY - (i / 2) * (innerH / 2);
    const v = (i / 2) * maxAbs;
    grid.push(`<line x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${y+4}" fill="#555a73" font-size="10" text-anchor="end" font-family="JetBrains Mono">${v >= 0 ? '+' : ''}${fmt(v)}</text>`);
  }

  const bars = visible.map((r, i) => {
    const xL = padL + i * groupW + 2;
    const peH = Math.abs(r.peChg) / maxAbs * (innerH / 2);
    const ceH = Math.abs(r.ceChg) / maxAbs * (innerH / 2);
    const peY = r.peChg >= 0 ? zeroY - peH : zeroY;
    const ceY = r.ceChg >= 0 ? zeroY - ceH : zeroY;
    const isATM = r.strike === atm;
    return `<rect x="${xL}" y="${peY}" width="${barW}" height="${peH}" fill="#ef4444" rx="2" opacity="0.85"><title>PE ${fmt0(r.strike)} Δ ${r.peChg >= 0 ? '+' : ''}${fmt(r.peChg)}</title></rect>
      <rect x="${xL+barW+2}" y="${ceY}" width="${barW}" height="${ceH}" fill="#3b82f6" rx="2" opacity="0.85"><title>CE ${fmt0(r.strike)} Δ ${r.ceChg >= 0 ? '+' : ''}${fmt(r.ceChg)}</title></rect>
      <text x="${xL+barW+1}" y="${H-padB+18}" fill="${isATM?'#a78bfa':'#8b91a8'}" font-size="9" text-anchor="end" font-family="JetBrains Mono" font-weight="${isATM?700:400}" transform="rotate(-50 ${xL+barW+1} ${H-padB+18})">${fmt0(r.strike)}</text>`;
  }).join('');

  let spotLine = '';
  if (STATE.spot) {
    const idx = visible.findIndex(r => r.strike >= STATE.spot);
    if (idx > 0) {
      const a = visible[idx - 1], b = visible[idx];
      const t = (STATE.spot - a.strike) / Math.max(b.strike - a.strike, 1);
      const x = padL + (idx - 1 + t) * groupW + groupW / 2;
      spotLine = `<line x1="${x}" y1="${padT}" x2="${x}" y2="${padT+innerH}" stroke="#06b6d4" stroke-width="1.5" stroke-dasharray="4,4"/>
        <text x="${x}" y="${padT-8}" fill="#06b6d4" font-size="11" text-anchor="middle" font-family="DM Sans" font-weight="600">${escapeHTML(STATE.sym)} ${fmt2(STATE.spot)}</text>`;
    }
  }
  const baseline = `<line x1="${padL}" y1="${zeroY}" x2="${W-padR}" y2="${zeroY}" stroke="rgba(255,255,255,0.18)"/>`;

  svg.innerHTML = grid.join('') + bars + baseline + spotLine;

  const s = d.summary;
  const ceCls = s.totalCeChange >= 0 ? 'delta-pos' : 'delta-neg';
  const peCls = s.totalPeChange >= 0 ? 'delta-pos' : 'delta-neg';
  const spotMove = s.toSpot - s.fromSpot;
  const spotCls = spotMove >= 0 ? 'delta-pos' : 'delta-neg';
  sumEl.innerHTML = `
    <div class="item"><span class="lab">From → To</span><span class="val">${escapeHTML(s.fromTime)} → ${escapeHTML(s.toTime)}</span></div>
    <div class="item"><span class="lab">Spot Move</span><span class="val ${spotCls}">${fmt2(s.fromSpot)} → ${fmt2(s.toSpot)} <span style="font-size:11px">(${spotMove >= 0 ? '+' : ''}${fmt2(spotMove)})</span></span></div>
    <div class="item"><span class="lab">Total Call OI Δ</span><span class="val ${ceCls}">${s.totalCeChange >= 0 ? '+' : ''}${fmt(s.totalCeChange)}</span></div>
    <div class="item"><span class="lab">Total Put OI Δ</span><span class="val ${peCls}">${s.totalPeChange >= 0 ? '+' : ''}${fmt(s.totalPeChange)}</span></div>`;
}

/* ---------- TRENDS: Multi-Strike Picker + Chart ---------- */
function renderStrikePicker() {
  const wrap = $('multiStrikePicker');
  if (!STATE.chain.length) {
    wrap.innerHTML = '<span style="color:var(--text-faint);font-size:12px">Loading…</span>';
    return;
  }
  // Top 14 strikes by total OI in current snapshot
  const sorted = [...STATE.chain].sort((a,b) => (b.ceOI + b.peOI) - (a.ceOI + a.peOI)).slice(0, 14);
  // Sort by strike for stable display
  sorted.sort((a,b) => a.strike - b.strike);
  const colorOf = (strike) => {
    const idx = [...STATE.multiStrikeSelected].sort((a,b) => a-b).indexOf(strike);
    return idx >= 0 ? STRIKE_PALETTE[idx % STRIKE_PALETTE.length] : 'var(--text-faint)';
  };
  wrap.innerHTML = sorted.map(r => {
    const checked = STATE.multiStrikeSelected.has(r.strike);
    const color = colorOf(r.strike);
    return `<label class="strike-pick ${checked ? 'checked' : ''}">
      <span class="dot" style="background:${color}"></span>
      <input type="checkbox" data-strike="${r.strike}" ${checked ? 'checked' : ''}/>
      ${fmt0(r.strike)}
    </label>`;
  }).join('');
  wrap.querySelectorAll('input').forEach(input => {
    input.addEventListener('change', () => {
      const s = parseInt(input.dataset.strike, 10);
      if (input.checked) STATE.multiStrikeSelected.add(s);
      else STATE.multiStrikeSelected.delete(s);
      loadMultiStrike();
    });
  });
}

function renderMultiStrike() {
  const svg = $('multiStrikeChart');
  const h = STATE.multiStrikeData;
  if (!h || !h.series || h.series.length < 2) {
    svg.innerHTML = `<text x="500" y="200" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">Need at least 2 snapshots — they accumulate every 3 min during market hours</text>`;
    return;
  }
  const series = h.series;
  const strikes = [...STATE.multiStrikeSelected].sort((a,b) => a-b);
  if (!strikes.length) {
    svg.innerHTML = `<text x="500" y="200" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">Select at least one strike from above</text>`;
    return;
  }

  const W = 1000, H = 400, padL = 70, padR = 80, padT = 24, padB = 50;
  const innerW = W - padL - padR, innerH = H - padT - padB;

  // Left axis: spot. Right axis: OI.
  const spotVals = series.map(s => s.spot).filter(v => v > 0);
  let spotMn = Math.min(...spotVals), spotMx = Math.max(...spotVals);
  const spotPad = (spotMx - spotMn) * 0.1 || 10;
  spotMn -= spotPad; spotMx += spotPad;

  let oiMx = 1;
  for (const pt of series) {
    for (const s of strikes) {
      const r = pt.strikes[String(s)];
      if (r) oiMx = Math.max(oiMx, r.ceOI, r.peOI);
    }
  }

  const x = (i) => padL + (series.length === 1 ? innerW/2 : (i / (series.length - 1)) * innerW);
  const ySpot = (v) => padT + innerH - ((v - spotMn) / Math.max(spotMx - spotMn, 1)) * innerH;
  const yOI = (v) => padT + innerH - (v / oiMx) * innerH;

  // Y grid (left = spot)
  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const yy = padT + (innerH / 4) * i;
    const sv = spotMx - ((spotMx - spotMn) / 4) * i;
    const ov = oiMx - (oiMx / 4) * i;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${yy+4}" fill="#9ca3af" font-size="10" text-anchor="end" font-family="JetBrains Mono">${fmt2(sv)}</text>
      <text x="${W-padR+8}" y="${yy+4}" fill="#8b91a8" font-size="10" text-anchor="start" font-family="JetBrains Mono">${fmt(ov)}</text>`);
  }

  // X labels
  const xLabels = [];
  const tickEvery = Math.max(1, Math.floor(series.length / 6));
  series.forEach((pt, i) => {
    if (i % tickEvery === 0 || i === series.length - 1) {
      xLabels.push(`<text x="${x(i)}" y="${H-padB+16}" fill="#555a73" font-size="10" text-anchor="middle" font-family="JetBrains Mono">${escapeHTML(pt.time)}</text>`);
    }
  });

  // Spot line
  const spotPath = series.map((pt, i) => `${i===0?'M':'L'} ${x(i)} ${ySpot(pt.spot)}`).join(' ');
  let lines = `<path d="${spotPath}" fill="none" stroke="#9ca3af" stroke-width="2" stroke-linejoin="round"/>`;

  // OI lines per selected strike
  strikes.forEach((s, idx) => {
    const ceColor = STRIKE_PALETTE[(idx * 2) % STRIKE_PALETTE.length];
    const peColor = STRIKE_PALETTE[(idx * 2 + 1) % STRIKE_PALETTE.length];
    const cePath = series.map((pt, i) => {
      const v = (pt.strikes[String(s)] || {}).ceOI || 0;
      return `${i===0?'M':'L'} ${x(i)} ${yOI(v)}`;
    }).join(' ');
    const pePath = series.map((pt, i) => {
      const v = (pt.strikes[String(s)] || {}).peOI || 0;
      return `${i===0?'M':'L'} ${x(i)} ${yOI(v)}`;
    }).join(' ');
    lines += `<path d="${cePath}" fill="none" stroke="${ceColor}" stroke-width="1.6" stroke-linejoin="round" opacity="0.9"><title>CE ${fmt0(s)}</title></path>`;
    lines += `<path d="${pePath}" fill="none" stroke="${peColor}" stroke-width="1.6" stroke-linejoin="round" opacity="0.9" stroke-dasharray="4,3"><title>PE ${fmt0(s)}</title></path>`;
  });

  // Axis titles
  const titles = `<text x="${padL-50}" y="${padT-8}" fill="#9ca3af" font-size="10" font-family="DM Sans" font-weight="600">${escapeHTML(STATE.sym)}</text>
    <text x="${W-padR+50}" y="${padT-8}" fill="#8b91a8" font-size="10" font-family="DM Sans" font-weight="600" text-anchor="end">Open Interest</text>`;

  svg.innerHTML = grid.join('') + xLabels.join('') + lines + titles;
}

/* ---------- TRENDS: Daily OI vs Time ---------- */
function renderDailyOI() {
  const svg = $('dailyOIChart');
  const d = STATE.dailyAgg;
  if (!d || !d.days || d.days.length < 2) {
    svg.innerHTML = `<text x="500" y="180" fill="#555a73" text-anchor="middle" font-family="DM Sans" font-size="12">Need at least 2 trading days of snapshots — comes naturally as the database accumulates</text>`;
    return;
  }
  const days = d.days;
  const W = 1000, H = 380, padL = 70, padR = 70, padT = 24, padB = 50;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const groupW = innerW / days.length;
  const barW = (groupW - 6) / 2;

  const oiMx = Math.max(...days.flatMap(d => [d.totalCEOI, d.totalPEOI]), 1);
  const pcrVals = days.map(d => d.pcr).filter(v => v > 0);
  const spotVals = days.map(d => d.spot).filter(v => v > 0);

  let pcrMn = Math.min(...pcrVals, 0.5), pcrMx = Math.max(...pcrVals, 1.5);
  const pcrPad = (pcrMx - pcrMn) * 0.1 || 0.1;
  pcrMn -= pcrPad; pcrMx += pcrPad;
  let spotMn = Math.min(...spotVals), spotMx = Math.max(...spotVals);
  const spotPad = (spotMx - spotMn) * 0.05 || 50;
  spotMn -= spotPad; spotMx += spotPad;

  const yOI = (v) => padT + innerH - (v / oiMx) * innerH;
  // Right-axis combines PCR (primary) and spot (overlaid normalized to PCR scale for visualization)
  const yPCR = (v) => padT + innerH - ((v - pcrMn) / Math.max(pcrMx - pcrMn, 0.01)) * innerH;
  const ySpot = (v) => padT + innerH - ((v - spotMn) / Math.max(spotMx - spotMn, 1)) * innerH;

  // Grid
  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const yy = padT + (innerH / 4) * i;
    const ov = oiMx - (oiMx / 4) * i;
    const pv = pcrMx - ((pcrMx - pcrMn) / 4) * i;
    grid.push(`<line x1="${padL}" y1="${yy}" x2="${W-padR}" y2="${yy}" stroke="rgba(255,255,255,0.04)"/>
      <text x="${padL-8}" y="${yy+4}" fill="#8b91a8" font-size="10" text-anchor="end" font-family="JetBrains Mono">${fmt(ov)}</text>
      <text x="${W-padR+8}" y="${yy+4}" fill="#a78bfa" font-size="10" text-anchor="start" font-family="JetBrains Mono">${fmt2(pv)}</text>`);
  }

  // Bars
  const bars = days.map((day, i) => {
    const xC = padL + i * groupW + (groupW - barW * 2 - 4) / 2;
    const peH = (day.totalPEOI / oiMx) * innerH;
    const ceH = (day.totalCEOI / oiMx) * innerH;
    const peY = padT + innerH - peH;
    const ceY = padT + innerH - ceH;
    return `<rect x="${xC}" y="${peY}" width="${barW}" height="${peH}" fill="#ef4444" rx="2" opacity="0.85"><title>${escapeHTML(day.date)} PE ${fmt(day.totalPEOI)}</title></rect>
      <rect x="${xC+barW+4}" y="${ceY}" width="${barW}" height="${ceH}" fill="#3b82f6" rx="2" opacity="0.85"><title>${escapeHTML(day.date)} CE ${fmt(day.totalCEOI)}</title></rect>`;
  }).join('');

  // Date labels
  const xCenter = (i) => padL + i * groupW + groupW / 2;
  const tickEvery = Math.max(1, Math.floor(days.length / 10));
  const dateLabels = days.map((day, i) => {
    if (i % tickEvery !== 0 && i !== days.length - 1) return '';
    const dt = day.date.slice(5); // MM-DD
    return `<text x="${xCenter(i)}" y="${H-padB+18}" fill="#555a73" font-size="10" text-anchor="middle" font-family="JetBrains Mono">${escapeHTML(dt)}</text>`;
  }).join('');

  // PCR line (right axis, primary)
  const pcrPath = days.map((day, i) => `${i===0?'M':'L'} ${xCenter(i)} ${yPCR(day.pcr)}`).join(' ');
  // Spot line (separate scale, overlaid using its own scaling - we use ySpot)
  const spotPath = days.map((day, i) => `${i===0?'M':'L'} ${xCenter(i)} ${ySpot(day.spot)}`).join(' ');

  const lines = `
    <path d="${spotPath}" fill="none" stroke="#9ca3af" stroke-width="1.5" stroke-linejoin="round" opacity="0.7"/>
    <path d="${pcrPath}" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-linejoin="round"/>
    ${days.map((d, i) => `<circle cx="${xCenter(i)}" cy="${yPCR(d.pcr)}" r="2.5" fill="#8b5cf6"/>`).join('')}
  `;

  const titles = `<text x="${padL-50}" y="${padT-8}" fill="#8b91a8" font-size="10" font-family="DM Sans" font-weight="600">CE / PE OI</text>
    <text x="${W-padR+50}" y="${padT-8}" fill="#a78bfa" font-size="10" font-family="DM Sans" font-weight="600" text-anchor="end">PCR</text>`;

  svg.innerHTML = grid.join('') + bars + dateLabels + lines + titles;
}

function renderCompare(d) {
  const sum = $('cmpSummary');
  const spotSign = d.spotMove >= 0 ? '+' : '';
  const pcrSign = d.pcrShift >= 0 ? '+' : '';
  const mpSign = d.maxPainShift >= 0 ? '+' : '';
  const spotCls = d.spotMove >= 0 ? 'pcr-bull' : 'pcr-bear';
  const pcrCls = d.pcrShift >= 0 ? 'pcr-bull' : 'pcr-bear';

  let totalCeDelta = 0, totalPeDelta = 0;
  for (const r of (d.rows || [])) {
    totalCeDelta += r.ceOIDelta || 0;
    totalPeDelta += r.peOIDelta || 0;
  }
  const ceSign = totalCeDelta >= 0 ? '+' : '';
  const peSign = totalPeDelta >= 0 ? '+' : '';
  const ceCls = totalCeDelta > 0 ? 'pcr-bull' : (totalCeDelta < 0 ? 'pcr-bear' : '');
  const peCls = totalPeDelta > 0 ? 'pcr-bull' : (totalPeDelta < 0 ? 'pcr-bear' : '');
  const netDelta = totalPeDelta - totalCeDelta;
  const netLabel = netDelta > 0 ? 'PE > CE (lean bullish)' : netDelta < 0 ? 'CE > PE (lean bearish)' : 'flat';

  sum.innerHTML = `
    <div class="stat ${spotCls}"><div class="label">Spot Move</div><div class="value num">${spotSign}${fmt2(d.spotMove)}</div></div>
    <div class="stat ${pcrCls}"><div class="label">PCR Shift</div><div class="value num">${pcrSign}${fmt2(d.pcrShift)}</div></div>
    <div class="stat maxpain"><div class="label">Max Pain Shift</div><div class="value num">${mpSign}${fmt0(d.maxPainShift)}</div></div>
    <div class="stat ${ceCls}"><div class="label">Total CE ΔOI</div><div class="value num">${ceSign}${fmt(totalCeDelta)}</div><div style="font-size:10px;color:var(--text-faint);margin-top:2px">calls</div></div>
    <div class="stat ${peCls}"><div class="label">Total PE ΔOI</div><div class="value num">${peSign}${fmt(totalPeDelta)}</div><div style="font-size:10px;color:var(--text-faint);margin-top:2px">puts · ${netLabel}</div></div>
    <div class="stat"><div class="label">A → B</div><div class="value num" style="font-size:14px">${d.a.time} → ${d.b.time}</div></div>`;

  const tb = $('cmpBody');
  const rows = d.rows.filter(r =>
    r.ceOIA || r.ceOIB || r.peOIA || r.peOIB ||
    r.ceOIDelta !== 0 || r.peOIDelta !== 0
  );
  rows.sort((a, b) => a.strike - b.strike);
  const atmA = d.a && d.a.atmStrike;
  const atmB = d.b && d.b.atmStrike;
  const atmStrike = (atmA != null && atmB != null) ? Math.round((atmA + atmB) / 2) : (atmB ?? atmA);
  let atmRowStrike = null;
  if (atmStrike != null && rows.length) {
    atmRowStrike = rows.reduce((best, r) =>
      Math.abs(r.strike - atmStrike) < Math.abs(best - atmStrike) ? r.strike : best,
      rows[0].strike
    );
  }
  const topCEA = _topRanks(rows, 'ceOIA', 5);
  const topCEB = _topRanks(rows, 'ceOIB', 5);
  const topCED = _topRanks(rows, 'ceOIDelta', 5, true);
  const topPEA = _topRanks(rows, 'peOIA', 5);
  const topPEB = _topRanks(rows, 'peOIB', 5);
  const topPED = _topRanks(rows, 'peOIDelta', 5, true);
  const tag = (mp, k, extra = '') =>
    mp.has(k) ? ` class="${extra ? extra + ' ' : ''}top-oi" data-rank="${mp.get(k)}"` : (extra ? ` class="${extra}"` : '');
  tb.innerHTML = rows.map(r => {
    const ceCls = r.ceOIDelta > 0 ? 'delta-pos' : (r.ceOIDelta < 0 ? 'delta-neg' : '');
    const peCls = r.peOIDelta > 0 ? 'delta-pos' : (r.peOIDelta < 0 ? 'delta-neg' : '');
    const ceS = r.ceOIDelta > 0 ? '+' : '';
    const peS = r.peOIDelta > 0 ? '+' : '';
    const trCls = r.strike === atmRowStrike ? ' class="atm"' : '';
    return `<tr${trCls}>
      <td class="label-cell strike">${fmt0(r.strike)}</td>
      <td${tag(topCEA, r.strike)}>${fmt(r.ceOIA)}</td>
      <td${tag(topCEB, r.strike)}>${fmt(r.ceOIB)}</td>
      <td${tag(topCED, r.strike, ceCls)}>${ceS}${fmt(r.ceOIDelta)}</td>
      <td${tag(topPEA, r.strike)}>${fmt(r.peOIA)}</td>
      <td${tag(topPEB, r.strike)}>${fmt(r.peOIB)}</td>
      <td${tag(topPED, r.strike, peCls)}>${peS}${fmt(r.peOIDelta)}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--text-faint);padding:14px">No data</td></tr>';
}

function showFatal() {
  document.querySelector('main').innerHTML = `
    <div class="error-screen">
      <h2>Unable to fetch data</h2>
      <p style="color:var(--text-dim)"><strong>Error:</strong> ${escapeHTML(STATE.err || 'unknown')}</p>
      <ul>
        <li>Is the backend running on port 8000?</li>
        <li>Try opening <a href="/api/health" target="_blank">/api/health</a> directly.</li>
        <li>If running on a cloud VM, switch <code>fetcher.py</code> to <code>server=True</code>.</li>
        <li>If cookies expired, delete <code>.nse_cache/</code> and restart.</li>
        <li>NSE only serves live data Mon–Fri 09:15–15:30 IST.</li>
      </ul>
      <button class="primary" onclick="location.reload()">Retry</button>
      <details style="margin-top:14px">
        <summary style="cursor:pointer;color:var(--text-dim);font-size:12px">Debug output</summary>
        <pre>${escapeHTML(STATE.err || '')}</pre>
      </details>
    </div>`;
}

/* ── Real-time stream ─────────────────────────────────────────────────────
   Replaces the legacy 20-s setInterval(poll). The server pushes a snapshot
   whenever a fresh one is persisted (every 3 min during the window) plus
   one initial sync on connect. We keep poll() for symbol/expiry changes
   and the manual Snap button. */
let _es = null;
let _esBackoffMs = 1000;
function connectStream() {
  try { if (_es) _es.close(); } catch (_) {}
  const url = `/api/stream?symbol=${encodeURIComponent(STATE.sym)}`;
  const es = new EventSource(url);
  _es = es;
  es.onopen = () => { _esBackoffMs = 1000; };
  es.onmessage = (ev) => {
    try {
      const snap = JSON.parse(ev.data);
      applyData(snap);
      setLive(snap.stale ? 'stale' : 'live');
      STATE.hasData = true;
      STATE.fetchCount++;
      refreshSnapshotsList();
      render();
    } catch (e) { /* ignore malformed frame */ }
  };
  es.onerror = () => {
    setLive('error');
    try { es.close(); } catch (_) {}
    // Exponential backoff to 30s ceiling, then keep retrying.
    setTimeout(connectStream, Math.min(_esBackoffMs, 30000));
    _esBackoffMs = Math.min(_esBackoffMs * 2, 30000);
  };
}

async function loadVersionBadge() {
  try {
    const r = await fetch('/api/version', { cache: 'no-store' });
    if (!r.ok) return;
    const v = await r.json();
    const b = $('liveBadge');
    if (b) b.title = `OI Pulse ${v.version} · ${v.sha} · built ${v.builtAt}`;
  } catch (_) { /* non-fatal */ }
}

/* ════════════════════════════════════════════════════════════════════════
   3.1  Calendar tab — per-expiry summary
   ═══════════════════════════════════════════════════════════════════════ */
async function loadCalendar() {
  const body = $('calendarBody');
  if (!body) return;
  body.innerHTML = '<div style="color:var(--fg-4);font-size:12px;padding:8px">Fetching every expiry…</div>';
  try {
    const count = STATE.calendarCount || 6;
    const r = await fetch(`/api/calendar?symbol=${encodeURIComponent(STATE.sym)}&maxExpiries=${count}`, { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    STATE.calendar = d;
    renderCalendar();
  } catch (e) {
    body.innerHTML = `<div style="color:var(--bear);font-size:12px;padding:8px">Calendar load failed: ${escapeHTML(e.message || String(e))}</div>`;
  }
}
function renderCalendar() {
  const body = $('calendarBody');
  if (!body || !STATE.calendar) return;
  const rows = STATE.calendar.expiries || [];
  if (!rows.length) { body.innerHTML = '<div style="color:var(--fg-4)">No expiries available.</div>'; return; }
  const spot = STATE.calendar.spot;
  const minIv = Math.min(...rows.map(r => r.atmIv || Infinity));
  const maxIv = Math.max(...rows.map(r => r.atmIv || 0));
  const ivColor = (iv) => {
    if (!maxIv || iv <= 0) return 'var(--fg-3)';
    const t = (iv - minIv) / Math.max(maxIv - minIv, 0.01);
    return t > 0.66 ? 'var(--bear)' : t < 0.33 ? 'var(--bull)' : 'var(--amber)';
  };
  const html = `
    <table class="cal-table">
      <thead>
        <tr>
          <th>Expiry</th><th>DTE</th><th>ATM</th><th>Straddle ₹</th>
          <th>ATM IV %</th><th>PCR</th><th>Max Pain</th><th>Total OI (CE / PE)</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(r => `
          <tr>
            <td><strong>${escapeHTML(r.expiry)}</strong></td>
            <td class="num">${r.dte.toFixed(1)}d</td>
            <td class="num">${fmt0(r.atmStrike)}</td>
            <td class="num">${fmt2(r.atmStraddle)}</td>
            <td class="num" style="color:${ivColor(r.atmIv)}">${r.atmIv.toFixed(2)}</td>
            <td class="num" style="color:${r.pcr > 1.2 ? 'var(--bull)' : r.pcr < 0.8 ? 'var(--bear)' : 'var(--fg-2)'}">${r.pcr.toFixed(2)}</td>
            <td class="num">${fmt0(r.maxPain)} <span style="color:var(--fg-4);font-size:10px">(${spot ? ((r.maxPain - spot) >= 0 ? '+' : '') + fmt0(r.maxPain - spot) : ''})</span></td>
            <td class="num"><span style="color:var(--ce)">${fmt(r.totalCEOI)}</span> / <span style="color:var(--pe)">${fmt(r.totalPEOI)}</span></td>
          </tr>`).join('')}
      </tbody>
    </table>`;
  body.innerHTML = html;
}

/* ════════════════════════════════════════════════════════════════════════
   3.5  Regime calendar heatmap
   ═══════════════════════════════════════════════════════════════════════ */
async function loadRegimeCalendar() {
  try {
    const days = STATE.regimeDays || 30;
    const r = await fetch(`/api/regime-calendar?symbol=${encodeURIComponent(STATE.sym)}&days=${days}`, { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    STATE.regimeCal = await r.json();
    renderRegimeHeatmap();
  } catch (e) {
    const el = $('regimeHeatmap');
    if (el) el.innerHTML = `<div style="color:var(--bear);font-size:12px">Heatmap load failed.</div>`;
  }
}
function renderRegimeHeatmap() {
  const el = $('regimeHeatmap');
  if (!el || !STATE.regimeCal) return;
  const { days, buckets } = STATE.regimeCal;
  if (!days || !days.length) { el.innerHTML = '<div style="color:var(--fg-4)">Not enough history yet.</div>'; return; }
  const colorOf = (cls) => ({
    bull: 'var(--bull)', bear: 'var(--bear)', warn: 'var(--amber)',
    neutral: 'var(--violet)', empty: 'transparent'
  })[cls] || 'var(--bg-3)';
  const cells = (day) => day.cells.map(c =>
    `<div class="heat-cell" title="${escapeHTML(day.date)} ${escapeHTML(c.bucket)} — ${escapeHTML(c.regime || 'no data')}" style="background:${colorOf(c.cls)}"></div>`).join('');
  el.innerHTML = `
    <div class="heat-grid">
      <div class="heat-col-headers">
        <div class="heat-cell heat-header"></div>
        ${buckets.map(b => `<div class="heat-cell heat-header">${escapeHTML(b)}</div>`).join('')}
      </div>
      ${days.map(d => `
        <div class="heat-row">
          <div class="heat-cell heat-header" style="text-align:right;padding-right:6px">${escapeHTML(d.date.slice(5))}</div>
          ${cells(d)}
        </div>`).join('')}
    </div>
    <div class="legend" style="margin-top:10px">
      <span><span class="sw" style="background:var(--bull)"></span>Bullish</span>
      <span><span class="sw" style="background:var(--bear)"></span>Bearish</span>
      <span><span class="sw" style="background:var(--amber)"></span>Lean</span>
      <span><span class="sw" style="background:var(--violet)"></span>Neutral</span>
    </div>`;
}

/* ════════════════════════════════════════════════════════════════════════
   3.7  Payoff visualizer — two-leg pre-trade scenario tool
   ═══════════════════════════════════════════════════════════════════════ */
STATE.payoff = { legs: [{}, {}] };
function initPayoff() {
  if (!STATE.chain || !STATE.chain.length) return;
  // Populate strike selects with EVERY strike in the chain — no ATM-vicinity cap
  // so spread / wing strategies can pick deep OTM strikes too.
  const atm = STATE.atmStrike;
  const sorted = STATE.chain.slice().sort((a, b) => a.strike - b.strike);
  document.querySelectorAll('#panel-payoff select[data-payoff="strike"]').forEach(sel => {
    sel.innerHTML = '';
    sorted.forEach(r => {
      const o = document.createElement('option'); o.value = r.strike; o.textContent = fmt0(r.strike);
      if (r.strike === atm) o.selected = true;
      sel.appendChild(o);
    });
  });
  bindPayoffEvents();
  renderPayoff();
}
function bindPayoffEvents() {
  document.querySelectorAll('#panel-payoff [data-payoff]').forEach(el => {
    el.removeEventListener('change', renderPayoff);
    el.removeEventListener('input', renderPayoff);
    el.addEventListener('change', renderPayoff);
    el.addEventListener('input', renderPayoff);
  });
}
function _readLeg(i) {
  const root = document.querySelector(`#panel-payoff .payoff-leg[data-leg="${i}"]`);
  const side = root.querySelector('[data-payoff="side"]').value;
  if (!side) return null;
  const action = root.querySelector('[data-payoff="action"]').value;
  const strike = parseFloat(root.querySelector('[data-payoff="strike"]').value);
  const qty = parseInt(root.querySelector('[data-payoff="qty"]').value, 10) || 1;
  const row = STATE.chain.find(r => r.strike === strike);
  if (!row) return null;
  const ltp = side === 'CE' ? row.ceLTP : row.peLTP;
  root.querySelector('[data-payoff="ltp"]').textContent = '@ ' + fmt2(ltp);
  return { side, action, strike, qty, ltp };
}
function _legPayoff(leg, S) {
  if (!leg) return 0;
  const intrinsic = leg.side === 'CE' ? Math.max(S - leg.strike, 0) : Math.max(leg.strike - S, 0);
  const sign = leg.action === 'BUY' ? 1 : -1;
  return sign * (intrinsic - leg.ltp) * leg.qty * (STATE.lotSize || 1);
}
function renderPayoff() {
  const legs = [_readLeg(0), _readLeg(1)].filter(Boolean);
  const svg = $('payoffChart');
  const summary = $('payoffSummary');
  if (!legs.length || !STATE.spot) { svg.innerHTML = ''; summary.textContent = 'Pick at least one leg.'; return; }
  const spot = STATE.spot;
  const span = spot * 0.08;
  const xs = []; const ys = [];
  for (let i = 0; i <= 200; i++) {
    const S = spot - span + (2 * span) * i / 200;
    const pnl = legs.reduce((acc, l) => acc + _legPayoff(l, S), 0);
    xs.push(S); ys.push(pnl);
  }
  const W = 1000, H = 380, padL = 60, padR = 20, padT = 20, padB = 30;
  const minY = Math.min(...ys, 0), maxY = Math.max(...ys, 0);
  const xScale = (v) => padL + (v - xs[0]) / (xs[xs.length - 1] - xs[0]) * (W - padL - padR);
  const yScale = (v) => padT + (1 - (v - minY) / (maxY - minY || 1)) * (H - padT - padB);
  const path = xs.map((x, i) => `${i ? 'L' : 'M'}${xScale(x).toFixed(1)},${yScale(ys[i]).toFixed(1)}`).join(' ');
  const zeroY = yScale(0);
  const spotX = xScale(spot);
  svg.innerHTML = `
    <line x1="${padL}" x2="${W - padR}" y1="${zeroY}" y2="${zeroY}" stroke="var(--fg-4)" stroke-dasharray="3 3" />
    <line x1="${spotX}" x2="${spotX}" y1="${padT}" y2="${H - padB}" stroke="var(--gold)" stroke-dasharray="4 4" />
    <text x="${spotX + 4}" y="${padT + 12}" font-size="11" fill="var(--gold)">spot ${fmt0(spot)}</text>
    <path d="${path}" fill="none" stroke="var(--ce)" stroke-width="2.2" />
    <text x="${padL}" y="${padT + 12}" font-size="11" fill="var(--fg-3)">P&amp;L (₹)</text>
  `;
  // headline numbers
  const maxProfit = Math.max(...ys);
  const maxLoss = Math.min(...ys);
  const breakevens = [];
  for (let i = 1; i < ys.length; i++) {
    if ((ys[i - 1] < 0 && ys[i] >= 0) || (ys[i - 1] > 0 && ys[i] <= 0)) {
      const t = -ys[i - 1] / (ys[i] - ys[i - 1]);
      breakevens.push(xs[i - 1] + t * (xs[i] - xs[i - 1]));
    }
  }
  summary.innerHTML = `
    <span>Max profit <strong style="color:var(--bull)">${fmt2(maxProfit)}</strong></span>
    <span>Max loss <strong style="color:var(--bear)">${fmt2(maxLoss)}</strong></span>
    <span>Break-even ${breakevens.length ? breakevens.map(b => fmt0(b)).join(' / ') : '—'}</span>
    <span>Lot ${STATE.lotSize}</span>`;
}

/* ════════════════════════════════════════════════════════════════════════
   3.4  Annotations — click a strike row to add a note
   ═══════════════════════════════════════════════════════════════════════ */
STATE.notes = {};
async function loadNotes() {
  try {
    const r = await fetch(`/api/notes?symbol=${encodeURIComponent(STATE.sym)}`, { cache: 'no-store' });
    if (!r.ok) return;
    const j = await r.json();
    STATE.notes = {};
    (j.notes || []).forEach(n => { (STATE.notes[n.strike] = STATE.notes[n.strike] || []).push(n); });
    renderNotesStrip();
  } catch (_) {}
}
async function addNote(strike) {
  if (strike == null) {
    const s = prompt('Strike for the note:');
    strike = parseFloat(s);
    if (!strike || isNaN(strike)) return;
  }
  const body = prompt(`Note for strike ${strike}:`);
  if (!body) return;
  try {
    await fetch('/api/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: STATE.sym, strike, body }),
    });
    await loadNotes();
    renderNotesStrip();
  } catch (e) { alert('Save failed: ' + e); }
}
function renderNotesStrip() {
  const strip = $('notesStrip');
  if (!strip) return;
  const entries = Object.entries(STATE.notes || {});
  if (!entries.length) { strip.hidden = true; strip.innerHTML = ''; return; }
  strip.hidden = false;
  strip.innerHTML = entries.flatMap(([strike, notes]) =>
    notes.map(n => `
      <span class="note-chip" title="${escapeHTML(n.created_at || '')}">
        <strong>${fmt0(parseFloat(strike))}</strong>
        ${n.side ? `<span style="color:var(--fg-4)"> ${escapeHTML(n.side)}</span>` : ''}
        — ${escapeHTML(n.body)}
        <button class="note-x" title="Delete" onclick="deleteNote(${n.id})">×</button>
      </span>`)).join('');
}
if ($('addNoteBtn')) $('addNoteBtn').addEventListener('click', () => addNote());
async function deleteNote(id) {
  if (!confirm('Delete this note?')) return;
  try {
    await fetch('/api/notes/' + id, { method: 'DELETE' });
    await loadNotes();
    renderNotesStrip();
  } catch (_) {}
}
window.addNote = addNote;
window.deleteNote = deleteNote;
// Reload notes whenever symbol changes
const _origPoll = poll;
// (poll is already declared above; we don't override — we just hook STATE.notes on symbol change)

/* ════════════════════════════════════════════════════════════════════════
   4.4  Light / dark theme toggle (persisted in localStorage)
   ═══════════════════════════════════════════════════════════════════════ */
function applyTheme(name) {
  document.documentElement.setAttribute('data-theme', name);
  const btn = $('themeBtn');
  if (btn) { btn.textContent = name === 'light' ? '☾' : '☼'; btn.setAttribute('aria-pressed', name === 'light' ? 'true' : 'false'); }
  try { localStorage.setItem('oipulse-theme', name); } catch (_) {}
}
if ($('themeBtn')) {
  $('themeBtn').addEventListener('click', () => {
    const cur = document.documentElement.getAttribute('data-theme') || 'dark';
    applyTheme(cur === 'dark' ? 'light' : 'dark');
  });
}
try {
  const saved = localStorage.getItem('oipulse-theme');
  if (saved) applyTheme(saved);
} catch (_) {}

applyHashOnLoad();
mountAllRangeControls();
poll();
loadNotes();
connectStream();
loadVersionBadge();

/* ── Polling fallback ────────────────────────────────────────────────────
   SSE only delivers events when the scheduler persists a new snapshot
   (Mon-Fri 09:00-15:30 IST). Outside that window the stream sits idle
   and the user sees data only from the initial poll(). Keep a 30 s
   poll running so the headline numbers refresh; the 20 s in-memory
   cache absorbs most NSE traffic. */
setInterval(poll, 30000);
