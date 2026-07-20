#!/bin/bash
# Paginate 15m candles from newest to oldest into candles.jsonl
> candles_raw.txt
AFTER=""
for i in $(seq 1 120); do
  if [ -z "$AFTER" ]; then
    OUT=$(okx market candles TSM-USDT-SWAP --bar 15m --limit 100 --json 2>/dev/null)
  else
    OUT=$(okx market candles TSM-USDT-SWAP --bar 15m --limit 100 --after "$AFTER" --json 2>/dev/null)
  fi
  AFTER=$(echo "$OUT" | node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{try{const j=JSON.parse(d);const a=j.data||j;if(!a.length){console.log("");process.exit()}for(const r of a){process.stderr.write(r.join(",")+"\n")}const ts=a.map(x=>+x[0]);console.log(Math.min(...ts))}catch(e){console.log("")}})' 2>>candles_raw.txt)
  if [ -z "$AFTER" ]; then echo "done after $i pages"; break; fi
done
wc -l candles_raw.txt
