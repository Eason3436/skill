const fs = require('fs');
const raw = fs.readFileSync(__dirname + '/candles_raw.txt', 'utf8').trim().split('\n');
const map = new Map();
for (const line of raw){ const p=line.split(','); const ts=+p[0]; if(!ts||isNaN(ts))continue;
  map.set(ts,{ts,o:+p[1],h:+p[2],l:+p[3],c:+p[4]}); }
const candles=[...map.values()].sort((a,b)=>a.ts-b.ts);
const ET=-4*3600*1000;
const etParts=u=>{const d=new Date(u+ET);return{dow:d.getUTCDay(),y:d.getUTCFullYear(),mo:d.getUTCMonth()+1,day:d.getUTCDate()};};
const etToUtc=(y,mo,day,h,m)=>Date.UTC(y,mo-1,day,h,m)-ET;
function weekends(){const wk=[],seen=new Set();
  for(const c of candles){const e=etParts(c.ts); if(e.dow===5){const k=`${e.y}-${String(e.mo).padStart(2,'0')}-${String(e.day).padStart(2,'0')}`;
    if(seen.has(k))continue; seen.add(k); const s=etToUtc(e.y,e.mo,e.day,16,0); wk.push({label:k,startUtc:s,endUtc:s+65.5*3600*1000});}}
  return wk;}
function anchor(s){let b=null;for(const c of candles){if(c.ts<=s)b=c;else break;}return b?b.c:null;}
function win(w){return candles.filter(c=>c.ts>w.startUtc&&c.ts<=w.endUtc);}

function baseline(cs,P0,lowPct,upPct){const lower=P0*(1-lowPct),upper=P0*(1+upPct);
  let pos=false,entry=0;const ev=[];
  for(const c of cs){if(!pos){if(c.l<=lower){pos=true;entry=lower;if(c.h>=upper){ev.push({ts:c.ts,frac:1,ret:upper/entry-1});pos=false;}}}
    else{if(c.h>=upper){ev.push({ts:c.ts,frac:1,ret:upper/entry-1});pos=false;}}}
  if(pos){const last=cs[cs.length-1];ev.push({ts:last.ts,frac:1,ret:last.c/entry-1});}
  return ev;}
function trailing(cs,P0,d,up){let hi=P0,pos=false,entry=0;const ev=[];
  for(const c of cs){
    if(!pos){const trig=hi*(1-d);if(c.l<=trig){pos=true;entry=trig;if(c.h>=entry*(1+up)){ev.push({ts:c.ts,frac:1,ret:up});pos=false;}}}
    else{if(c.h>=entry*(1+up)){ev.push({ts:c.ts,frac:1,ret:up});pos=false;}}
    if(c.h>hi)hi=c.h;}
  if(pos){const last=cs[cs.length-1];ev.push({ts:last.ts,frac:1,ret:last.c/entry-1});}
  return ev;}

// evaluate over a subset of weekends; returns {ret,dd,part,buys,perWk[]}
function run(runner, subset, fee=0){
  let allEv=[],part=0;const perWk=[];
  for(const w of subset){const P0=anchor(w.startUtc);const cs=win(w);if(!P0||!cs.length)continue;
    const ev=runner(cs,P0); if(ev.length)part++;
    const wkRet=ev.reduce((s,e)=>s+e.frac*e.ret,0);
    perWk.push({label:w.label,ret:wkRet*100,n:ev.length});
    for(const e of ev)allEv.push(e);}
  allEv.sort((a,b)=>a.ts-b.ts);
  let eq=1,peak=1,dd=0;
  for(const e of allEv){eq*=(1+e.frac*e.ret)*(1-fee*e.frac)*(1-fee*e.frac);if(eq>peak)peak=eq;dd=Math.min(dd,(eq-peak)/peak);}
  return{ret:(eq-1)*100,dd:dd*100,part,total:subset.length,buys:allEv.length,perWk};}

