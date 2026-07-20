const fs=require('fs');
const raw=fs.readFileSync(__dirname+'/candles_raw.txt','utf8').trim().split('\n');
const map=new Map();for(const l of raw){const p=l.split(',');const ts=+p[0];if(!ts||isNaN(ts))continue;map.set(ts,{ts,o:+p[1],h:+p[2],l:+p[3],c:+p[4]});}
const candles=[...map.values()].sort((a,b)=>a.ts-b.ts);
const ET=-4*3600*1000;
const ep=u=>{const d=new Date(u+ET);return{dow:d.getUTCDay(),y:d.getUTCFullYear(),mo:d.getUTCMonth()+1,day:d.getUTCDate()};};
const eu=(y,mo,day,h,m)=>Date.UTC(y,mo-1,day,h,m)-ET;
function wkends(){const w=[],s=new Set();for(const c of candles){const e=ep(c.ts);if(e.dow===5){const k=`${e.y}-${String(e.mo).padStart(2,'0')}-${String(e.day).padStart(2,'0')}`;if(s.has(k))continue;s.add(k);const st=eu(e.y,e.mo,e.day,16,0);w.push({label:k,s:st,e:st+65.5*3600*1000});}}return w;}
const anc=s=>{let b=null;for(const c of candles){if(c.ts<=s)b=c;else break;}return b?b.c:null;};
const win=w=>candles.filter(c=>c.ts>w.s&&c.ts<=w.e);
// trailing dip with optional stop-loss sl (fraction, e.g. 0.03). sl=0 => none
function trail(cs,P0,d,up,sl){let hi=P0,pos=false,entry=0,minL=Infinity,mae=0;const ev=[];
  for(const c of cs){
    if(!pos){const t=hi*(1-d);if(c.l<=t){pos=true;entry=t;minL=c.l;
      if(c.h>=entry*(1+up)){ev.push({ts:c.ts,frac:1,ret:up});pos=false;}
      else if(sl&&c.l<=entry*(1-sl)){ev.push({ts:c.ts,frac:1,ret:-sl});pos=false;}}}
    else{if(c.l<minL)minL=c.l;mae=Math.min(mae,minL/entry-1);
      // assume TP checked before SL within bar (optimistic-neutral)
      if(c.h>=entry*(1+up)){ev.push({ts:c.ts,frac:1,ret:up});pos=false;}
      else if(sl&&c.l<=entry*(1-sl)){ev.push({ts:c.ts,frac:1,ret:-sl});pos=false;}}
    if(c.h>hi)hi=c.h;}
  if(pos){const last=cs[cs.length-1];ev.push({ts:last.ts,frac:1,ret:last.c/entry-1});}
  return{ev,mae};}
function run(d,up,sl,fee){const W=wkends();let all=[],part=0,worstMAE=0;
  for(const w of W){const P0=anc(w.s),cs=win(w);if(!P0||!cs.length)continue;const r=trail(cs,P0,d,up,sl);if(r.ev.length)part++;worstMAE=Math.min(worstMAE,r.mae);for(const e of r.ev)all.push(e);}
  all.sort((a,b)=>a.ts-b.ts);let eq=1,pk=1,dd=0;
  for(const e of all){eq*=(1+e.frac*e.ret)*(1-fee)*(1-fee);if(eq>pk)pk=eq;dd=Math.min(dd,(eq-pk)/pk);}
  return{part,total:W.length,buys:all.length,ret:(eq-1)*100,dd:dd*100,mae:worstMAE*100};}
console.log('trailing dip=1.0% tp=+2%, vary stop-loss (net 0.05%/side)');
console.log('  SL      Wkds  Buys   netRet   MaxDD    MAE');
for(const sl of [0,0.025,0.03,0.035,0.04]){const r=run(0.01,0.02,sl,0.0005);
  console.log(`  ${sl?(sl*100).toFixed(1)+'%':'none'}`.padEnd(9),`${r.part}/${r.total}`.padStart(5),String(r.buys).padStart(5),(r.ret.toFixed(2)+'%').padStart(9),(r.dd.toFixed(2)+'%').padStart(8),(r.mae.toFixed(2)+'%').padStart(8));}
console.log('\nfor reference dip=2.0% tp=+2% no SL:');
{const r=run(0.02,0.02,0,0.0005);console.log(`  ${r.part}/${r.total} buys ${r.buys} net ${r.ret.toFixed(2)}% dd ${r.dd.toFixed(2)}% mae ${r.mae.toFixed(2)}%`);}
