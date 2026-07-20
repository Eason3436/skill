const fs=require('fs');
const ET=-4*3600*1000;
const ep=u=>{const d=new Date(u+ET);return{dow:d.getUTCDay(),y:d.getUTCFullYear(),mo:d.getUTCMonth()+1,day:d.getUTCDate()};};
const eu=(y,mo,day,h,m)=>Date.UTC(y,mo-1,day,h,m)-ET;
function load(f){const raw=fs.readFileSync(f,'utf8').trim().split('\n');const m=new Map();
  for(const l of raw){const p=l.split(',');const ts=+p[0];if(!ts||isNaN(ts))continue;m.set(ts,{ts,o:+p[1],h:+p[2],l:+p[3],c:+p[4]});}
  return[...m.values()].sort((a,b)=>a.ts-b.ts);}
function stats(tok,file){const C=load(file);
  const seen=new Set();const W=[];
  for(const c of C){const e=ep(c.ts);if(e.dow===5){const k=`${e.y}-${e.mo}-${e.day}`;if(seen.has(k))continue;seen.add(k);const s=eu(e.y,e.mo,e.day,16,0);W.push({s,e:s+65.5*3600*1000});}}
  const anc=s=>{let b=null;for(const c of C){if(c.ts<=s)b=c;else break;}return b?b.c:null;};
  const win=w=>C.filter(c=>c.ts>w.s&&c.ts<=w.e);
  const rng=[],dn=[],upx=[],fm=[],lows=[];
  for(const w of W){const P0=anc(w.s),cs=win(w);if(!P0||!cs.length)continue;
    const lo=Math.min(...cs.map(x=>x.l)),hi=Math.max(...cs.map(x=>x.h)),last=cs[cs.length-1].c;
    rng.push((hi-lo)/P0*100); dn.push((lo/P0-1)*100); upx.push((hi/P0-1)*100);
    fm.push((last/P0-1)*100); lows.push((lo/P0-1)*100);}
  const avg=a=>a.reduce((s,x)=>s+x,0)/a.length;
  const worstDn=Math.min(...lows);
  return{tok,n:rng.length,rng:avg(rng),dn:avg(dn),up:avg(upx),absFM:avg(fm.map(Math.abs)),worstDn};}
const toks=[['TSM','candles_raw.txt'],['NVDA','cand_NVDA.txt'],['TSLA','cand_TSLA.txt'],['AAPL','cand_AAPL.txt'],['AMD','cand_AMD.txt'],['META','cand_META.txt']];
console.log('Weekend-window volatility (Fri16:00ET -> Mon09:30ET), avg across weekends');
console.log('Token   #wk  avgRange%  avgDown%  avgUp%  avg|Fri->Mon|%  worstDown%');
let acc={rng:0,dn:0,up:0,fm:0,n:0};
for(const [t,f] of toks){const s=stats(t,f);acc.rng+=s.rng;acc.dn+=s.dn;acc.up+=s.up;acc.fm+=s.absFM;acc.n++;
  console.log(t.padEnd(7),String(s.n).padStart(3),s.rng.toFixed(2).padStart(9),s.dn.toFixed(2).padStart(9),
    s.up.toFixed(2).padStart(7),s.absFM.toFixed(2).padStart(13),s.worstDn.toFixed(1).padStart(11));}
console.log('-'.repeat(72));
console.log('AVG'.padEnd(7),' ',(acc.rng/acc.n).toFixed(2).padStart(9),(acc.dn/acc.n).toFixed(2).padStart(9),
  (acc.up/acc.n).toFixed(2).padStart(7),(acc.fm/acc.n).toFixed(2).padStart(13));
