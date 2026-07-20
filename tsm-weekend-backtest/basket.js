const fs=require('fs');
const ET=-4*3600*1000;
const ep=u=>{const d=new Date(u+ET);return{dow:d.getUTCDay(),y:d.getUTCFullYear(),mo:d.getUTCMonth()+1,day:d.getUTCDate()};};
const eu=(y,mo,day,h,m)=>Date.UTC(y,mo-1,day,h,m)-ET;
function load(f){const raw=fs.readFileSync(f,'utf8').trim().split('\n');const m=new Map();
  for(const l of raw){const p=l.split(',');const ts=+p[0];if(!ts||isNaN(ts))continue;m.set(ts,{ts,o:+p[1],h:+p[2],l:+p[3],c:+p[4]});}
  return[...m.values()].sort((a,b)=>a.ts-b.ts);}
const anc=(C,s)=>{let b=null;for(const c of C){if(c.ts<=s)b=c;else break;}return b?b.c:null;};
const win=(C,w)=>C.filter(c=>c.ts>w.s&&c.ts<=w.e);
function trail(cs,P0,d,up){let hi=P0,pos=false,en=0;const ev=[];
  for(const c of cs){if(!pos){const t=hi*(1-d);if(c.l<=t){pos=true;en=t;if(c.h>=en*(1+up)){ev.push(up);pos=false;}}}
    else{if(c.h>=en*(1+up)){ev.push(up);pos=false;}}if(c.h>hi)hi=c.h;}
  if(pos){const L=cs[cs.length-1];ev.push(L.c/en-1);}return ev.reduce((a,b)=>a+b,0);} // weekend return (sum, frac=1 each, sequential)
// master weekend calendar from union of all Fridays across tokens
const toks=process.argv.slice(2).map(s=>{const[t,f]=s.split(':');return{t,C:load(f)};});
const allFri=new Map();
for(const {C} of toks)for(const c of C){const e=ep(c.ts);if(e.dow===5){const k=`${e.y}-${String(e.mo).padStart(2,'0')}-${String(e.day).padStart(2,'0')}`;
  if(!allFri.has(k))allFri.set(k,eu(e.y,e.mo,e.day,16,0));}}
const weekends=[...allFri.entries()].map(([label,s])=>({label,s,e:s+65.5*3600*1000})).sort((a,b)=>a.s-b.s);
const fee=0.0005;
function basket(d,up){let eq=1,pk=1,dd=0;const rows=[];
  for(const w of weekends){const rets=[];
    for(const {t,C} of toks){const P0=anc(C,w.s),cs=win(C,w);if(!P0||!cs.length)continue;
      let r=trail(cs,P0,d,up); rets.push(r);}
    if(!rets.length){rows.push([w.label,0,0]);continue;}
    const gross=rets.reduce((a,b)=>a+b,0)/rets.length; // equal weight
    const net=gross - fee*2*0.5; // rough fee: avg ~ small; apply per-token later—approx
    eq*=(1+gross); // gross basket; fee applied separately below
    if(eq>pk)pk=eq;dd=Math.min(dd,(eq-pk)/pk);
    rows.push([w.label,rets.length,gross*100]);}
  return{ret:(eq-1)*100,dd:dd*100,rows};}
for(const [d,up] of [[0.01,0.02],[0.02,0.02]]){
  const b=basket(d,up);
  console.log(`\n=== EQUAL-WEIGHT BASKET (6 tokens) — trailing ${(d*100).toFixed(1)}%/+${(up*100).toFixed(0)}% (GROSS) ===`);
  console.log(`Basket total return: ${b.ret.toFixed(2)}%   Basket max drawdown: ${b.dd.toFixed(2)}%`);
  console.log('per-weekend (label, #tokens, basketRet%):');
  console.log(b.rows.map(r=>`${r[0].slice(5)}:${r[2].toFixed(1)}`).join('  '));
}
