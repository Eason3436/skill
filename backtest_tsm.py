#!/usr/bin/env python3
"""
Bollinger-band mean-reversion backtest for TSM-USDT-SWAP on OKX.

Strategy (as requested):
  * Split the account budget into 3 equal tranches.
  * Every time price *touches the lower band* (a new dip), buy one tranche
    (up to 3 tranches held at once). Long only.
  * Every time price *touches the upper band* (a new poke), sell 2/3 of the
    coins currently held.
  * No stop loss.

The band multiplier (standard deviations) per timeframe:
  30m -> 2.5 | 1h -> 2.5 | 2h -> 2.5
  3h  -> 2.0 | 4h -> 2.0 | 6h -> 2.0 | 8h -> 2.0 | 12h -> 2.0

Reports maximum drawdown and total return for each timeframe.

Data comes straight from the public OKX market-data API (no key needed).
OKX has no native 3H / 8H candles, so those are resampled from 1H data.
"""

import time
import math
import requests

INST = "TSM-USDT-SWAP"
OKX = "https://www.okx.com"

# ---- strategy / backtest configuration ------------------------------------
BB_PERIOD = 20          # Bollinger moving-average length (classic default)
INITIAL_CAPITAL = 10_000.0
N_TRANCHES = 3
SELL_FRACTION = 2.0 / 3.0
FEE_RATE = 0.0005       # 0.05% per fill (taker-ish); set 0 for gross figures

# timeframe -> band std multiplier
TIMEFRAMES = {
    "30m": 2.5,
    "1h":  2.5,
    "2h":  2.5,
    "3h":  2.0,
    "4h":  2.0,
    "6h":  2.0,
    "8h":  2.0,
    "12h": 2.0,
}

# OKX bar codes for the natively-supported timeframes
NATIVE_BAR = {
    "30m": "30m", "1h": "1H", "2h": "2H",
    "4h": "4H", "6h": "6H", "12h": "12H",
}
# timeframes that must be built by resampling 1H candles
RESAMPLE_FROM_1H = {"3h": 3, "8h": 8}


# ---- data fetching ---------------------------------------------------------
def fetch_candles(bar, cap=6000):
    """Return list of candles ascending by time: [ts_ms, o, h, l, c] (floats)."""
    url = OKX + "/api/v5/market/history-candles"
    rows, after = [], ""
    while len(rows) < cap:
        params = {"instId": INST, "bar": bar, "limit": "100"}
        if after:
            params["after"] = after
        for attempt in range(4):
            try:
                r = requests.get(url, params=params, timeout=25).json()
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
        data = r.get("data", [])
        if not data:
            break
        rows.extend(data)
        after = data[-1][0]
        time.sleep(0.12)
        if len(data) < 100:
            break
    # OKX returns newest-first; flip to oldest-first and keep confirmed candles
    rows = [row for row in rows if row[-1] == "1"]
    rows.reverse()
    out = []
    for row in rows:
        out.append([int(row[0]), float(row[1]), float(row[2]),
                    float(row[3]), float(row[4])])
    # de-dup on timestamp (pagination can overlap)
    seen, uniq = set(), []
    for c in out:
        if c[0] in seen:
            continue
        seen.add(c[0])
        uniq.append(c)
    uniq.sort(key=lambda x: x[0])
    return uniq


