#!/bin/bash
TOK="$1"; OUT="cand_${TOK}.txt"; > "$OUT"; AFTER=""
for i in $(seq 1 100); do
  if [ -z "$AFTER" ]; then O=$(okx market candles ${TOK}-USDT-SWAP --bar 15m --limit 100 --json 2>/dev/null)
  else O=$(okx market candles ${TOK}-USDT-SWAP --bar 15m --limit 100 --after "$AFTER" --json 2>/dev/null); fi
  AFTER=$(echo "$O" | node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{try{const j=JSON.parse(d);const a=j.data||j;if(!a.length){console.log("");process.exit()}for(const r of a)process.stderr.write(r.join(",")+"\n");console.log(Math.min(...a.map(x=>+x[0])))}catch(e){console.log("")}})' 2>>"$OUT")
  # stop once we have data older than 2026-03-15 (ts 1773532800000)
  if [ -z "$AFTER" ] || [ "$AFTER" -lt 1773532800000 ]; then echo "$TOK done p$i"; break; fi
done
wc -l "$OUT"