const wk=weekends();
const half=Math.floor(wk.length/2);
const train=wk.slice(0,half), test=wk.slice(half);
console.log(`Total weekends ${wk.length}. TRAIN=${train[0].label}..${train[train.length-1].label} (${train.length})  TEST=${test[0].label}..${test[test.length-1].label} (${test.length})`);

// ---------- (1) Walk-forward: pick best trailing param on TRAIN, check TEST ----------
const grid=[];
for(const d of [0.008,0.010,0.0125,0.015,0.0175,0.020,0.025]) for(const up of [0.015,0.020,0.025]) grid.push({d,up});
function best(subset){let b=null;for(const g of grid){const r=run((cs,P0)=>trailing(cs,P0,g.d,g.up),subset);
  if(!b||r.ret>b.ret)b={...g,...r};}return b;}
const bTrain=best(train);
const rTestOfTrainBest=run((cs,P0)=>trailing(cs,P0,bTrain.d,bTrain.up),test);
const bTest=best(test);
console.log('\n(1) WALK-FORWARD (out-of-sample)');
console.log(`  Best on TRAIN: dip${(bTrain.d*100).toFixed(2)}/tp${(bTrain.up*100).toFixed(1)} -> TRAIN ret ${bTrain.ret.toFixed(2)}% (part ${bTrain.part}/${bTrain.total})`);
console.log(`  Same params on TEST (true OOS): ret ${rTestOfTrainBest.ret.toFixed(2)}% dd ${rTestOfTrainBest.dd.toFixed(2)}% part ${rTestOfTrainBest.part}/${rTestOfTrainBest.total}`);
console.log(`  (Best that COULD have been on TEST: dip${(bTest.d*100).toFixed(2)}/tp${(bTest.up*100).toFixed(1)} ret ${bTest.ret.toFixed(2)}%)`);

// ---------- (2) Parameter plateau: full-sample surface for trailing tp=2% ----------
console.log('\n(2) PARAMETER PLATEAU (full sample, tp fixed +2%, vary dip)');
console.log('   dip%   fullRet   trainRet   testRet   part');
for(const d of [0.008,0.010,0.0125,0.015,0.0175,0.020,0.025]){
  const f=run((cs,P0)=>trailing(cs,P0,d,0.02),wk);
  const tr=run((cs,P0)=>trailing(cs,P0,d,0.02),train);
  const te=run((cs,P0)=>trailing(cs,P0,d,0.02),test);
  console.log(`  ${(d*100).toFixed(2).padStart(5)}  ${f.ret.toFixed(2).padStart(7)}%  ${tr.ret.toFixed(2).padStart(7)}%  ${te.ret.toFixed(2).padStart(7)}%  ${f.part}/${f.total}`);
}

// ---------- (3) Return concentration ----------
function concentration(runner,name){
  const r=run(runner,wk);
  const contrib=r.perWk.map(w=>({label:w.label,ret:w.ret})).sort((a,b)=>b.ret-a.ret);
  const tot=contrib.reduce((s,x)=>s+x.ret,0);
  const top1=contrib[0], top2=contrib.slice(0,2).reduce((s,x)=>s+x.ret,0);
  console.log(`\n(3) CONCENTRATION ${name}: sum-of-wk ${tot.toFixed(2)}%`);
  console.log(`  best weekend ${top1.label} = ${top1.ret.toFixed(2)}% (${(top1.ret/tot*100).toFixed(0)}% of total)`);
  console.log(`  top-2 weekends = ${top2.toFixed(2)}% (${(top2/tot*100).toFixed(0)}% of total)`);
  console.log(`  ex-best-weekend total = ${(tot-top1.ret).toFixed(2)}%`);
  console.log(`  all wk sorted: ${contrib.map(x=>x.label.slice(5)+':'+x.ret.toFixed(1)).join(' ')}`);
}
concentration((cs,P0)=>baseline(cs,P0,0.018,0.02),'baseline -1.8/+2');
concentration((cs,P0)=>trailing(cs,P0,0.02,0.02),'trailing 2.0/+2');
concentration((cs,P0)=>trailing(cs,P0,0.01,0.02),'trailing 1.0/+2');