def resample(candles_1h, hours):
    """Aggregate 1H candles into `hours`-hour bars aligned to the UTC epoch."""
    bucket_ms = hours * 3600 * 1000
    groups = {}
    order = []
    for ts, o, h, l, c in candles_1h:
        key = (ts // bucket_ms) * bucket_ms
        if key not in groups:
            groups[key] = [key, o, h, l, c, ts]  # ts,o,h,l,c,last_ts
            order.append(key)
        else:
            g = groups[key]
            g[2] = max(g[2], h)      # high
            g[3] = min(g[3], l)      # low
            if ts > g[5]:            # later close
                g[4] = c
                g[5] = ts
    order.sort()
    # drop the final, possibly-incomplete bucket
    result = [groups[k][:5] for k in order]
    if len(result) > 1:
        result = result[:-1]
    return result


def get_timeframe_data(tf, cache_1h):
    if tf in NATIVE_BAR:
        return fetch_candles(NATIVE_BAR[tf])
    hours = RESAMPLE_FROM_1H[tf]
    if cache_1h[0] is None:
        cache_1h[0] = fetch_candles("1H")
    return resample(cache_1h[0], hours)


# ---- indicators ------------------------------------------------------------
def bollinger(closes, period, k):
    """Return (mid, upper, lower) lists; None until enough history."""
    n = len(closes)
    mid = [None] * n
    up = [None] * n
    lo = [None] * n
    for i in range(period - 1, n):
        window = closes[i - period + 1:i + 1]
        m = sum(window) / period
        var = sum((x - m) ** 2 for x in window) / period   # population std
        sd = math.sqrt(var)
        mid[i] = m
        up[i] = m + k * sd
        lo[i] = m - k * sd
    return mid, up, lo


# ---- backtest engine (no tranches: all-in on lower, all-out on upper) ------
def backtest_simple(candles, k):
    """Buy full budget on a fresh lower-band touch, sell everything on a fresh
    upper-band touch. No position splitting, no stop loss."""
    closes = [c[4] for c in candles]
    mid, up, lo = bollinger(closes, BB_PERIOD, k)

    cash = INITIAL_CAPITAL
    coin = 0.0
    below_state = False
    above_state = False
    trades = 0
    equity_curve = []
    peak = -1e18
    max_dd = 0.0

    for i in range(BB_PERIOD, len(candles)):
        ts, o, high, low, close = candles[i]
        upper, lower = up[i - 1], lo[i - 1]
        if upper is None or lower is None:
            continue

        touch_low = low <= lower
        if touch_low and not below_state:
            below_state = True
            if cash > 1e-6:                       # all-in
                fill = max(low, min(lower, high))
                coin += (cash / fill) * (1 - FEE_RATE)
                cash = 0.0
                trades += 1
        elif not touch_low:
            below_state = False

        touch_high = high >= upper
        if touch_high and not above_state:
            above_state = True
            if coin > 1e-12:                      # all-out
                fill = min(high, max(upper, low))
                cash += coin * fill * (1 - FEE_RATE)
                coin = 0.0
                trades += 1
        elif not touch_high:
            above_state = False

        equity = cash + coin * close
        equity_curve.append((ts, equity))
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd

    final_equity = cash + coin * closes[-1]
    start_px = closes[BB_PERIOD]
    return {
        "candles": len(candles),
        "bars_traded": len(equity_curve),
        "trades": trades,
        "final_equity": final_equity,
        "total_return": final_equity / INITIAL_CAPITAL - 1.0,
        "max_drawdown": max_dd,
        "buy_hold_return": closes[-1] / start_px - 1.0,
        "end_coin_value": coin * closes[-1],
    }


# ---- backtest engine -------------------------------------------------------
def backtest(candles, k):
    closes = [c[4] for c in candles]
    mid, up, lo = bollinger(closes, BB_PERIOD, k)

    cash = INITIAL_CAPITAL
    coin = 0.0
    open_lots = 0
    below_state = False   # currently sitting on/under the lower band
    above_state = False   # currently sitting on/over the upper band

    tranche_budget = INITIAL_CAPITAL / N_TRANCHES
    trades = 0
    equity_curve = []
    peak = -1e18
    max_dd = 0.0

    # Evaluate each candle against the PREVIOUS candle's bands (no look-ahead).
    for i in range(BB_PERIOD, len(candles)):
        ts, o, high, low, close = candles[i]
        upper = up[i - 1]
        lower = lo[i - 1]
        if upper is None or lower is None:
            continue

        # --- lower band: buy on a fresh dip ---
        touch_low = low <= lower
        if touch_low and not below_state:
            below_state = True
            if open_lots < N_TRANCHES and cash > 1e-6:
                fill = max(low, min(lower, high))       # limit fill at band
                spend = min(tranche_budget, cash)
                qty = spend / fill
                coin += qty * (1 - FEE_RATE)
                cash -= spend
                open_lots += 1
                trades += 1
        elif not touch_low:
            below_state = False

        # --- upper band: sell 2/3 on a fresh poke ---
        touch_high = high >= upper
        if touch_high and not above_state:
            above_state = True
            if coin > 1e-12:
                fill = min(high, max(upper, low))
                sell_qty = coin * SELL_FRACTION
                cash += sell_qty * fill * (1 - FEE_RATE)
                coin -= sell_qty
                open_lots = round(open_lots / 3.0)      # 3->1, 2->1, 1->0
                trades += 1
                if coin * close < 1e-6:
                    coin = 0.0
                    open_lots = 0
        elif not touch_high:
            above_state = False

        # --- mark-to-market equity & drawdown ---
        equity = cash + coin * close
        equity_curve.append((ts, equity))
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd

    final_equity = cash + coin * closes[-1]
    total_return = final_equity / INITIAL_CAPITAL - 1.0

    # buy & hold over the same tradeable window (from first evaluated candle)
    start_px = closes[BB_PERIOD]
    bh_return = closes[-1] / start_px - 1.0

    return {
        "candles": len(candles),
        "bars_traded": len(equity_curve),
        "trades": trades,
        "final_equity": final_equity,
        "total_return": total_return,
        "max_drawdown": max_dd,
        "buy_hold_return": bh_return,
        "end_coin_value": coin * closes[-1],
    }


def _print_table(title, engine, cache_1h):
    print(title)
    print("=" * 96)
    print(f"{'TF':>4} {'±std':>5} {'candles':>8} {'trades':>7} "
          f"{'Return %':>10} {'MaxDD %':>9} {'FinalEq':>11} {'Buy&Hold %':>11}")
    print("-" * 96)
    results = {}
    for tf, k in TIMEFRAMES.items():
        candles = get_timeframe_data(tf, cache_1h)
        res = engine(candles, k)
        results[tf] = res
        print(f"{tf:>4} {k:>5.1f} {res['candles']:>8} {res['trades']:>7} "
              f"{res['total_return']*100:>10.2f} {res['max_drawdown']*100:>9.2f} "
              f"{res['final_equity']:>11,.0f} {res['buy_hold_return']*100:>11.2f}")
    print("=" * 96)
    return results


def main():
    cache_1h = [None]
    print(f"Instrument: {INST}   |  Bollinger period: {BB_PERIOD}   "
          f"|  Capital: {INITIAL_CAPITAL:,.0f} USDT  |  Fee/side: {FEE_RATE*100:.3f}%\n")
    r3 = _print_table("[A] 3-tranche: buy 1/3 on each lower touch (max 3), "
                      "sell 2/3 on each upper touch", backtest, cache_1h)
    print()
    r1 = _print_table("[B] No tranches: all-in on lower touch, all-out on "
                      "upper touch", backtest_simple, cache_1h)
    print("\nNotes: long-only mean reversion, no stop loss. A 'touch' is a new "
          "wick tag of the band\n(re-armed after price closes back inside). "
          "Fills modelled at the band price. 3H/8H resampled from 1H.")
    return r3, r1


if __name__ == "__main__":
    main()
