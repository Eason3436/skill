const fs=require('fs');
const ET=-4*3600*1000;
const ep=u=>{const d=new Date(u+ET);return{dow:d.getUTCDay(),y:d.getUTCFullYear(),mo:d.getUTCMonth()+1,day:d.getUTCDate()};};
const eu=(y,mo,day,h,m)=>Date.UTC(y,mo-1,day,h,m)-ET;
function load(f){const raw=fs.readFileSync(f,'utf8').trim().split('\n');const m=new Map();
  for(const l of raw){const p=l.split(',');const ts=+p[0];if(!ts||isNaN(ts))continue;m.set(ts,{ts,o:+p[1],h:+p[2],l:+p[3],c:+p[4]});}
  return[...m.values()].sort((a,b)=>a.ts-b.ts);}
function wkends(C){const s=new Set();const W=[];
  for(const c of C){const e=ep(c.ts);if(e.dow===5){const k=`${e.y}-${e.mo}-${e.day}`;if(s.has(k))continue;s.add(k);const st=eu(e.y,e.mo,e.day,16,0);W.push({s:st,e:st+65.5*3600*1000});}}return W;}
const anc=(C,s)=>{let b=null;for(const c of C){if(c.ts<=s)b=c;else break;}return b?b.c:null;};
const win=(C,w)=>C.filter(c=>c.ts>w.s&&c.ts<=w.e);
function avgRange(C,W){const r=[];for(const w of W){const P0=anc(C,w.s),cs=win(C,w);if(!P0||!cs.length)continue;
  const lo=Math.min(...cs.map(x=>x.l)),hi=Math.max(...cs.map(x=>x.h));r.push((hi-lo)/P0);}return r.reduce((a,b)=>a+b,0)/r.length;}
function trail(cs,P0,d,up){let hi=P0,pos=false,en=0;const ev=[];
  for(const c of cs){if(!pos){const t=hi*(1-d);if(c.l<=t){pos=true;en=t;if(c.h>=en*(1+up)){ev.push(up);pos=false;}}}
    else{if(c.h>=en*(1+up)){ev.push(up);pos=false;}}if(c.h>hi)hi=c.h;}
  if(pos){const L=cs[cs.length-1];ev.push(L.c/en-1);}return ev;}
function evalTok(C,W,d,up,fee){let all=[],part=0;const per=[];
  for(const w of W){const P0=anc(C,w.s),cs=win(C,w);if(!P0||!cs.length)continue;const ev=trail(cs,P0,d,up);if(ev.length)part++;
    per.push({s:w.s,ret:ev.reduce((a,b)=>a+b,0)});for(const e of ev)all.push(e);}
  all.sort();let eq=1,pk=1,dd=0;for(const r of all){eq*=(1+r)*(1-fee)*(1-fee);if(eq>pk)pk=eq;dd=Math.min(dd,(eq-pk)/pk);}
  return{ret:(eq-1)*100,dd:dd*100,part,total:W.length,per};}

const toks=[['TSM','candles_raw.txt'],['NVDA','cand_NVDA.txt'],['TSLA','cand_TSLA.txt'],['AAPL','cand_AAPL.txt'],['AMD','cand_AMD.txt'],['META','cand_META.txt']];
const fee=0.0005;
const data=toks.map(([t,f])=>{const C=load(f);const W=wkends(C);const half=Math.floor(W.length/2);
  return{t,C,train:W.slice(0,half),test:W.slice(half)};});
// reference vol = avg of train ranges across tokens
const trRanges=data.map(d=>({t:d.t,r:avgRange(d.C,d.train)}));
const refR=trRanges.reduce((s,x)=>s+x.r,0)/trRanges.length;
console.log('Per-token TRAIN-half avg weekend range, scale s=range/ref, custom bands (base dip1%/tp2% x s):');
console.log('Token   trainRange%   s     -> dip%   tp%');
const bands={};
for(const {t,r} of trRanges){const s=r/refR;const dip=0.01*s,tp=0.02*s;bands[t]={dip,tp,s};
  console.log(t.padEnd(7),(r*100).toFixed(2).padStart(9),s.toFixed(2).padStart(6),'  ',(dip*100).toFixed(2).padStart(5),(tp*100).toFixed(2).padStart(6));}

console.log('\n=== TEST-half (out-of-sample) comparison: UNIFORM 1%/2% vs CUSTOM vol-scaled ===');
console.log('Token    uniform(ret/dd)      custom(ret/dd)');
let uAll=[],cAll=[]; const uPer={},cPer={};
for(const d of data){const u=evalTok(d.C,d.test,0.01,0.02,fee);const b=bands[d.t];const c=evalTok(d.C,d.test,b.dip,b.tp,fee);
  console.log(d.t.padEnd(7),`${u.ret.toFixed(2)}% / ${u.dd.toFixed(2)}%`.padStart(18),'  ',`${c.ret.toFixed(2)}% / ${c.dd.toFixed(2)}%`.padStart(18));
  uAll.push(u.ret);cAll.push(c.ret);
  for(const p of u.per){uPer[p.s]=(uPer[p.s]||0)+p.ret;}
  for(const p of c.per){cPer[p.s]=(cPer[p.s]||0)+p.ret;}}
const avg=a=>a.reduce((s,x)=>s+x,0)/a.length;
console.log(`\nAvg per-token TEST net return:  uniform ${avg(uAll).toFixed(2)}%   custom ${avg(cAll).toFixed(2)}%`);
// basket on test: average per-weekend across tokens, compound (gross approx)
function basket(per){const keys=Object.keys(per).map(Number).sort((a,b)=>a-b);let eq=1,pk=1,dd=0;
  // per already summed across tokens per weekend; need count -> approximate equal weight by dividing by #tokens present
  return null;}
