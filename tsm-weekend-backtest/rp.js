const fs=require('fs');
const ET=-4*3600*1000;
const ep=u=>{const d=new Date(u+ET);return{dow:d.getUTCDay(),y:d.getUTCFullYear(),mo:d.getUTCMonth()+1,day:d.getUTCDate()};};
const eu=(y,mo,day,h,m)=>Date.UTC(y,mo-1,day,h,m)-ET;
function load(f){const raw=fs.readFileSync(f,'utf8').trim().split('\n');const m=new Map();
  for(const l of raw){const p=l.split(',');const ts=+p[0];if(!ts||isNaN(ts))continue;m.set(ts,{ts,o:+p[1],h:+p[2],l:+p[3],c:+p[4]});}
  return[...m.values()].sort((a,b)=>a.ts-b.ts);}
function wkends(C){const s=new Set();const W=[];
  for(const c of C){const e=ep(c.ts);if(e.dow===5){const k=`${e.y}-${e.mo}-${e.day}`;if(s.has(k))continue;s.add(k);const st=eu(e.y,e.mo,e.day,16,0);W.push({label:`${e.y}-${String(e.mo).padStart(2,'0')}-${String(e.day).padStart(2,'0')}`,s:st,e:st+65.5*3600*1000});}}return W;}
const anc=(C,s)=>{let b=null;for(const c of C){if(c.ts<=s)b=c;else break;}return b?b.c:null;};
const win=(C,w)=>C.filter(c=>c.ts>w.s&&c.ts<=w.e);
function rng(C,W){const r=[];for(const w of W){const P0=anc(C,w.s),cs=win(C,w);if(!P0||!cs.length)continue;
  r.push((Math.max(...cs.map(x=>x.h))-Math.min(...cs.map(x=>x.l)))/P0);}return r.reduce((a,b)=>a+b,0)/r.length;}
function trail(cs,P0,d,up){let hi=P0,pos=false,en=0;const ev=[];
  for(const c of cs){if(!pos){const t=hi*(1-d);if(c.l<=t){pos=true;en=t;if(c.h>=en*(1+up)){ev.push(up);pos=false;}}}
    else{if(c.h>=en*(1+up)){ev.push(up);pos=false;}}if(c.h>hi)hi=c.h;}
  if(pos){const L=cs[cs.length-1];ev.push(L.c/en-1);}return ev.reduce((a,b)=>a+b,0);}
const toks=[['TSM','candles_raw.txt'],['NVDA','cand_NVDA.txt'],['TSLA','cand_TSLA.txt'],['AAPL','cand_AAPL.txt'],['AMD','cand_AMD.txt'],['META','cand_META.txt']];
const fee=0.0005;
const D=toks.map(([t,f])=>{const C=load(f);const W=wkends(C);const half=Math.floor(W.length/2);
  return{t,C,train:W.slice(0,half),test:W.slice(half),full:W};});
const refR=D.map(d=>rng(d.C,d.train)).reduce((a,b)=>a+b,0)/D.length;
D.forEach(d=>{d.r=rng(d.C,d.train);d.s=d.r/refR;d.dip=0.01*d.s;d.tp=0.02*d.s;d.invw=1/d.r;});
const sumInv=D.reduce((s,d)=>s+d.invw,0);D.forEach(d=>d.wRP=d.invw/sumInv);
console.log('Per-token: trainRange%, scale s, invVol weight(%)');
D.forEach(d=>console.log(`  ${d.t.padEnd(6)} range ${(d.r*100).toFixed(2)}%  s=${d.s.toFixed(2)}  RPweight=${(d.wRP*100).toFixed(1)}%`));

// portfolio over a weekend set: config = {bands:'uniform'|'custom', weight:'equal'|'rp'}
function port(Wsel, bandMode, weightMode){
  // union weekend labels
  const labels=[...new Set(D.flatMap(d=>d[Wsel].map(w=>w.label)))].sort();
  let eq=1,pk=1,dd=0;const rows=[];
  for(const lab of labels){let num=0,den=0;
    for(const d of D){const w=d[Wsel].find(x=>x.label===lab);if(!w)continue;const P0=anc(d.C,w.s),cs=win(d.C,w);if(!P0||!cs.length)continue;
      const dip=bandMode==='custom'?d.dip:0.01, tp=bandMode==='custom'?d.tp:0.02;
      const r=trail(cs,P0,dip,tp)-2*fee*0.5; // rough net per weekend (approx)
      const wt=weightMode==='rp'?d.wRP:1;num+=wt*r;den+=wt;}
    if(den===0){rows.push([lab,0]);continue;}
    const br=num/den;eq*=(1+br);if(eq>pk)pk=eq;dd=Math.min(dd,(eq-pk)/pk);rows.push([lab,br*100]);}
  return{ret:(eq-1)*100,dd:dd*100,rows};}

for(const Wsel of ['full','test']){
  console.log(`\n===== BASKET on ${Wsel.toUpperCase()} weekends (approx net) =====`);
  for(const [bm,wm,name] of [['uniform','equal','A: equal-weight + uniform 1%/2% (原方案)'],
                             ['custom','equal','B: equal-weight + vol-scaled bands'],
                             ['uniform','rp','C: inverse-vol weight + uniform bands'],
                             ['custom','rp','D: inverse-vol weight + vol-scaled bands (全客製)']]){
    const p=port(Wsel,bm,wm);
    console.log(`  ${name.padEnd(48)} ret ${p.ret.toFixed(2).padStart(7)}%   maxDD ${p.dd.toFixed(2).padStart(7)}%`);
  }
}
