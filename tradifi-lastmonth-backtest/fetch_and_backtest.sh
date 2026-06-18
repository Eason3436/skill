#!/usr/bin/env bash
# Fetch real Binance/OKX TRADIFI perp data live and backtest with the gold config.
# Requires the environment network policy to allow fapi.binance.com + www.okx.com.
# Usage: ./fetch_and_backtest.sh <START YYYY-MM-DD> <END YYYY-MM-DD> [LEVERAGE]
set -euo pipefail

START="${1:?need start date YYYY-MM-DD}"
END="${2:?need end date YYYY-MM-DD}"
LEV="${3:-15}"
SYMS="GLW,XLE,COHR,BMNR,ARM,HIMS,QCOM,USAR,MRVL,CSCO"

# Run from the backend dir regardless of where it's invoked.
HERE="$(cd "$(dirname "$0")" && pwd)"
BACKEND="${BTC_BACKEND:-$HERE/../../btc-trading-agent/backend}"
cd "$BACKEND"

echo ">> connectivity check"
python3 - <<'PY'
import urllib.request, socket, sys
socket.setdefaulttimeout(8)
for name,u in [("binance fapi","https://fapi.binance.com/fapi/v1/time"),
               ("okx","https://www.okx.com/api/v5/public/time")]:
    try:
        urllib.request.urlopen(u); print(f"   OK   {name}")
    except Exception as e:
        print(f"   FAIL {name}: {e}"); sys.exit(2)
PY

OUT="reports/tradifi_real_${START}_${END}_${LEV}x.json"
CSV="reports/tradifi_real_${START}_${END}_${LEV}x.csv"

echo ">> fetching live data + backtesting (gold config: 0.4%/0.05%/180m + auto-flatten, leverage ${LEV})"
python3 scripts/run_actual_tradifi_backtest.py \
  --capital 100 --leverage "$LEV" --timeframe 1m \
  --start "$START" --end "$END" \
  --entry 0.004 --exit 0.0005 --max-hold-minutes 180 \
  --simulate-costs --model-liquidation --auto-flatten-buffer 0.005 --seed 42 \
  --exclude-symbols OPENAI,ANTHROPIC \
  --symbols "$SYMS" \
  --out "$OUT" --csv-out "$CSV"

echo ">> done -> $OUT"
