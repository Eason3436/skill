const fs=require('fs');
const ET=-4*3600*1000;
const ep=u=>{const d=new Date(u+ET);return{dow:d.getUTCDay(),y:d.getUTCFullYear(),mo:d.getUTCMonth()+1,day:d.getUTCDate()};};
const eu=(y,mo,day,h,m)=>Date.UTC(y,mo-1,day,h,m)-ET;
function load(file){const raw=fs.readFileSync(file,'utf8').trim().split('\n');const m=new Map();
  for(const l of raw){const p=l.split(',');const ts=+p[0];if(!ts||isNaN(ts))continue;m.set(ts,{ts,o:+p[1],h:+p[2],l:+p[3],c:+p[4]});}
  return [...m.values()].sort((a,b)=>a.ts-b.ts);}
function wkends(candles){const w=[],s=new Set();
  for(const c of candles){const e=ep(c.ts);if(e.dow===5){const k=`${e.y}-${String(e.mo).padStart(2,'0')}-${String(e.day).padStart(2,'0')}`;
    if(s.has(k))continue;s.add(k);const st=eu(e.y,e.mo,e.day,16,0);w.push({label:k,s:st,e:st+65.5*3600*1000});}}return w;}
const anc=(candles,s)=>{let b=null;for(const c of candles){if(c.ts<=s)b=c;else break;}return b?b.c:null;};
const win=(candles,w)=>candles.filter(c=>c.ts>w.s&&c.ts<=w.e);

function baseline(cs,P0,lowPct,upPct){const lo=P0*(1-lowPct),up=P0*(1+upPct);let pos=false,en=0;const ev=[];
  for(const c of cs){if(!pos){if(c.l<=lo){pos=true;en=lo;if(c.h>=up){ev.push({ts:c.ts,frac:1,ret:up/en-1});pos=false;}}}
    else{if(c.h>=up){ev.push({ts:c.ts,frac:1,ret:up/en-1});pos=false;}}}
  if(pos){const L=cs[cs.length-1];ev.push({ts:L.ts,frac:1,ret:L.c/en-1});}return ev;}
function trail(cs,P0,d,up){let hi=P0,pos=false,en=0;const ev=[];
  for(const c of cs){
    if(!pos){const t=hi*(1-d);if(c.l<=t){pos=true;en=t;if(c.h>=en*(1+up)){ev.push({ts:c.ts,frac:1,ret:up});pos=false;}}}
    else{if(c.h>=en*(1+up)){ev.push({ts:c.ts,frac:1,ret:up});pos=false;}}
    if(c.h>hi)hi=c.h;}
  if(pos){const L=cs[cs.length-1];ev.push({ts:L.ts,frac:1,ret:L.c/en-1});}return ev;}

function run(candles,runner,fee){const W=wkends(candles);let all=[],part=0;const perWk=[];
  for(const w of W){const P0=anc(candles,w.s),cs=win(candles,w);if(!P0||!cs.length)continue;
    const ev=runner(cs,P0);if(ev.length)part++;const wr=ev.reduce((s,e)=>s+e.frac*e.ret,0);
    perWk.push({label:w.label,ret:wr*100});for(const e of ev)all.push(e);}
  all.sort((a,b)=>a.ts-b.ts);let eq=1,pk=1,dd=0;
  for(const e of all){eq*=(1+e.frac*e.ret)*(1-fee)*(1-fee);if(eq>pk)pk=eq;dd=Math.min(dd,(eq-pk)/pk);}
  const sums=perWk.map(x=>x.ret);const tot=sums.reduce((a,b)=>a+b,0);const best=Math.max(...sums,0);
  return{part,total:W.length,buys:all.length,ret:(eq-1)*100,dd:dd*100,
    bestShare: tot>0?best/tot*100:0, wkStart:W[0]?.label, wkEnd:W[W.length-1]?.label};}

const files=process.argv.slice(2); // list of TOKEN:file
const fee=0.0005;
console.log(`Cross-token validation — same rules, net ${fee*100}%/side, 15m, weekend Fri16:00ET->Mon09:30ET`);
console.log('\n### Rule = TRAILING dip 1.0% / tp +2%  (the recommended rule)');
console.log('Token   Wkds  Buys   netRet   MaxDD   best%   range');
const agg={t10:[],t20:[],base:[]};
for(const f of files){const [tok,file]=f.split(':');const C=load(file);
  const r=run(C,(cs,P0)=>trail(cs,P0,0.01,0.02),fee);agg.t10.push({tok,r});
  console.log(tok.padEnd(7),`${r.part}/${r.total}`.padStart(5),String(r.buys).padStart(5),
    (r.ret.toFixed(2)+'%').padStart(9),(r.dd.toFixed(2)+'%').padStart(8),(r.bestShare.toFixed(0)+'%').padStart(6),` ${r.wkStart}..${r.wkEnd}`);}
console.log('\n### Rule = TRAILING dip 2.0% / tp +2%');
console.log('Token   Wkds  Buys   netRet   MaxDD   best%');
for(const f of files){const [tok,file]=f.split(':');const C=load(file);
  const r=run(C,(cs,P0)=>trail(cs,P0,0.02,0.02),fee);agg.t20.push({tok,r});
  console.log(tok.padEnd(7),`${r.part}/${r.total}`.padStart(5),String(r.buys).padStart(5),
    (r.ret.toFixed(2)+'%').padStart(9),(r.dd.toFixed(2)+'%').padStart(8),(r.bestShare.toFixed(0)+'%').padStart(6));}
console.log('\n### Rule = BASELINE fixed band -1.8% / +2%');
console.log('Token   Wkds  Buys   netRet   MaxDD');
for(const f of files){const [tok,file]=f.split(':');const C=load(file);
  const r=run(C,(cs,P0)=>baseline(cs,P0,0.018,0.02),fee);agg.base.push({tok,r});
  console.log(tok.padEnd(7),`${r.part}/${r.total}`.padStart(5),String(r.buys).padStart(5),
    (r.ret.toFixed(2)+'%').padStart(9),(r.dd.toFixed(2)+'%').padStart(8));}
// summary
const avg=a=>a.reduce((s,x)=>s+x.r.ret,0)/a.length;
const pos=a=>a.filter(x=>x.r.ret>0).length;
console.log('\n=== SUMMARY (positive tokens / avg net return) ===');
console.log(`Trailing 1.0/+2 : ${pos(agg.t10)}/${agg.t10.length} positive, avg ${avg(agg.t10).toFixed(2)}%`);
console.log(`Trailing 2.0/+2 : ${pos(agg.t20)}/${agg.t20.length} positive, avg ${avg(agg.t20).toFixed(2)}%`);
console.log(`Baseline -1.8/+2: ${pos(agg.base)}/${agg.base.length} positive, avg ${avg(agg.base).toFixed(2)}%`);
