const fs = require('fs');
// Load candles: ts,o,h,l,c,vol,...  (OKX order). Dedupe by ts, sort ascending.
const raw = fs.readFileSync(__dirname + '/candles_raw.txt', 'utf8').trim().split('\n');
const map = new Map();
for (const line of raw) {
  const p = line.split(',');
  const ts = +p[0];
  if (!ts || isNaN(ts)) continue;
  map.set(ts, { ts, o: +p[1], h: +p[2], l: +p[3], c: +p[4] });
}
const candles = [...map.values()].sort((a, b) => a.ts - b.ts);
console.log('unique candles', candles.length,
  'from', new Date(candles[0].ts).toISOString(),
  'to', new Date(candles[candles.length - 1].ts).toISOString());

// ET = UTC-4 for entire range (EDT, Mar 8 – Nov 1 2026). Confirm range is within.
const ET_OFFSET = -4 * 3600 * 1000; // add to UTC ms to get "ET wall clock" ms

// Helper: given a UTC ms, return ET wall-clock components
function etParts(utcMs) {
  const d = new Date(utcMs + ET_OFFSET);
  return { dow: d.getUTCDay(), h: d.getUTCHours(), m: d.getUTCMinutes(),
           y: d.getUTCFullYear(), mo: d.getUTCMonth() + 1, day: d.getUTCDate() };
}
// Build a UTC ms for a given ET wall-clock date/time
function etToUtc(y, mo, day, h, m) {
  return Date.UTC(y, mo - 1, day, h, m) - ET_OFFSET;
}

