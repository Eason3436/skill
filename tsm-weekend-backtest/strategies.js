const fs = require('fs');
const raw = fs.readFileSync(__dirname + '/candles_raw.txt', 'utf8').trim().split('\n');
const map = new Map();
for (const line of raw) { const p = line.split(','); const ts = +p[0]; if (!ts || isNaN(ts)) continue;
  map.set(ts, { ts, o:+p[1], h:+p[2], l:+p[3], c:+p[4] }); }
const candles = [...map.values()].sort((a,b)=>a.ts-b.ts);
const ET = -4*3600*1000;
const etParts = u => { const d=new Date(u+ET); return {dow:d.getUTCDay(),y:d.getUTCFullYear(),mo:d.getUTCMonth()+1,day:d.getUTCDate()}; };
const etToUtc = (y,mo,day,h,m) => Date.UTC(y,mo-1,day,h,m) - ET;

function weekends(){ const wk=[],seen=new Set();
  for(const c of candles){ const e=etParts(c.ts); if(e.dow===5){ const k=`${e.y}-${String(e.mo).padStart(2,'0')}-${String(e.day).padStart(2,'0')}`;
    if(seen.has(k))continue; seen.add(k); const s=etToUtc(e.y,e.mo,e.day,16,0); wk.push({label:k,startUtc:s,endUtc:s+65.5*3600*1000}); } }
  return wk; }
function anchor(s){ let b=null; for(const c of candles){ if(c.ts<=s)b=c; else break; } return b?b.c:null; }
function win(w){ return candles.filter(c=>c.ts>w.startUtc && c.ts<=w.endUtc); }

// ---- Strategy runners: each returns {participated:bool, events:[{ts,frac,ret}], mae} ----
// events: realized trades. frac = fraction of 1x capital. ret = P/L fraction on that capital.
// mae = worst unrealized (sum lot MtM as fraction of 1x) over the weekend.

// S0 baseline: single band from Friday close
function baseline(cs,P0,lowPct,upPct){
  const lower=P0*(1-lowPct),upper=P0*(1+upPct);
  let pos=false,entry=0,minL=Infinity,mae=0; const ev=[];
  for(const c of cs){ if(!pos){ if(c.l<=lower){pos=true;entry=lower;minL=c.l; if(c.h>=upper){ev.push({ts:c.ts,frac:1,ret:upper/entry-1});pos=false;}}}
    else{ if(c.l<minL)minL=c.l; mae=Math.min(mae,minL/entry-1); if(c.h>=upper){ev.push({ts:c.ts,frac:1,ret:upper/entry-1});pos=false;} } }
  if(pos){const last=cs[cs.length-1]; ev.push({ts:last.ts,frac:1,ret:last.c/entry-1}); mae=Math.min(mae,minL/entry-1);}
  return {participated:ev.length>0,events:ev,mae}; }

// S1 Ladder DCA (Martingale-lite): 3 equal tranches, pooled avg-cost take-profit
function ladder(cs,P0,levels,tp){
  let lots=[],idx=0,mae=0; const ev=[];
  const avg=()=>{let s=0,q=0;for(const l of lots){s+=l.entry*l.size;q+=l.size;}return q?s/q:0;};
  for(const c of cs){
    while(idx<levels.length && c.l<=P0*(1-levels[idx])){ lots.push({entry:P0*(1-levels[idx]),size:1/levels.length}); idx++; }
    if(lots.length){ const a=avg(); // MtM at bar low
      let m=0; for(const l of lots)m+=l.size*(c.l/l.entry-1); mae=Math.min(mae,m);
      const tgt=a*(1+tp); if(c.h>=tgt){ const frac=lots.reduce((s,l)=>s+l.size,0); ev.push({ts:c.ts,frac,ret:tgt/a-1}); lots=[]; } }
  }
  if(lots.length){ const a=avg(),last=cs[cs.length-1],frac=lots.reduce((s,l)=>s+l.size,0);
    ev.push({ts:last.ts,frac,ret:last.c/a-1}); }
  return {participated:ev.length>0||idx>0,events:ev,mae}; }

// S2 Trailing dip buy: buy on d% pullback from running high; TP +up%; sequential single lot; re-entry allowed
function trailing(cs,P0,d,up){
  let hi=P0,pos=false,entry=0,minL=Infinity,mae=0; const ev=[];
  for(const c of cs){
    if(!pos){ const trig=hi*(1-d); if(c.l<=trig){pos=true;entry=trig;minL=c.l; if(c.h>=entry*(1+up)){ev.push({ts:c.ts,frac:1,ret:up});pos=false;}} }
    else{ if(c.l<minL)minL=c.l; mae=Math.min(mae,minL/entry-1); if(c.h>=entry*(1+up)){ev.push({ts:c.ts,frac:1,ret:up});pos=false;} }
    if(c.h>hi)hi=c.h;
  }
  if(pos){const last=cs[cs.length-1];ev.push({ts:last.ts,frac:1,ret:last.c/entry-1});}
  return {participated:ev.length>0,events:ev,mae}; }

// S3 Grid: buy levels every step% from -min to -max below P0, each 1/G size, per-level TP +gtp%, re-arm
function grid(cs,P0,levelsPct,gtp){
  const G=levelsPct.length; const state=levelsPct.map(p=>({price:P0*(1-p),holding:false,entry:0}));
  let mae=0; const ev=[];
  for(const c of cs){
    // buys
    for(const s of state){ if(!s.holding && c.l<=s.price){ s.holding=true; s.entry=s.price; } }
    // MtM
    let m=0; for(const s of state)if(s.holding)m+=(1/G)*(c.l/s.entry-1); mae=Math.min(mae,m);
    // sells
    for(const s of state){ if(s.holding){ const tgt=s.entry*(1+gtp); if(c.h>=tgt){ ev.push({ts:c.ts,frac:1/G,ret:gtp}); s.holding=false; } } }
  }
  const last=cs[cs.length-1];
  for(const s of state){ if(s.holding){ ev.push({ts:last.ts,frac:1/G,ret:last.c/s.entry-1}); } }
  const anyBuy = state.some(s=>s.holding) || ev.length>0;
  return {participated:anyBuy,events:ev,mae}; }

// ---- Aggregate: compound equity across all events chronologically ----
function evaluate(name, runner){
  const wks=weekends(); let allEv=[]; let participated=0; let worstMAE=0; const perWk=[];
  for(const w of wks){ const P0=anchor(w.startUtc); const cs=win(w); if(!P0||!cs.length)continue;
    const r=runner(cs,P0); if(r.participated)participated++;
    worstMAE=Math.min(worstMAE,r.mae);
    // weekend return (as frac of 1x): sum frac*ret (approx, non-compounded within week)
    const wkRet=r.events.reduce((s,e)=>s+e.frac*e.ret,0);
    perWk.push({label:w.label,n:r.events.length,wkRet:wkRet*100});
    for(const e of r.events)allEv.push(e);
  }
  allEv.sort((a,b)=>a.ts-b.ts);
  let eq=1,peak=1,dd=0;
  for(const e of allEv){ eq*= (1+e.frac*e.ret); if(eq>peak)peak=eq; dd=Math.min(dd,(eq-peak)/peak); }
  const buys=allEv.length;
  return {name,participated,total:wks.length,buys,totalRet:(eq-1)*100,maxDD:dd*100,mae:worstMAE*100,perWk}; }

function row(r){ console.log(
  r.name.padEnd(26),
  `${r.participated}/${r.total}`.padStart(6),
  String(r.buys).padStart(5),
  (r.totalRet.toFixed(2)+'%').padStart(9),
  (r.maxDD.toFixed(2)+'%').padStart(8),
  (r.mae.toFixed(2)+'%').padStart(8)); }