// Find all Fridays in range, build weekend windows:
//   anchor/start = Friday 16:00 ET  (US regular close)
//   end/force-close = Monday 09:30 ET (US regular open)
// Anchor price P0 = close of the candle at/just before Fri 16:00 ET.
function findWeekends() {
  const wk = [];
  const seen = new Set();
  for (const c of candles) {
    const e = etParts(c.ts);
    if (e.dow === 5) { // Friday
      const key = `${e.y}-${e.mo}-${e.day}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const startUtc = etToUtc(e.y, e.mo, e.day, 16, 0);
      const endUtc = startUtc + (65.5 * 3600 * 1000); // Fri16:00 -> Mon 09:30 ET = 65.5h
      wk.push({ label: key, startUtc, endUtc });
    }
  }
  return wk;
}

function anchorPrice(startUtc) {
  // last candle with ts <= startUtc (its close = the price at Fri 16:00 ET)
  let best = null;
  for (const c of candles) {
    if (c.ts <= startUtc) best = c; else break;
  }
  return best;
}

function runWeekend(w, lowPct, upPct) {
  const anch = anchorPrice(w.startUtc);
  if (!anch) return null;
  const P0 = anch.c;
  const lower = P0 * (1 - lowPct);
  const upper = P0 * (1 + upPct);
  const win = candles.filter(c => c.ts > w.startUtc && c.ts <= w.endUtc);
  if (!win.length) return null;
  let inPos = false, entry = 0, minLow = Infinity;
  const trades = [];
  for (const c of win) {
    if (!inPos) {
      if (c.l <= lower) { inPos = true; entry = lower; minLow = c.l;
        // same-bar target?
        if (c.h >= upper) { trades.push({ ret: upper / entry - 1, type: 'tp', ts: c.ts, mae: (minLow/entry-1) }); inPos = false; }
      }
    } else {
      if (c.l < minLow) minLow = c.l;
      if (c.h >= upper) { trades.push({ ret: upper / entry - 1, type: 'tp', ts: c.ts, mae: (minLow/entry-1) }); inPos = false; }
    }
  }
  // force close at window end
  if (inPos) {
    const last = win[win.length - 1];
    trades.push({ ret: last.c / entry - 1, type: 'force', ts: last.ts, mae: (minLow/entry-1) });
    inPos = false;
  }
  return { label: w.label, P0, lower, upper, nCandles: win.length,
           firstTs: win[0].ts, lastTs: win[win.length - 1].ts, trades };
}

function backtest(lowPct, upPct, feePerSide) {
  const weekends = findWeekends();
  let equity = 1;
  let peak = 1, maxDD = 0;
  const curve = [{ equity: 1 }];
  const perWeekend = [];
  let allTrades = [];
  for (const w of weekends) {
    const r = runWeekend(w, lowPct, upPct);
    if (!r) continue;
    let wkStart = equity;
    for (const t of r.trades) {
      // apply round-trip fee: entry + exit
      const grossMult = 1 + t.ret;
      const netMult = grossMult * (1 - feePerSide) * (1 - feePerSide);
      equity *= netMult;
      if (equity > peak) peak = equity;
      const dd = (equity - peak) / peak;
      if (dd < maxDD) maxDD = dd;
      curve.push({ equity, ts: t.ts });
      allTrades.push({ ...t, netRet: netMult - 1 });
    }
    perWeekend.push({ label: r.label, P0: r.P0, lower: r.lower, upper: r.upper,
      nTrades: r.trades.length, types: r.trades.map(t => t.type).join('+'),
      wkReturnPct: (equity / wkStart - 1) * 100 });
  }
  return { weekends: perWeekend, totalReturnPct: (equity - 1) * 100,
    maxDDpct: maxDD * 100, nWeekends: perWeekend.length,
    nTrades: allTrades.length, allTrades, finalEquity: equity };
}

function summarize(name, lowPct, upPct, fee) {
  const r = backtest(lowPct, upPct, fee);
  const wins = r.allTrades.filter(t => t.netRet > 0).length;
  const tp = r.allTrades.filter(t => t.type === 'tp').length;
  const force = r.allTrades.filter(t => t.type === 'force').length;
  const forceWins = r.allTrades.filter(t => t.type === 'force' && t.netRet > 0).length;
  console.log(`\n===== ${name}  (lower -${(lowPct*100).toFixed(1)}%, upper +${(upPct*100).toFixed(1)}%, fee ${(fee*100).toFixed(3)}%/side) =====`);
  console.log(`Weekends traded: ${r.weekends.filter(w=>w.nTrades>0).length}/${r.nWeekends}   Trades: ${r.nTrades}  (TP ${tp}, ForceClose ${force})`);
  console.log(`Win rate: ${(wins/r.nTrades*100).toFixed(1)}%   (of force-closes, ${forceWins}/${force} positive)`);
  console.log(`Total return (compounded): ${r.totalReturnPct.toFixed(2)}%`);
  console.log(`Max drawdown (realized equity curve): ${r.maxDDpct.toFixed(2)}%`);
  const worstMAE = Math.min(...r.allTrades.map(t => t.mae)) * 100;
  console.log(`Worst intra-trade unrealized drawdown (MAE while holding): ${worstMAE.toFixed(2)}%`);
  console.log(`Final equity (start 1.0): ${r.finalEquity.toFixed(4)}`);
  return r;
}

const args = process.argv.slice(2);
const fee = args[0] !== undefined ? +args[0] : 0;
const A = summarize('Variant A', 0.018, 0.02, fee);
const B = summarize('Variant B', 0.02, 0.02, fee);

// Per-weekend detail table for variant A
console.log('\n--- Per-weekend detail (Variant A -1.8/+2) ---');
console.log('Weekend(Fri)   P0       lower    upper    nTr  type        wkRet%');
for (const w of A.weekends) {
  console.log(
    w.label.padEnd(13),
    w.P0.toFixed(2).padStart(7),
    w.lower.toFixed(2).padStart(8),
    w.upper.toFixed(2).padStart(8),
    String(w.nTrades).padStart(3),
    (w.types||'-').padEnd(11),
    w.wkReturnPct.toFixed(2).padStart(7));
}
console.log('\n--- Per-weekend detail (Variant B -2/+2) ---');
console.log('Weekend(Fri)   P0       lower    upper    nTr  type        wkRet%');
for (const w of B.weekends) {
  console.log(
    w.label.padEnd(13),
    w.P0.toFixed(2).padStart(7),
    w.lower.toFixed(2).padStart(8),
    w.upper.toFixed(2).padStart(8),
    String(w.nTrades).padStart(3),
    (w.types||'-').padEnd(11),
    w.wkReturnPct.toFixed(2).padStart(7));
}