console.log('Strategy'.padEnd(26),'Wkds'.padStart(6),'Buys'.padStart(5),'TotRet'.padStart(9),'MaxDD'.padStart(8),'MAE'.padStart(8));
console.log('-'.repeat(70));
const results=[];
results.push(evaluate('S0 baseline -1.8/+2',        (cs,P0)=>baseline(cs,P0,0.018,0.02)));
results.push(evaluate('S1 ladder -1/-1.8/-2.6 tp2', (cs,P0)=>ladder(cs,P0,[0.01,0.018,0.026],0.02)));
results.push(evaluate('S1b ladder -0.8/-1.6/-2.4 tp1.5',(cs,P0)=>ladder(cs,P0,[0.008,0.016,0.024],0.015)));
results.push(evaluate('S2 trailing dip 1.5% tp2',   (cs,P0)=>trailing(cs,P0,0.015,0.02)));
results.push(evaluate('S2b trailing dip 1.0% tp1.5',(cs,P0)=>trailing(cs,P0,0.010,0.015)));
results.push(evaluate('S3 grid -1..-5% step1 tp1',  (cs,P0)=>grid(cs,P0,[0.01,0.02,0.03,0.04,0.05],0.01)));
results.push(evaluate('S3b grid -0.8..-4% step0.8 tp1',(cs,P0)=>grid(cs,P0,[0.008,0.016,0.024,0.032,0.04],0.01)));
for(const r of results)row(r);

// detail for the two most interesting
console.log('\n--- per-weekend wkRet% (S1 ladder) ---');
console.log(results[1].perWk.map(w=>`${w.label}:${w.wkRet.toFixed(2)}(${w.n})`).join('  '));
console.log('\n--- per-weekend wkRet% (S2 trailing) ---');
console.log(results[3].perWk.map(w=>`${w.label}:${w.wkRet.toFixed(2)}(${w.n})`).join('  '));

// ---- Trailing dip param sweep with fee sensitivity ----
function evalFee(name, runner, feeSide){
  const wks=weekends(); let allEv=[],part=0,worstMAE=0;
  for(const w of wks){ const P0=anchor(w.startUtc); const cs=win(w); if(!P0||!cs.length)continue;
    const r=runner(cs,P0); if(r.participated)part++; worstMAE=Math.min(worstMAE,r.mae);
    for(const e of r.events)allEv.push(e); }
  allEv.sort((a,b)=>a.ts-b.ts);
  let eq=1,peak=1,dd=0;
  for(const e of allEv){ const net=(1+e.frac*e.ret)*(1-feeSide*e.frac)*(1-feeSide*e.frac);
    eq*=net; if(eq>peak)peak=eq; dd=Math.min(dd,(eq-peak)/peak); }
  return {name,part,total:wks.length,buys:allEv.length,ret:(eq-1)*100,dd:dd*100}; }

console.log('\n\n===== Trailing-dip sweep (gross vs net 0.05%/side) =====');
console.log('variant'.padEnd(22),'Wkds'.padStart(6),'Buys'.padStart(5),'gross'.padStart(9),'net'.padStart(9),'MaxDD(net)'.padStart(11));
for(const d of [0.010,0.0125,0.015,0.020]){
  for(const up of [0.015,0.020]){
    const g=evalFee('',(cs,P0)=>trailing(cs,P0,d,up),0);
    const n=evalFee('',(cs,P0)=>trailing(cs,P0,d,up),0.0005);
    console.log(`dip${(d*100).toFixed(2)}/tp${(up*100).toFixed(1)}`.padEnd(22),
      `${g.part}/${g.total}`.padStart(6), String(g.buys).padStart(5),
      (g.ret.toFixed(2)+'%').padStart(9),(n.ret.toFixed(2)+'%').padStart(9),(n.dd.toFixed(2)+'%').padStart(11));
  }
}
